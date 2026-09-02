"""Immutable composition captured alongside each new portfolio history record."""
import datetime as dt
import math
from flask import Blueprint, jsonify, request
from flask_login import login_required
from flask_login import current_user
from sqlalchemy import MetaData, Table, Column, Integer, DateTime, Float, JSON, select, and_, or_

metadata = MetaData()
compositions = Table('portfolio_compositions', metadata,
    Column('history_id', Integer, primary_key=True, autoincrement=False),
    Column('date', DateTime, nullable=False, index=True),
    Column('total_value', Float, nullable=False),
    Column('positions', JSON, nullable=False))

new_compositions = Table('new_portfolio_compositions', metadata,
    Column('history_id', Integer, primary_key=True, autoincrement=False),
    Column('user_id', Integer, nullable=False, index=True),
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


def save_new_composition(session, history_id, user_id, date, portfolio):
    """Capture valued New Portfolio Editor positions in the snapshot transaction."""
    positions=[];xstocks={}
    for row in portfolio.get('positions',[]):
        asset=str(row.get('asset') or 'Unknown');source=str(row.get('origin') or 'Unspecified').strip() or 'Unspecified'
        value=row.get('value_usd')
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):
            raise ValueError('New portfolio composition contains an invalid value.')
        if asset.endswith('x'):
            key=('xStocks',source);xstocks[key]=xstocks.get(key,0)+value
            continue
        positions.append({'coin_id':asset,'source':source,'amount':row.get('balance'),
            'price_usd':row.get('price_usd'),'value_usd':value})
    positions.extend({'coin_id':asset,'source':source,'amount':None,'price_usd':None,'value_usd':value}
        for (asset,source),value in sorted(xstocks.items()))
    session.execute(new_compositions.insert().values(history_id=history_id,user_id=user_id,date=date,
        total_value=portfolio['total_value_usd'],positions=positions))


def create_composition_blueprint(db, user_id_provider=None):
    bp = Blueprint('composition_history', __name__)
    user_id_provider=user_id_provider or (lambda: current_user.id)

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
        table=new_compositions
        query = select(table)
        user_id=user_id_provider()
        query=query.where(table.c.user_id==user_id)
        if period != 'all':
            query = query.where(table.c.date >= dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)-dt.timedelta(days=int(period)))
        if before is not None:
            cursor_query=select(table.c.date).where(table.c.history_id==before)
            cursor_query=cursor_query.where(table.c.user_id==user_id)
            cursor_date = db.session.execute(cursor_query).scalar_one_or_none()
            if cursor_date is None:
                return jsonify(success=False, error='Snapshot cursor not found.'), 400
            query = query.where(or_(table.c.date < cursor_date,
                and_(table.c.date == cursor_date, table.c.history_id < before)))
        # Read at most 201 JSON documents; older pages are requested explicitly.
        rows = db.session.execute(query.order_by(table.c.date.desc(), table.c.history_id.desc()).limit(201)).mappings().all()
        more = len(rows) > 200
        page = rows[:200]
        data = [dict(r, date=r['date'].isoformat()+'Z') for r in reversed(page)]
        return jsonify(success=True, data=data, next_before=page[-1]['history_id'] if more else None)
    return bp
