"""Cookie-free, authenticated snapshot creation with atomic per-slot deduplication."""
import datetime as dt
import math
import os
import secrets
import time
from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required
from sqlalchemy import MetaData, Table, Column, Integer, BigInteger, DateTime, String, select
from sqlalchemy.exc import IntegrityError
import requests

metadata = MetaData()
receipts = Table('worker_snapshot_receipts', metadata,
    Column('slot', BigInteger, primary_key=True),
    Column('history_id', Integer, nullable=False),
    Column('completed_at', DateTime, nullable=False))
health = Table('worker_snapshot_health', metadata,
    Column('id', Integer, primary_key=True),
    Column('last_attempt', DateTime), Column('last_success', DateTime),
    Column('last_error', String(500)))


class SnapshotUnavailable(Exception):
    pass


def worker_key():
    key = os.environ.get('WORKER_KEY', '')
    return key if len(key) >= 32 and key != 'default_worker_key' else None


def snapshot_interval():
    try:
        interval = int(os.environ.get('HISTORY_INTERVAL_SECONDS', '3600'))
    except ValueError:
        raise SnapshotUnavailable('Invalid snapshot interval configuration.')
    if not 300 <= interval <= 86400:
        raise SnapshotUnavailable('Snapshot interval must be between 300 and 86400 seconds.')
    return interval


def utcnow():
    # Existing database uses naive timestamps; production runs UTC.
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def fresh_prices(coin_ids, http=requests, now=None):
    now = now or time.time()
    prices = {}
    crypto_ids = sorted(c for c in coin_ids if c.lower() != 'chf')
    try:
        # Request only required IDs, including bitcoin for the valuation denominator.
        for start in range(0, len(crypto_ids), 100):
            batch = crypto_ids[start:start+100]
            response = http.get('https://api.coingecko.com/api/v3/simple/price',
                params={'ids': ','.join(batch), 'vs_currencies': 'usd', 'include_last_updated_at': 'true'},
                timeout=(5, 15), allow_redirects=False)
            if response.status_code != 200:
                raise SnapshotUnavailable(f'Crypto price provider returned HTTP {response.status_code}.')
            data = response.json()
            for coin in batch:
                item = data.get(coin, {})
                value, timestamp = item.get('usd'), item.get('last_updated_at')
                if not valid_positive(value) or not valid_positive(timestamp) or not -60 <= now-timestamp <= 900:
                    raise SnapshotUnavailable('Required crypto prices are missing, invalid, or older than 15 minutes.')
                prices[coin] = value
        chf_ids = [c for c in coin_ids if c.lower() == 'chf']
        if chf_ids:
            response = http.get('https://api.frankfurter.app/latest', params={'from': 'CHF', 'to': 'USD'}, timeout=(5, 15), allow_redirects=False)
            if response.status_code != 200:
                raise SnapshotUnavailable(f'Forex provider returned HTTP {response.status_code}.')
            data = response.json()
            rate = data.get('rates', {}).get('USD')
            date = dt.date.fromisoformat(data.get('date', ''))
            age = (dt.datetime.fromtimestamp(now, dt.timezone.utc).date()-date).days
            if not valid_positive(rate) or not 0 <= age <= 7:
                raise SnapshotUnavailable('CHF rate is invalid or stale.')
            prices.update({coin: rate for coin in chf_ids})
    except SnapshotUnavailable:
        raise
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        raise SnapshotUnavailable('Price provider request failed or returned invalid data.') from None
    return prices


def valid_positive(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def value_snapshot(rows, prices):
    total, actual_btc = 0.0, 0.0
    if not rows:
        raise SnapshotUnavailable('No portfolio entries are configured.')
    for row in rows:
        amount = row.amount
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
            raise SnapshotUnavailable('A portfolio balance is invalid or negative.')
        if amount == 0:
            continue
        if not valid_positive(prices.get(row.coin_id)):
            raise SnapshotUnavailable('A required portfolio price is missing or invalid.')
        total += amount * prices[row.coin_id]
        if row.coin_id == 'bitcoin': actual_btc += amount
    if not math.isfinite(total) or not valid_positive(prices.get('bitcoin')):
        raise SnapshotUnavailable('Portfolio valuation or Bitcoin price is invalid.')
    return {'total_value': total, 'btc': total/prices['bitcoin'], 'actual_btc': actual_btc}


def health_data(session, now=None):
    now = now or utcnow()
    row = session.execute(select(health).where(health.c.id == 1)).mappings().first()
    interval = snapshot_interval()
    latest = row['last_success'] if row else None
    overdue = latest is None or (now-latest).total_seconds() > interval*2
    return {'last_attempt': row['last_attempt'].isoformat()+'Z' if row and row['last_attempt'] else None,
            'last_success': latest.isoformat()+'Z' if latest else None,
            'last_error': row['last_error'] if row else None,
            'overdue': overdue, 'configured': worker_key() is not None, 'interval_seconds': interval}


def set_health(session, **values):
    # Seeded at startup; one row avoids schema changes to the legacy status table.
    session.execute(health.update().where(health.c.id == 1).values(**values))


def create_snapshot_blueprint(db, portfolio, history, price_reader=fresh_prices):
    bp = Blueprint('snapshot_worker', __name__)

    @bp.before_request
    def authenticate_worker():
        if request.endpoint == 'snapshot_worker.status':
            return None  # This route is guarded by Flask-Login instead.
        expected = worker_key()
        if not expected:
            return jsonify(success=False, error='Worker authentication is not configured.'), 503
        supplied = request.headers.get('X-Worker-Key', '')
        if not secrets.compare_digest(supplied.encode(), expected.encode()):
            return jsonify(success=False, error='Invalid worker credentials.'), 401

    @bp.get('/worker_status')
    @login_required
    def status():
        try:
            return jsonify(success=True, data=health_data(db.session))
        except Exception:
            db.session.rollback()
            return jsonify(success=False, error='Worker status unavailable.'), 503

    @bp.post('/worker_api/snapshot')
    def snapshot():
        try:
            interval = snapshot_interval()
        except SnapshotUnavailable as error:
            return jsonify(success=False, error=str(error)), 503
        payload = request.get_json(silent=True)
        slot = payload.get('slot') if isinstance(payload, dict) else None
        current_slot = int(time.time()) // interval * interval
        if isinstance(slot, bool) or not isinstance(slot, int) or slot not in (current_slot, current_slot-interval):
            return jsonify(success=False, error='Invalid or expired snapshot slot.', interval_seconds=interval), 400
        try:
            completed = db.session.execute(select(receipts).where(receipts.c.slot == slot)).mappings().first()
            if completed:
                return jsonify(success=True, duplicate=True, history_id=completed['history_id'], interval_seconds=interval)
            set_health(db.session, last_attempt=utcnow())
            db.session.commit()
            query = select(portfolio.c.id, portfolio.c.coin_id, portfolio.c.amount).order_by(portfolio.c.id)
            rows = db.session.execute(query).all()
            db.session.rollback()  # No database transaction held during network requests.
            ids = {r.coin_id for r in rows if r.amount != 0} | {'bitcoin'}
            prices = price_reader(ids)
            values = value_snapshot(rows, prices)
            # Reject concurrent edits rather than recording an inconsistent snapshot.
            if db.session.execute(query).all() != rows:
                raise SnapshotUnavailable('Holdings changed during pricing; retrying is safe.')
            completed_at = utcnow()
            inserted = db.session.execute(history.insert().values(date=completed_at, **values))
            history_id = inserted.inserted_primary_key[0]
            db.session.execute(receipts.insert().values(slot=slot, history_id=history_id, completed_at=completed_at))
            set_health(db.session, last_success=completed_at, last_error=None)
            db.session.commit()  # History, receipt and success are atomic.
            return jsonify(success=True, duplicate=False, history_id=history_id, interval_seconds=interval)
        except IntegrityError:
            db.session.rollback()
            completed = db.session.execute(select(receipts).where(receipts.c.slot == slot)).mappings().first()
            if completed:
                return jsonify(success=True, duplicate=True, history_id=completed['history_id'], interval_seconds=interval)
            return jsonify(success=False, error='Snapshot could not be committed.'), 503
        except Exception as error:
            db.session.rollback()
            message = str(error) if isinstance(error, SnapshotUnavailable) else 'Snapshot failed; check server logs.'
            if not isinstance(error, SnapshotUnavailable): current_app.logger.exception('Snapshot failed')
            try:
                set_health(db.session, last_error=message[:500])
                db.session.commit()
            except Exception:
                db.session.rollback()
            return jsonify(success=False, error=message), 503
    return bp


def initialize_snapshot_tables(engine):
    metadata.create_all(engine)
    with engine.begin() as connection:
        if connection.execute(select(health.c.id).where(health.c.id == 1)).first() is None:
            # Handle simultaneous web process startup without a duplicate-row failure.
            if engine.dialect.name == 'postgresql':
                from sqlalchemy.dialects.postgresql import insert
                connection.execute(insert(health).values(id=1).on_conflict_do_nothing())
            elif engine.dialect.name == 'sqlite':
                from sqlalchemy.dialects.sqlite import insert
                connection.execute(insert(health).values(id=1).on_conflict_do_nothing())
            else:
                connection.execute(health.insert().values(id=1))
