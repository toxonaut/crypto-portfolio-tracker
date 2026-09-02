"""On-demand bounded chart responses and an explicit cash-flow annotation ledger."""
import datetime as dt
import math
import secrets
import re
from collections import deque
from itertools import islice
from decimal import Decimal, InvalidOperation
from flask import Blueprint, jsonify, request, session, current_app
from flask_login import login_required
from sqlalchemy import Table, Column, Integer, DateTime, Numeric, String, MetaData, UniqueConstraint, select, func

metadata = MetaData()
cash_flows = Table('portfolio_cash_flows', metadata,
    Column('id', Integer, primary_key=True),
    Column('request_id', String(64), unique=True),
    Column('date', DateTime, nullable=False, index=True),
    Column('amount_usd', Numeric(24, 8), nullable=False),
    Column('note', String(200), nullable=False, default=''))

new_cash_flows = Table('new_portfolio_cash_flows', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, nullable=False, index=True),
    Column('request_id', String(64)),
    Column('date', DateTime, nullable=False, index=True),
    Column('amount_usd', Numeric(24, 8), nullable=False),
    Column('note', String(200), nullable=False, default=''),
    UniqueConstraint('user_id','request_id',name='uq_new_portfolio_cash_flow_user_request'))


def parse_flow(data, now=None):
    now = now or dt.datetime.now()
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object.')
    try:
        date = dt.datetime.fromisoformat(data.get('datetime', ''))
        amount = Decimal(str(data.get('amount_usd', '')))
    except (ValueError, TypeError, InvalidOperation):
        raise ValueError('Enter a valid server-time date and USD amount.')
    if date.tzinfo is not None or date > now or date.year < 2000:
        raise ValueError('Use server time between year 2000 and now, without a timezone suffix.')
    if not amount.is_finite() or amount <= 0 or amount > Decimal('1000000000000'):
        raise ValueError('Amount must be greater than zero and at most 1 trillion USD.')
    if amount != amount.quantize(Decimal('.00000001')):
        raise ValueError('Use at most eight decimal places.')
    kind = data.get('kind')
    if kind not in ('deposit', 'withdrawal'):
        raise ValueError('Choose deposit or withdrawal.')
    note = data.get('note', '')
    if not isinstance(note, str) or len(note) > 200:
        raise ValueError('Note must be at most 200 characters.')
    key = data.get('request_id')
    if key is not None and (not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', key)):
        raise ValueError('Invalid annotation request ID.')
    return {'date': date, 'amount_usd': amount if kind == 'deposit' else -amount, 'note': note.strip(), 'request_id': key}


def read_chart(db_session, history, days='90', max_points=600, now=None, gap_seconds=10800,
               history_filters=(), flow_table=cash_flows, flow_filters=()):
    now = now or dt.datetime.now()
    if days not in ('7', '30', '90', '180', '365', '730', 'all'):
        raise ValueError('Unsupported history range.')
    if not 32 <= max_points <= 1200:
        raise ValueError('max_points must be between 32 and 1200.')
    conditions = [*history_filters, history.c.date <= now]
    if days != 'all':
        conditions.append(history.c.date >= now-dt.timedelta(days=int(days)))
    stats = db_session.execute(select(func.count(), func.min(history.c.date), func.max(history.c.date)).where(*conditions)).one()
    latest = db_session.execute(select(history.c.date).where(history.c.date <= now).order_by(history.c.date.desc()).limit(1)).scalar()
    result = {'data': [], 'flows': [], 'extremes': {}, 'meta': {
        'range': days, 'source_count': stats[0], 'returned_count': 0, 'latest': latest.isoformat() if latest else None,
        'server_now': now.isoformat(), 'stale': latest is None or (now-latest).total_seconds() > gap_seconds,
        'gap_count': 0, 'gap_threshold_hours': gap_seconds/3600, 'invalid_count': 0,
        'flow_count': 0, 'flows_truncated': False, 'sampled': False}}
    flow_conditions = [*flow_filters, flow_table.c.date <= now]
    if days != 'all': flow_conditions.append(flow_table.c.date >= now-dt.timedelta(days=int(days)))
    flows = db_session.execute(select(flow_table).where(*flow_conditions).order_by(flow_table.c.date, flow_table.c.id).limit(501)).mappings().all()
    truncated = len(flows) > 500
    flows = flows[:500]
    result['flows'] = [{'id': r['id'], 'datetime': r['date'].isoformat(), 'amount_usd': float(r['amount_usd']), 'note': r['note']} for r in flows]
    result['meta'].update(flow_count=len(flows), flows_truncated=truncated)
    if not stats[0]: return result
    bucket_count = max_points // 8
    span = max((stats[2]-stats[1]).total_seconds(), 1)
    buckets = {}
    segment = 0
    previous = None
    baseline_date = None
    flow_index = 0
    net_flow = 0.0
    recent = deque()
    extremes = {key: None for key in ['largestPercentGain','largestDollarGain','largestPercentLoss','largestDollarLoss']}
    query = select(history.c.id, history.c.date, history.c.total_value, history.c.btc).where(*conditions).order_by(history.c.date, history.c.id)
    for row in db_session.execute(query.execution_options(yield_per=1000)):
        if row.total_value is None or not math.isfinite(row.total_value):
            result['meta']['invalid_count'] += 1
            segment += 1
            continue
        if previous is not None and (row.date-previous).total_seconds() > gap_seconds:
            segment += 1
            result['meta']['gap_count'] += 1
        previous = row.date
        if baseline_date is None: baseline_date = row.date
        while flow_index < len(flows) and flows[flow_index]['date'] <= row.date:
            flow = flows[flow_index]
            if flow['date'] > baseline_date: net_flow += float(flow['amount_usd'])
            flow_index += 1
        point = {'id': row.id, 'datetime': row.date.isoformat(), 'total_value': row.total_value,
                 'btc': row.btc if row.btc is not None and math.isfinite(row.btc) else None,
                 'adjusted_usd': None if truncated else row.total_value-net_flow, 'segment': segment}
        bucket = row.id if stats[0] <= max_points else min(bucket_count-1, int((row.date-stats[1]).total_seconds()/span*bucket_count))
        selected = buckets.setdefault(bucket, {'first': point})
        selected['last'] = point
        for metric in ('total_value', 'btc', 'adjusted_usd'):
            if point[metric] is None: continue
            for suffix, compare in [('min', lambda a,b:a<b), ('max', lambda a,b:a>b)]:
                key = metric+suffix
                if key not in selected or compare(point[metric], selected[key][metric]): selected[key] = point
        target = row.date-dt.timedelta(days=1)
        while len(recent) > 1 and recent[1][0] <= target: recent.popleft()
        choices = list(islice(recent, 2)) if recent and recent[0][0] <= target else list(islice(recent, 1))
        if choices:
            date, value = min(choices, key=lambda r: abs(r[0]-target))
            if value > 0 and abs((date-target).total_seconds()) <= 14400:
                change = {'value': row.total_value-value, 'percent': (row.total_value-value)/value*100, 'date': row.date.isoformat()}
                for key in extremes:
                    metric = 'percent' if 'Percent' in key else 'value'
                    gain = 'Gain' in key
                    if (change[metric] > 0 if gain else change[metric] < 0) and (extremes[key] is None or (change[metric] > extremes[key][metric] if gain else change[metric] < extremes[key][metric])):
                        extremes[key] = change
        recent.append((row.date, row.total_value))
    points = {p['id']: p for bucket in buckets.values() for p in bucket.values()}
    result['data'] = sorted(points.values(), key=lambda p:(p['datetime'],p['id']))
    result['extremes'] = extremes
    result['meta'].update(returned_count=len(points), sampled=len(points) < stats[0])
    return result


def create_history_blueprint(db, history, gap_seconds=10800, path='/history', flow_table=cash_flows, user_id_provider=None):
    bp = Blueprint('history_chart', __name__)

    @bp.get(path)
    @login_required
    def chart():
        try:
            user_id=user_id_provider() if user_id_provider else None
            history_filters=(history.c.user_id==user_id,) if user_id_provider else ()
            flow_filters=(flow_table.c.user_id==user_id,) if user_id_provider else ()
            payload = read_chart(db.session, history, request.args.get('range', '90'), int(request.args.get('max_points','600')), gap_seconds=gap_seconds,
                history_filters=history_filters,flow_table=flow_table,flow_filters=flow_filters)
            session.setdefault('history_csrf', secrets.token_urlsafe(32))
            payload.update(success=True, csrf_token=session['history_csrf'])
            return jsonify(payload)
        except ValueError as error:
            return jsonify(success=False, error=str(error)), 400
        except Exception:
            db.session.rollback()
            current_app.logger.exception('History query failed')
            return jsonify(success=False, error='History is temporarily unavailable. Please retry.'), 503

    def csrf_valid():
        token = request.headers.get('X-CSRF-Token', '')
        return bool(session.get('history_csrf')) and secrets.compare_digest(token, session['history_csrf'])

    @bp.post(path+'/flows')
    @login_required
    def add_flow():
        if not csrf_valid(): return jsonify(success=False, error='Reload history before saving.'), 403
        try:
            values = parse_flow(request.get_json(silent=True))
        except ValueError as error:
            return jsonify(success=False, error=str(error)), 400
        try:
            user_id=user_id_provider() if user_id_provider else None
            if values['request_id']:
                conditions=[flow_table.c.request_id == values['request_id']]
                if user_id_provider: conditions.append(flow_table.c.user_id==user_id)
                existing = db.session.execute(select(flow_table).where(*conditions)).mappings().first()
                if existing:
                    if any(existing[key] != values[key] for key in ('date', 'amount_usd', 'note')):
                        return jsonify(success=False, error='Request ID already used for another annotation.'), 409
                    return jsonify(success=True, id=existing['id']), 201
            if user_id_provider: values['user_id']=user_id
            inserted = db.session.execute(flow_table.insert().values(**values))
            flow_id = inserted.inserted_primary_key[0]
            db.session.commit()
            return jsonify(success=True, id=flow_id), 201
        except Exception:
            db.session.rollback()
            return jsonify(success=False, error='Could not save annotation. Please retry.'), 503

    @bp.delete(path+'/flows/<int:flow_id>')
    @login_required
    def delete_flow(flow_id):
        if not csrf_valid(): return jsonify(success=False, error='Reload history before deleting.'), 403
        try:
            conditions=[flow_table.c.id == flow_id]
            if user_id_provider: conditions.append(flow_table.c.user_id==user_id_provider())
            deleted = db.session.execute(flow_table.delete().where(*conditions)).rowcount
            db.session.commit()
            return (jsonify(success=True), 200) if deleted else (jsonify(success=False, error='Annotation not found.'), 404)
        except Exception:
            db.session.rollback()
            return jsonify(success=False, error='Could not delete annotation. Please retry.'), 503
    return bp
