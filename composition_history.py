"""Immutable composition captured alongside each new portfolio history record."""
import datetime as dt
from flask import Blueprint, jsonify, request
from flask_login import login_required
from sqlalchemy import MetaData, Table, Column, Integer, DateTime, Float, JSON, select, and_, or_

metadata = MetaData()
compositions = Table('portfolio_compositions', metadata,
    Column('history_id', Integer, primary_key=True, autoincrement=False),
    Column('date', DateTime, nullable=False, index=True),
    Column('total_value', Float, nullable=False),
    Column('positions', JSON, nullable=False))


def save_composition(session, history_id, date, rows, prices, total_value):
    # Save in the caller's transaction: never commit a partial snapshot.
    positions = [{'coin_id':r.coin_id, 'source':r.source or 'Unspecified',
                  'amount':r.amount, 'price_usd':prices.get(r.coin_id),
                  'value_usd':r.amount*prices[r.coin_id] if r.amount else 0.0} for r in rows]
    session.execute(compositions.insert().values(history_id=history_id, date=date,
                    total_value=total_value, positions=positions))


def create_composition_blueprint(db):
    bp = Blueprint('composition_history', __name__)

    @bp.get('/history/composition')
    @login_required
    def read_composition():
        period = request.args.get('range', '30')
        if period not in ('7','30','90','365','all'):
            return jsonify(success=False, error='Unsupported period.'), 400
        try:
            before = int(request.args['before']) if 'before' in request.args else None
            if before is not None and before <= 0: raise ValueError()
        except ValueError:
            return jsonify(success=False, error='Invalid page cursor.'), 400
        query = select(compositions)
        if period != 'all':
            query = query.where(compositions.c.date >= dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)-dt.timedelta(days=int(period)))
        if before is not None:
            cursor_date = db.session.execute(select(compositions.c.date).where(compositions.c.history_id == before)).scalar_one_or_none()
            if cursor_date is None:
                return jsonify(success=False, error='Snapshot cursor not found.'), 400
            query = query.where(or_(compositions.c.date < cursor_date,
                and_(compositions.c.date == cursor_date, compositions.c.history_id < before)))
        # Read at most 201 JSON documents; older pages are requested explicitly.
        rows = db.session.execute(query.order_by(compositions.c.date.desc(), compositions.c.history_id.desc()).limit(201)).mappings().all()
        more = len(rows) > 200
        page = rows[:200]
        data = [dict(r, date=r['date'].isoformat()+'Z') for r in reversed(page)]
        return jsonify(success=True, data=data, next_before=page[-1]['history_id'] if more else None)
    return bp
