from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import datetime
import math
import logging
import secrets
import time
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy import literal
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from composition_history import create_composition_blueprint, save_new_composition, new_compositions
from history_summary import read_history_summary
from history_chart import create_history_blueprint, cash_flows, new_cash_flows
from snapshot_service import worker_key, snapshot_interval, utcnow
from kraken_portfolio import portfolio as kraken_portfolio, KrakenUnavailable, enrich_market_data
from new_portfolio import manual_positions, merge_portfolios, overview_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

def resolve_database_url() -> Optional[str]:
    """
    Resolve a usable SQLAlchemy Postgres URL from environment variables.
    Preference order:
      1) DATABASE_URL
      2) POSTGRES_URL
      3) Compose from PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    Normalizes postgres:// to postgresql:// as required by SQLAlchemy.
    """
    raw_db = os.environ.get('DATABASE_URL')
    raw_pg = os.environ.get('POSTGRES_URL')
    if raw_db is not None and raw_db.strip() == '':
        logger.warning("DATABASE_URL is set but empty")
    if raw_pg is not None and raw_pg.strip() == '':
        logger.warning("POSTGRES_URL is set but empty")

    url = (raw_db.strip() if isinstance(raw_db, str) else raw_db) or (raw_pg.strip() if isinstance(raw_pg, str) else raw_pg)
    if not url:
        pg_host = os.environ.get('PGHOST')
        pg_port = os.environ.get('PGPORT', '5432')
        pg_user = os.environ.get('PGUSER')
        pg_pass = os.environ.get('PGPASSWORD')
        pg_db = os.environ.get('PGDATABASE')
        # Warn if present but empty
        for name, val in [('PGHOST', pg_host), ('PGPORT', pg_port), ('PGUSER', pg_user), ('PGPASSWORD', pg_pass), ('PGDATABASE', pg_db)]:
            if val is not None and isinstance(val, str) and val.strip() == '':
                logger.warning(f"{name} is set but empty")
        # Normalize
        pg_host = pg_host.strip() if isinstance(pg_host, str) else pg_host
        pg_port = (pg_port.strip() if isinstance(pg_port, str) else pg_port) or '5432'
        pg_user = pg_user.strip() if isinstance(pg_user, str) else pg_user
        pg_pass = pg_pass.strip() if isinstance(pg_pass, str) else pg_pass
        pg_db = pg_db.strip() if isinstance(pg_db, str) else pg_db
        if all([pg_host, pg_user, pg_db]):
            # Password and port are optional (port defaults to 5432)
            cred = pg_user
            if pg_pass:
                cred = f"{pg_user}:{pg_pass}"
            url = f"postgresql://{cred}@{pg_host}:{pg_port}/{pg_db}"
    if url and url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url

# Resolve database URL with fallbacks
database_url = resolve_database_url()
if not database_url:
    logger.error("No database connection info found. Expected DATABASE_URL, POSTGRES_URL, or PG* variables (PGHOST, PGUSER, PGPASSWORD, PGDATABASE).")
    raise SystemExit(1)

logger.info(f"Starting Crypto Portfolio Tracker v1.3.0")
logger.info(f"Using database URL: {'postgresql://<redacted>' if database_url else 'Unknown'}")

# Configure the Flask application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PORT'] = os.environ.get('PORT', 5000)
# Set a secret key for session management
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

db = SQLAlchemy(app)

class NewPortfolioEntry(db.Model):
    __tablename__ = 'new_portfolio_entry'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    coin_id = db.Column(db.String(100), nullable=False)
    origin = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    apy = db.Column(db.Float, nullable=False, default=0.0)

    def to_editor_dict(self):
        return {'id':self.id,'coin_id':self.coin_id,'origin':self.origin,'amount':self.amount,'apy':self.apy}

class NewPortfolioHistory(db.Model):
    __tablename__ = 'new_portfolio_history'
    __table_args__ = (db.UniqueConstraint('user_id','slot',name='uq_new_portfolio_history_user_slot'),
        db.Index('ix_new_portfolio_history_user_date','user_id','date'))
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    slot = db.Column(db.BigInteger, nullable=False)
    date = db.Column(db.DateTime, nullable=False, index=True)
    total_value = db.Column(db.Float, nullable=False)
    btc = db.Column(db.Float, nullable=True)
    actual_btc = db.Column(db.Float, nullable=True)
    legacy_history_id = db.Column(db.Integer, nullable=True)

class NewPortfolioWorkerHealth(db.Model):
    __tablename__ = 'new_portfolio_worker_health'
    id = db.Column(db.Integer, primary_key=True)
    last_attempt = db.Column(db.DateTime, nullable=True)
    last_success = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.String(500), nullable=True)

class PortfolioHistory(db.Model):
    __table_args__ = (db.Index('ix_portfolio_history_date', 'date'),)
    __tablename__ = 'portfolio_history'  # Explicitly set lowercase table name
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    btc = db.Column(db.Float, nullable=True)  # Total value divided by Bitcoin price
    actual_btc = db.Column(db.Float, nullable=True)  # Actual Bitcoin amount in portfolio
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'total_value': self.total_value,
            'btc': self.btc if self.btc is not None else 0,
            'actual_btc': self.actual_btc if self.actual_btc is not None else 0
        }

# Existing databases need this index too (create_all does not migrate existing tables).
# PostgreSQL concurrent creation avoids blocking history writes during deployment.
with app.app_context():
    with db.engine.connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
        if db.inspect(connection).has_table('portfolio_history'):
            concurrent = 'CONCURRENTLY ' if connection.dialect.name == 'postgresql' else ''
            connection.execute(db.text(
                f'CREATE INDEX {concurrent}IF NOT EXISTS ix_portfolio_history_date '
                'ON portfolio_history (date)'
            ))

# User model for authentication
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    name = db.Column(db.String(100))
    
    def __init__(self, email, name):
        self.email = email
        self.name = name

def migrate_legacy_history_if_unambiguous():
    """Copy legacy history exactly once when its sole owner can be identified."""
    users=[row[0] for row in db.session.execute(db.select(User.id)).all()]
    if len(users)!=1:return 0
    user_id=users[0];target=NewPortfolioHistory.__table__;source=PortfolioHistory.__table__
    missing=~db.exists(db.select(literal(1)).where(target.c.user_id==user_id,
        target.c.legacy_history_id==source.c.id))
    statement=target.insert().from_select(
        ['user_id','slot','date','total_value','btc','actual_btc','legacy_history_id'],
        db.select(literal(user_id),-(source.c.id+1),source.c.date,source.c.total_value,
            source.c.btc,source.c.actual_btc,source.c.id).where(missing))
    result=db.session.execute(statement);db.session.commit()
    return result.rowcount

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables if they don't exist
with app.app_context():
    # Check if users table exists
    try:
        db.session.execute(db.select(User).limit(1))
        logger.info("Users table exists")
    except Exception as e:
        logger.info("Creating users table")
        db.create_all()
        logger.info("Users table created")

# Isolated storage for the replacement editor; existing portfolio data is untouched.
with app.app_context():
    db.create_all()

# Additive ledger only; historical balances are never rewritten.
with app.app_context():
    new_cash_flows.create(db.engine, checkfirst=True)
    columns={column['name'] for column in db.inspect(db.engine).get_columns('new_portfolio_history')}
    with db.engine.begin() as connection:
        for name,column_type in (('btc','FLOAT'),('actual_btc','FLOAT'),('legacy_history_id','INTEGER')):
            if name not in columns:
                clause='IF NOT EXISTS ' if connection.dialect.name=='postgresql' else ''
                connection.execute(db.text(f'ALTER TABLE new_portfolio_history ADD COLUMN {clause}{name} {column_type}'))
        connection.execute(db.text('CREATE INDEX IF NOT EXISTS ix_new_portfolio_history_user_date ON new_portfolio_history (user_id, date)'))
        connection.execute(db.text('CREATE UNIQUE INDEX IF NOT EXISTS uq_new_portfolio_history_user_legacy ON new_portfolio_history (user_id, legacy_history_id)'))
    # Legacy annotations had no owner. Preserve them only when ownership is unambiguous.
    users=[row[0] for row in db.session.execute(db.select(User.id)).all()]
    if (len(users)==1 and db.inspect(db.engine).has_table(cash_flows.name) and
            db.session.execute(db.select(db.func.count()).select_from(new_cash_flows)).scalar()==0):
        legacy=db.session.execute(db.select(cash_flows).order_by(cash_flows.c.id)).mappings().all()
        if legacy:
            db.session.execute(new_cash_flows.insert(),[{'user_id':users[0],'request_id':row['request_id'],
                'date':row['date'],'amount_usd':row['amount_usd'],'note':row['note']} for row in legacy]);db.session.commit()
    migrate_legacy_history_if_unambiguous()
app.register_blueprint(create_history_blueprint(db,NewPortfolioHistory.__table__,path='/new-portfolio/history',
    flow_table=new_cash_flows,user_id_provider=lambda:current_user.id))
app.register_blueprint(create_composition_blueprint(db))
with app.app_context():
    new_compositions.create(db.engine, checkfirst=True)

# Initialize OAuth
oauth = OAuth(app)

# Get the base URL for the application
if 'RAILWAY_ENVIRONMENT' in os.environ:
    base_url = "https://crypto-tracker.up.railway.app"
    logger.info(f"Using Railway base URL: {base_url}")
else:
    base_url = "http://localhost:5000"
    logger.info(f"Using local base URL: {base_url}")

# Configure Google OAuth
google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')

if not google_client_id or not google_client_secret:
    logger.warning("Google OAuth credentials not set. Authentication will not work properly.")

google = oauth.register(
    name='google',
    client_id=google_client_id,
    client_secret=google_client_secret,
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

@app.before_request
def before_request():
    # The worker endpoint authenticates with its dedicated service key.
    if request.path == '/worker_api/new-portfolio-snapshot':
        return
    if request.path.startswith('/login') or request.path in ('/favicon.ico', '/health'):
        return
    if not current_user.is_authenticated and request.path != '/':
        return redirect(url_for('login'))

@app.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200


@app.route('/')
@login_required
def index():
    return render_template('index.html', version="1.3.0", db_type="PostgreSQL")

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login/google')
def login_google():
    # Use the correct callback URL format that matches Google Cloud Console configuration
    callback_url = f"{base_url}/login/google/callback"
    logger.info(f"Using Google OAuth callback URL: {callback_url}")
    return google.authorize_redirect(callback_url)

@app.route('/login/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.get('userinfo')
        email = user_info.json().get('email')
        name = user_info.json().get('name')
        
        logger.info(f"Google OAuth login attempt from: {email}")
        
        # Only allow specific email to login
        if email != 'martin.schaerer@gmail.com':
            logger.warning(f"Unauthorized login attempt from: {email}")
            return redirect(url_for('login', error='unauthorized'))
        
        # Check if user exists in database
        user = User.query.filter_by(email=email).first()
        
        # If user doesn't exist, create a new one
        if not user:
            user = User(email=email, name=name)
            db.session.add(user)
            db.session.commit()
            logger.info(f"Created new user: {email}")
        
        # Log in the user
        login_user(user)
        try:migrate_legacy_history_if_unambiguous()
        except Exception:
            db.session.rollback();logger.exception('Legacy history migration failed after login')
        logger.info(f"User logged in successfully: {email}")
        
        # Redirect to the main page
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error during Google OAuth callback: {str(e)}", exc_info=True)
        return redirect(url_for('login', error='auth_error'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/statistics')
@login_required
def statistics():
    return render_template('statistics.html')

@app.route('/experimental-portfolio')
@login_required
def experimental_portfolio():
    return render_template('experimental_portfolio.html')

@app.route('/api/experimental/kraken-portfolio')
@login_required
def get_kraken_portfolio():
    try:
        return jsonify(success=True, data=read_new_portfolio(request.args.get('refresh') == '1'))
    except KrakenUnavailable as error:
        return jsonify(success=False, error=str(error)), 503
    except Exception:
        logger.exception('Unexpected Kraken portfolio error')
        return jsonify(success=False, error='Kraken portfolio is temporarily unavailable.'), 503

def read_new_portfolio_for_user(user_id,force=False):
    from price_data import prices as price_service
    data=enrich_market_data(kraken_portfolio.read(force=force),price_service.read)
    entries=[entry.to_editor_dict() for entry in NewPortfolioEntry.query.filter_by(user_id=user_id).order_by(NewPortfolioEntry.id).all()]
    return merge_portfolios(data,manual_positions(entries,price_service.read))

def read_new_portfolio(force=False):
    return read_new_portfolio_for_user(current_user.id,force)

@app.route('/api/new-portfolio/overview')
@login_required
def get_new_portfolio_overview():
    try:
        from price_data import prices as price_service
        data=read_new_portfolio()
        bitcoin=price_service.read({'bitcoin'}).get('bitcoin',{}).get('usd')
        return jsonify(success=True,data=overview_data(data,bitcoin))
    except KrakenUnavailable as error:
        return jsonify(success=False,error=str(error)),503
    except Exception:
        logger.exception('Unexpected new portfolio overview error')
        return jsonify(success=False,error='New portfolio overview is temporarily unavailable.'),503

@app.route('/new-portfolio/history/summary')
@login_required
def get_new_portfolio_history_summary():
    try:
        data=read_history_summary(db.session,NewPortfolioHistory.__table__,filters=(NewPortfolioHistory.user_id==current_user.id,))
        return jsonify(success=True,data=data)
    except Exception:
        db.session.rollback();logger.exception('Unable to load new portfolio history summary')
        return jsonify(success=False,error='New portfolio history summary unavailable.'),503

def capture_new_portfolio_snapshots(user_ids,slot,track_health=False):
    from price_data import prices as price_service
    health=NewPortfolioWorkerHealth.query.get(1) if track_health else None
    if track_health:
        if health is None: health=NewPortfolioWorkerHealth(id=1);db.session.add(health)
        health.last_attempt=utcnow();db.session.commit()
    existing={row[0] for row in db.session.execute(db.select(NewPortfolioHistory.user_id).where(
        NewPortfolioHistory.slot==slot,NewPortfolioHistory.user_id.in_(user_ids))).all()}
    created=[]
    for index,user_id in enumerate(user_ids):
        if user_id in existing:continue
        data=read_new_portfolio_for_user(user_id,force=index==0)
        total=data.get('total_value_usd');bitcoin_quote=price_service.read({'bitcoin'}).get('bitcoin',{})
        bitcoin=bitcoin_quote.get('usd')
        if (not data.get('complete') or not isinstance(total,(int,float)) or isinstance(total,bool) or not math.isfinite(total)
                or bitcoin_quote.get('status')!='fresh' or not isinstance(bitcoin,(int,float)) or bitcoin<=0):
            raise ValueError('New portfolio pricing is incomplete or the Bitcoin reference price is not fresh.')
        if any(position.get('balance')!=0 and position.get('editable') and
                (position.get('market_data') or {}).get('status')!='fresh' for position in data.get('positions',[])):
            raise ValueError('A manual New Portfolio position has a stale or unavailable price.')
        actual_btc=sum(position.get('balance') or 0 for position in data.get('positions',[]) if position.get('asset')=='BTC')
        row=NewPortfolioHistory(user_id=user_id,slot=slot,date=utcnow(),total_value=total,btc=total/bitcoin,actual_btc=actual_btc)
        db.session.add(row);db.session.flush();save_new_composition(db.session,row.id,user_id,row.date,data);created.append(row)
    if track_health:
        health=NewPortfolioWorkerHealth.query.get(1)
        if created:
            health.last_success=created[-1].date
        else:
            # A retry may be the first request after the health table migration.
            # Seed success from the snapshot whose slot the worker just confirmed.
            confirmed_date=db.session.execute(db.select(db.func.max(NewPortfolioHistory.date)).where(
                NewPortfolioHistory.slot==slot,NewPortfolioHistory.user_id.in_(user_ids))).scalar()
            if confirmed_date: health.last_success=confirmed_date
        health.last_error=None
    db.session.commit()
    first=created[0].id if created else db.session.execute(db.select(NewPortfolioHistory.id).where(
        NewPortfolioHistory.slot==slot,NewPortfolioHistory.user_id.in_(user_ids)).order_by(NewPortfolioHistory.id)).scalar()
    return {'success':True,'duplicate':not created,'history_id':first,'interval_seconds':snapshot_interval()}

def record_new_snapshot_error(error):
    try:
        health=NewPortfolioWorkerHealth.query.get(1)
        if health is None: health=NewPortfolioWorkerHealth(id=1);db.session.add(health)
        health.last_error=str(error)[:500];db.session.commit()
    except Exception: db.session.rollback()

@app.route('/worker_api/new-portfolio-snapshot', methods=['POST'])
def save_new_portfolio_snapshot():
    expected=worker_key();supplied=request.headers.get('X-Worker-Key','')
    if not expected:return jsonify(success=False,error='Worker authentication is not configured.'),503
    if not secrets.compare_digest(supplied.encode(),expected.encode()):return jsonify(success=False,error='Invalid worker credentials.'),401
    try: interval=snapshot_interval()
    except Exception as error:return jsonify(success=False,error=str(error)),503
    payload=request.get_json(silent=True);slot=payload.get('slot') if isinstance(payload,dict) else None
    current_slot=int(time.time())//interval*interval
    if isinstance(slot,bool) or not isinstance(slot,int) or slot not in (current_slot,current_slot-interval):
        return jsonify(success=False,error='Invalid or expired snapshot slot.',interval_seconds=interval),400
    try:
        users=[row[0] for row in db.session.execute(db.select(User.id).order_by(User.id)).all()]
        if not users:return jsonify(success=False,error='No portfolio owner is configured.'),503
        return jsonify(**capture_new_portfolio_snapshots(users,slot,track_health=True))
    except Exception as error:
        db.session.rollback()
        record_new_snapshot_error(error)
        if not isinstance(error,ValueError):logger.exception('New portfolio snapshot failed')
        return jsonify(success=False,error=str(error) if isinstance(error,ValueError) else 'New portfolio snapshot failed.'),503

@app.route('/new-portfolio/add_history',methods=['POST'])
@login_required
def add_new_portfolio_history():
    try:
        # Manual captures remain on demand and do not consume the worker's hourly slot.
        slot=int(time.time()*1000000)
        return jsonify(**capture_new_portfolio_snapshots([current_user.id],slot))
    except Exception as error:
        db.session.rollback()
        if not isinstance(error,ValueError):logger.exception('Manual New Portfolio snapshot failed')
        return jsonify(success=False,error=str(error) if isinstance(error,ValueError) else 'Snapshot could not be saved.'),503

@app.route('/new-portfolio/worker_status')
@login_required
def new_portfolio_worker_status():
    try:
        interval=snapshot_interval();row=NewPortfolioWorkerHealth.query.get(1);now=utcnow()
        latest=row.last_success if row else None
        return jsonify(success=True,data={'last_attempt':row.last_attempt.isoformat()+'Z' if row and row.last_attempt else None,
            'last_success':latest.isoformat()+'Z' if latest else None,'last_error':row.last_error if row else None,
            'overdue':latest is None or (now-latest).total_seconds()>interval*2,'configured':worker_key() is not None,
            'interval_seconds':interval})
    except Exception:
        db.session.rollback();return jsonify(success=False,error='Worker status unavailable.'),503

@app.route('/api/new-portfolio/manual', methods=['POST'])
@login_required
def add_new_portfolio_entry():
    try:
        data=request.get_json(silent=True) or {}
        coin_id=str(data.get('coin_id','')).strip().lower();origin=str(data.get('origin','')).strip()
        amount=float(data.get('amount'));apy=float(data.get('apy',0))
        if not coin_id or len(coin_id)>100 or not origin or len(origin)>100: raise ValueError('Coin and origin are required and must be at most 100 characters.')
        if not math.isfinite(amount) or amount == 0: raise ValueError('Amount must be a finite nonzero number.')
        if not math.isfinite(apy) or not 0 <= apy <= 10000: raise ValueError('APY must be between 0 and 10,000 percent.')
        entry=NewPortfolioEntry(user_id=current_user.id,coin_id=coin_id,origin=origin,amount=amount,apy=apy)
        db.session.add(entry);db.session.commit()
        return jsonify(success=True,id=entry.id),201
    except (TypeError,ValueError) as error:
        db.session.rollback();return jsonify(success=False,error=str(error)),400
    except Exception:
        db.session.rollback();logger.exception('Unable to add new portfolio entry')
        return jsonify(success=False,error='Entry could not be saved.'),503

@app.route('/api/new-portfolio/manual/<int:entry_id>', methods=['PATCH'])
@login_required
def update_new_portfolio_entry(entry_id):
    entry=NewPortfolioEntry.query.filter_by(id=entry_id,user_id=current_user.id).first()
    if entry is None:return jsonify(success=False,error='Entry not found.'),404
    try:
        data=request.get_json(silent=True) or {};origin=str(data.get('origin','')).strip()
        amount=float(data.get('amount'));apy=float(data.get('apy'))
        if not origin or len(origin)>100: raise ValueError('Origin is required and must be at most 100 characters.')
        if not math.isfinite(amount) or amount == 0: raise ValueError('Amount must be a finite nonzero number.')
        if not math.isfinite(apy) or not 0 <= apy <= 10000: raise ValueError('APY must be between 0 and 10,000 percent.')
        entry.origin=origin;entry.amount=amount;entry.apy=apy;db.session.commit()
        return jsonify(success=True)
    except (TypeError,ValueError) as error:
        db.session.rollback();return jsonify(success=False,error=str(error)),400
    except Exception:
        db.session.rollback();logger.exception('Unable to update new portfolio entry')
        return jsonify(success=False,error='Entry could not be updated.'),503

@app.route('/api/new-portfolio/manual/<int:entry_id>', methods=['DELETE'])
@login_required
def delete_new_portfolio_entry(entry_id):
    entry=NewPortfolioEntry.query.filter_by(id=entry_id,user_id=current_user.id).first()
    if entry is None:return jsonify(success=False,error='Entry not found.'),404
    try:
        db.session.delete(entry);db.session.commit();return jsonify(success=True)
    except Exception:
        db.session.rollback();logger.exception('Unable to delete new portfolio entry')
        return jsonify(success=False,error='Entry could not be deleted.'),503

if __name__ == '__main__':
    # Only run the development server when running locally
    # Railway will use gunicorn to run the application
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
