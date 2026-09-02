from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os
import datetime
import json
import math
import logging
import secrets
import requests
import time
from dotenv import load_dotenv
from typing import Any, Optional
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from functools import wraps
from composition_history import create_composition_blueprint, save_composition
from history_summary import read_history_summary
from history_chart import create_history_blueprint, cash_flows
from snapshot_service import create_snapshot_blueprint, initialize_snapshot_tables, health_data, worker_key, snapshot_interval, utcnow
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

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()
    
    # Add zerion_id column if it doesn't exist
    try:
        # Check if the column already exists
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('portfolio')]
        
        if 'zerion_id' not in columns:
            logger.info("Adding zerion_id column to portfolio table")
            with db.engine.connect() as connection:
                connection.execute(db.text("ALTER TABLE portfolio ADD COLUMN zerion_id VARCHAR(255)"))
                connection.commit()
                logger.info("Successfully added zerion_id column to portfolio table")
                
        # Check if worker_status table exists
        tables = inspector.get_table_names()
        if 'worker_status' not in tables:
            logger.info("Creating worker_status table")
            # Create the worker_status table directly
            with db.engine.connect() as connection:
                connection.execute(db.text("""
                CREATE TABLE worker_status (
                    id SERIAL PRIMARY KEY,
                    last_check TIMESTAMP NOT NULL,
                    is_authenticated BOOLEAN DEFAULT FALSE,
                    last_error VARCHAR(500)
                )
                """))
                connection.commit()
                logger.info("Successfully created worker_status table")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}")

class Portfolio(db.Model):
    __tablename__ = 'portfolio'  # Explicitly set lowercase table name
    id = db.Column(db.Integer, primary_key=True)
    coin_id = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    apy = db.Column(db.Float, default=0.0)
    zerion_id = db.Column(db.String(255), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'coin_id': self.coin_id,
            'source': self.source,
            'amount': self.amount,
            'apy': self.apy,
            'zerion_id': self.zerion_id
        }

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
    __table_args__ = (db.UniqueConstraint('user_id','slot',name='uq_new_portfolio_history_user_slot'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    slot = db.Column(db.BigInteger, nullable=False)
    date = db.Column(db.DateTime, nullable=False, index=True)
    total_value = db.Column(db.Float, nullable=False)

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

class WorkerStatus(db.Model):
    __tablename__ = 'worker_status'  # Explicitly set lowercase table name
    id = db.Column(db.Integer, primary_key=True)
    last_check = db.Column(db.DateTime, nullable=False)
    is_authenticated = db.Column(db.Boolean, default=False)
    last_error = db.Column(db.String(500), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'last_check': self.last_check.isoformat(),
            'is_authenticated': self.is_authenticated,
            'last_error': self.last_error
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
    cash_flows.create(db.engine, checkfirst=True)
app.register_blueprint(create_history_blueprint(db, PortfolioHistory.__table__))
with app.app_context():
    initialize_snapshot_tables(db.engine)
app.register_blueprint(create_snapshot_blueprint(db, Portfolio.__table__, PortfolioHistory.__table__))
app.register_blueprint(create_composition_blueprint(db))

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

def get_portfolio_data():
    try:
        portfolio = Portfolio.query.all()
        return [item.to_dict() for item in portfolio]
    except Exception as e:
        logger.error(f"Error fetching portfolio data: {e}")
        return []

def get_history_data():
    try:
        history = PortfolioHistory.query.order_by(PortfolioHistory.date).all()
        return [item.to_dict() for item in history]
    except Exception as e:
        logger.error(f"Error fetching history data: {e}")
        return []

def get_forex_rate(base_currency, target_currency):
    url = f"https://api.frankfurter.app/latest?from={base_currency}&to={target_currency}"
    try:
        response = requests.get(url, timeout=15)
    except Exception as e:
        err = f"Forex request failed: {e}"
        logger.error(err)
        return None, err

    if response.status_code != 200:
        body = (response.text or "")
        body = body.strip().replace("\n", " ")
        if len(body) > 300:
            body = body[:300] + "..."
        err = f"Forex error {response.status_code}: {body}" if body else f"Forex error {response.status_code}"
        logger.error(err)
        return None, err

    try:
        data = response.json()
    except Exception as e:
        err = f"Forex JSON parse failed: {e}"
        logger.error(err)
        return None, err

    rate = data.get("rates", {}).get(target_currency)
    if rate is None:
        err = f"Forex rate missing for {base_currency}->{target_currency}"
        logger.error(err)
        return None, err

    return rate, None

def get_coin_prices(coin_ids):
    from price_data import prices
    return {coin: quote for coin, quote in prices.read(coin_ids).items() if quote['status'] == 'fresh'}


def get_coin_prices_with_error(coin_ids):
    from price_data import prices, quality_summary
    quotes = prices.read(coin_ids)
    quality = quality_summary(quotes, coin_ids)
    error = None if quality['fresh'] else 'Some prices are stale or unavailable.'
    return quotes, error


def get_quantity_numeric(blob: Any, target_id: str) -> Optional[str]:
    """
    Recursively search for a target_id in the blob and return its quantity.numeric value.
    
    For Zerion API, we need to handle these cases:
    1. Direct ID match in data items
    2. Partial ID match (some IDs might have different formats)
    3. Search in nested structures
    """
    # Log the target_id at debug level to avoid noisy logs
    logger.debug(f"Searching for Zerion ID: {target_id}")
    
    # Case 1 – dict: check id, then recurse into values
    if isinstance(blob, dict):
        # Check if this is the target object with exact ID match
        blob_id = blob.get("id")
        if blob_id == target_id:
            logger.debug(f"Found exact ID match: {blob_id}")
            try:
                return blob["attributes"]["quantity"]["numeric"]
            except (KeyError, TypeError):
                logger.debug("Found ID but couldn't extract quantity.numeric")
                return None
        
        # Check for partial ID match (Zerion IDs might have different formats)
        if blob_id and isinstance(blob_id, str) and target_id in blob_id:
            logger.debug(f"Found partial ID match: {blob_id} contains {target_id}")
            try:
                return blob["attributes"]["quantity"]["numeric"]
            except (KeyError, TypeError):
                logger.debug("Found partial ID match but couldn't extract quantity.numeric")
                pass
                
        # Special case for the Zerion API response structure
        if "data" in blob and isinstance(blob["data"], list):
            logger.debug(f"Checking data array with {len(blob['data'])} items")
            for i, item in enumerate(blob["data"]):
                # Try exact match first
                item_id = item.get("id")
                if item_id == target_id:
                    logger.debug(f"Found exact ID match in data[{i}]: {item_id}")
                    try:
                        numeric = item["attributes"]["quantity"]["numeric"]
                        logger.debug(f"Extracted quantity.numeric: {numeric}")
                        return numeric
                    except (KeyError, TypeError) as e:
                        logger.debug(f"Found ID but couldn't extract quantity.numeric: {e}")
                        pass
                
                # Try partial match
                if item_id and isinstance(item_id, str) and target_id in item_id:
                    logger.debug(f"Found partial ID match in data[{i}]: {item_id} contains {target_id}")
                    try:
                        numeric = item["attributes"]["quantity"]["numeric"]
                        logger.debug(f"Extracted quantity.numeric: {numeric}")
                        return numeric
                    except (KeyError, TypeError) as e:
                        logger.debug(f"Found partial ID match but couldn't extract quantity.numeric: {e}")
                        pass
                
                # Also check if target_id contains item_id (reverse partial match)
                if item_id and isinstance(item_id, str) and item_id in target_id:
                    logger.debug(f"Found reverse partial ID match in data[{i}]: {target_id} contains {item_id}")
                    try:
                        numeric = item["attributes"]["quantity"]["numeric"]
                        logger.debug(f"Extracted quantity.numeric: {numeric}")
                        return numeric
                    except (KeyError, TypeError) as e:
                        logger.debug(f"Found reverse partial ID match but couldn't extract quantity.numeric: {e}")
                        pass
                
                # Recursive search
                result = get_quantity_numeric(item, target_id)
                if result is not None:
                    return result
                    
        # Search all children
        for key, value in blob.items():
            result = get_quantity_numeric(value, target_id)
            if result is not None:
                return result
    
    # Case 2 – list: iterate and recurse
    elif isinstance(blob, list):
        for item in blob:
            result = get_quantity_numeric(item, target_id)
            if result is not None:
                return result
    
    # Case 3 – primitives: nothing to do
    return None

def scheduled_add_history():
    try:
        logger.info("Starting scheduled add_history task")
        portfolio_data = get_portfolio_data()
        
        # Get unique coin IDs
        coin_ids = list(set(item['coin_id'] for item in portfolio_data))
        
        # Get current prices
        prices = get_coin_prices(coin_ids)
        
        # Group portfolio data by coin_id
        grouped_data = {}
        total_value = 0
        
        # First, group all entries by coin_id
        for item in portfolio_data:
            coin_id = item['coin_id']
            source = item['source']
            amount = item['amount']
            apy = item.get('apy', 0)
            
            # Initialize coin data if not exists
            if coin_id not in grouped_data:
                grouped_data[coin_id] = {
                    'total_amount': 0,
                    'sources': {},
                    'price': 0,
                    'total_value': 0,
                    'hourly_change': 0,
                    'daily_change': 0,
                    'seven_day_change': 0,
                    'monthly_yield': 0,
                    'image': "https://assets.coingecko.com/coins/images/1/small/bitcoin.png"
                }
            
            # Add source data to the coin
            grouped_data[coin_id]['sources'][source] = {
                'amount': amount,
                'apy': apy,
                'zerion_id': item.get('zerion_id', '')
            }
            
            # Add to the total amount for this coin
            grouped_data[coin_id]['total_amount'] += amount
        
        # Calculate total values and monthly yield
        for coin_id, coin_data in grouped_data.items():
            price = 0
            hourly_change = None
            daily_change = None
            seven_day_change = None
            
            if coin_id in prices:
                price_data = prices[coin_id]
                price = price_data.get('usd', 0)
                hourly_change = price_data.get('usd_1h_change', 0)
                daily_change = price_data.get('usd_24h_change', 0)
                seven_day_change = price_data.get('usd_7d_change', 0)
            
            coin_total_value = 0
            coin_monthly_yield = 0
            
            for source, source_data in coin_data['sources'].items():
                amount = source_data['amount']
                apy = source_data.get('apy', 0)
                value = amount * price
                coin_total_value += value
                
                # Calculate monthly yield for this source
                yearly_yield = value * (apy / 100)
                monthly_yield = yearly_yield / 12
                coin_monthly_yield += monthly_yield
            
            # Set the total value and monthly yield for this coin
            grouped_data[coin_id]['total_value'] = coin_total_value
            grouped_data[coin_id]['monthly_yield'] = coin_monthly_yield
            grouped_data[coin_id]['price'] = price
            grouped_data[coin_id]['hourly_change'] = hourly_change
            grouped_data[coin_id]['daily_change'] = daily_change
            grouped_data[coin_id]['seven_day_change'] = seven_day_change
            total_value += coin_total_value
        
        logger.info(f"Calculated total portfolio value: {total_value}")
        
        # Get Bitcoin price and actual Bitcoin amount in portfolio
        bitcoin_price = 0
        actual_bitcoin_amount = 0
        
        if 'bitcoin' in grouped_data:
            bitcoin_price = grouped_data['bitcoin']['price']
            actual_bitcoin_amount = grouped_data['bitcoin']['total_amount']
        
        # Calculate total value in BTC
        btc_value = 0
        if bitcoin_price > 0:
            btc_value = total_value / bitcoin_price
            
        logger.info(f"Bitcoin price: {bitcoin_price}, BTC value: {btc_value}, Actual BTC: {actual_bitcoin_amount}")
        
        # Create new history entry
        new_entry = PortfolioHistory(
            date=datetime.datetime.now(),
            total_value=total_value,
            btc=btc_value,
            actual_btc=actual_bitcoin_amount
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        logger.info(f"Successfully added history entry with total value: {total_value}")
    except Exception as e:
        logger.error(f"Error in scheduled task: {str(e)}", exc_info=True)

# Add a scheduler that runs on every request to ensure history is added
# This is a fallback mechanism in case the background scheduler fails
last_history_check = datetime.datetime.now() - datetime.timedelta(hours=2)  # Start in the past to trigger immediately

@app.before_request
def before_request():
    # The snapshot blueprint enforces its own service authentication (or login for status).
    if request.blueprint == 'snapshot_worker' or request.path == '/worker_api/new-portfolio-snapshot':
        return
    # Allow login routes and the public deployment health check.
    if request.path.startswith('/login') or request.path in ('/favicon.ico', '/health'):
        return
    
    # Check if user is authenticated
    if not current_user.is_authenticated:
        if request.path != '/':
            return redirect(url_for('login'))
    
    # Only run the history check if 1==2 (disabled)
    # We now rely on the worker.py process to add history entries
    if 1==2:
        check_history_interval()

def check_history_interval():
    global last_history_check
    now = datetime.datetime.now()
    
    # Only check once per hour maximum
    if (now - last_history_check).total_seconds() >= 3600:  # 1 hour in seconds
        try:
            # Get the most recent history entry
            latest_entry = PortfolioHistory.query.order_by(PortfolioHistory.date.desc()).first()
            
            # If no entry exists or the latest entry is more than 1 hour old, add a new one
            if not latest_entry or (now - latest_entry.date).total_seconds() >= 3600:
                logger.info("Adding history entry via request-based check")
                scheduled_add_history()
                
            # Update the last check time
            last_history_check = now
        except Exception as e:
            logger.error(f"Error in request-based history check: {str(e)}", exc_info=True)

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

@app.route('/edit_portfolio')
@login_required
def edit_portfolio():
    db_type = "PostgreSQL"
    return render_template('edit_portfolio.html', version="1.3.0", db_type=db_type)

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
        existing={row[0] for row in db.session.execute(db.select(NewPortfolioHistory.user_id).where(NewPortfolioHistory.slot==slot)).all()}
        created=[]
        for index,user_id in enumerate(users):
            if user_id in existing:continue
            data=read_new_portfolio_for_user(user_id,force=index==0)
            total=data.get('total_value_usd')
            if not data.get('complete') or not isinstance(total,(int,float)) or isinstance(total,bool) or not math.isfinite(total):
                raise ValueError('New portfolio pricing is incomplete.')
            row=NewPortfolioHistory(user_id=user_id,slot=slot,date=utcnow(),total_value=total);db.session.add(row);created.append(row)
        db.session.commit()
        first=(created[0].id if created else db.session.execute(db.select(NewPortfolioHistory.id).where(NewPortfolioHistory.slot==slot).order_by(NewPortfolioHistory.id)).scalar())
        return jsonify(success=True,duplicate=not created,history_id=first,interval_seconds=interval)
    except Exception as error:
        db.session.rollback()
        if not isinstance(error,ValueError):logger.exception('New portfolio snapshot failed')
        return jsonify(success=False,error=str(error) if isinstance(error,ValueError) else 'New portfolio snapshot failed.'),503

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

@app.route('/portfolio')
@login_required
def get_portfolio():
    portfolio_data = get_portfolio_data()
    
    # Get unique coin IDs
    coin_ids = list(set(item['coin_id'] for item in portfolio_data))
    
    # Get current prices
    from price_data import prices as price_service, quality_summary
    prices = price_service.read(set(coin_ids) | {'bitcoin'})
    required = {item['coin_id'] for item in portfolio_data if item['amount'] != 0}
    quality = quality_summary(prices, required)
    price_error = None if quality['fresh'] else 'Some prices are stale or unavailable.'
    
    # Group portfolio data by coin_id
    grouped_data = {}
    total_value = 0
    total_monthly_yield = 0
    
    # First, group all entries by coin_id
    for item in portfolio_data:
        coin_id = item['coin_id']
        source = item['source']
        amount = item['amount']
        apy = item.get('apy', 0)
        
        # Initialize coin data if not exists
        if coin_id not in grouped_data:
            # Default image if none is available from CoinGecko
            image_url = "https://assets.coingecko.com/coins/images/1/small/bitcoin.png"
            
            # If we have data from CoinGecko, use their image URL
            if coin_id in prices and 'image' in prices[coin_id]:
                image_url = prices[coin_id]['image']
            
            grouped_data[coin_id] = {
                'total_amount': 0,
                'sources': {},
                'price': 0,
                'total_value': 0,
                'hourly_change': 0,
                'daily_change': 0,
                'seven_day_change': 0,
                'monthly_yield': 0,
                'image': image_url
            }
        
        # Add source data to the coin
        grouped_data[coin_id]['sources'][source] = {
            'amount': amount,
            'apy': apy,
            'zerion_id': item.get('zerion_id', '')
        }
        
        # Add to the total amount for this coin
        grouped_data[coin_id]['total_amount'] += amount
    
    # Calculate total values and monthly yield
    for coin_id, coin_data in grouped_data.items():
        price = 0
        hourly_change = None
        daily_change = None
        seven_day_change = None
        
        if coin_id in prices:
            price_data = prices[coin_id]
            price = price_data.get('usd') or 0
            hourly_change = price_data.get('usd_1h_change')
            daily_change = price_data.get('usd_24h_change')
            seven_day_change = price_data.get('usd_7d_change')
        
        coin_total_value = 0
        coin_monthly_yield = 0
        
        for source, source_data in coin_data['sources'].items():
            amount = source_data['amount']
            apy = source_data.get('apy', 0)
            value = amount * price
            coin_total_value += value
            
            # Calculate monthly yield for this source
            yearly_yield = value * (apy / 100)
            monthly_yield = yearly_yield / 12
            coin_monthly_yield += monthly_yield
        
        # Set the total value and monthly yield for this coin
        grouped_data[coin_id]['total_value'] = coin_total_value
        grouped_data[coin_id]['monthly_yield'] = coin_monthly_yield
        grouped_data[coin_id]['price_quality'] = {k: prices[coin_id].get(k) for k in ('status', 'source', 'as_of', 'fetched_at', 'cached')}
        grouped_data[coin_id]['price'] = prices[coin_id]['usd']
        if prices[coin_id]['usd'] is None and any(v['amount'] != 0 for v in coin_data['sources'].values()):
            grouped_data[coin_id]['total_value'] = None
            grouped_data[coin_id]['monthly_yield'] = None
        grouped_data[coin_id]['hourly_change'] = hourly_change
        grouped_data[coin_id]['daily_change'] = daily_change
        grouped_data[coin_id]['seven_day_change'] = seven_day_change
        total_value += coin_total_value
        total_monthly_yield += coin_monthly_yield
    
    # Return formatted data
    return jsonify({
        'success': True,
        'data': grouped_data,
        'total_value': total_value if quality['complete'] else None,
        'total_monthly_yield': total_monthly_yield if quality['complete'] else None,
        'price_quality': quality,
        'bitcoin_price': prices['bitcoin']['usd'] if prices['bitcoin']['status'] == 'fresh' else None,
        'price_error': price_error
    })

@app.route('/history/summary')
@login_required
def get_history_summary():
    try:
        return jsonify({'success': True, 'data': read_history_summary(db.session, PortfolioHistory.__table__)})
    except Exception:
        logger.exception('Unable to load history summary')
        return jsonify({'success': False, 'error': 'History summary unavailable'}), 503


@app.route('/api/add_coin', methods=['POST'])
@login_required
def add_coin_api():
    try:
        data = request.json
        
        new_entry = Portfolio(
            coin_id=data['coin_id'],
            source=data['source'],
            amount=float(data['amount']),
            apy=float(data.get('apy', 0)),
            zerion_id=data.get('zerion_id', '')
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_coin', methods=['POST'])
@login_required
def add_coin():
    try:
        data = request.json
        
        new_entry = Portfolio(
            coin_id=data['coin_id'],
            source=data['source'],
            amount=float(data['amount']),
            apy=float(data.get('apy', 0)),
            zerion_id=data.get('zerion_id', '')
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({'success': True, 'id': new_entry.id})
    except Exception as e:
        logger.error(f"Error adding coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/update_coin/<int:coin_id>', methods=['PUT'])
@login_required
def update_coin(coin_id):
    try:
        data = request.json
        entry = Portfolio.query.get(coin_id)
        
        if not entry:
            return jsonify({'success': False, 'error': 'Entry not found'})
        
        entry.amount = float(data['amount'])
        if 'apy' in data:
            entry.apy = float(data['apy'])
        if 'zerion_id' in data:
            entry.zerion_id = data['zerion_id']
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_coin', methods=['POST'])
@login_required
def update_coin_api():
    try:
        data = request.json
        
        # Find the entry based on coin_id and source
        entry = Portfolio.query.filter_by(
            coin_id=data['coin_id'],
            source=data['old_source']
        ).first()
        
        if not entry:
            return jsonify({'success': False, 'error': 'Entry not found'})
        
        # Update fields
        entry.source = data['new_source']
        entry.amount = float(data['new_amount'])
        if 'new_apy' in data:
            entry.apy = float(data['new_apy'])
        if 'new_zerion_id' in data:
            entry.zerion_id = data['new_zerion_id']
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_source', methods=['POST'])
@login_required
def delete_coin_api():
    try:
        data = request.json
        
        entry = Portfolio.query.filter_by(
            coin_id=data['coin_id'],
            source=data['source']
        ).first()
        
        if not entry:
            return jsonify({'success': False, 'error': 'Entry not found'})
        
        db.session.delete(entry)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/delete_coin/<int:coin_id>', methods=['DELETE'])
@login_required
def delete_coin(coin_id):
    try:
        entry = Portfolio.query.get(coin_id)
        
        if not entry:
            return jsonify({'success': False, 'error': 'Entry not found'})
        
        db.session.delete(entry)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_history', methods=['POST'])
@login_required
def add_history():
    # Never trust a formatted, demo-scaled, or incomplete browser valuation.
    from snapshot_service import fresh_prices, value_snapshot, SnapshotUnavailable, utcnow
    from types import SimpleNamespace
    try:
        holdings = [(r.id, r.coin_id, r.source, r.amount) for r in Portfolio.query.order_by(Portfolio.id).all()]
        db.session.rollback()
        rows = [SimpleNamespace(coin_id=coin, source=source, amount=amount) for _, coin, source, amount in holdings]
        quotes = fresh_prices({r.coin_id for r in rows if r.amount != 0} | {'bitcoin'})
        values = value_snapshot(rows, quotes)
        if [(r.id, r.coin_id, r.source, r.amount) for r in Portfolio.query.order_by(Portfolio.id).all()] != holdings:
            raise SnapshotUnavailable('Holdings changed during pricing. Please retry.')
        entry = PortfolioHistory(date=utcnow(), **values)
        db.session.add(entry)
        db.session.flush()
        save_composition(db.session, entry.id, entry.date, rows, quotes, values['total_value'])
        db.session.commit()
        return jsonify(success=True)
    except SnapshotUnavailable as error:
        db.session.rollback()
        return jsonify(success=False, error=str(error)), 503
    except Exception:
        db.session.rollback()
        logger.exception('Manual snapshot failed')
        return jsonify(success=False, error='Snapshot could not be saved.'), 503

@app.route('/debug_db')
@login_required
def debug_db():
    """
    Debug endpoint to check database contents directly.
    """
    try:
        # Get portfolio data
        portfolio_data = Portfolio.query.all()
        portfolio_items = [item.to_dict() for item in portfolio_data]
        
        # Get history data
        history_data = PortfolioHistory.query.all()
        history_items = [item.to_dict() for item in history_data]
        
        # Return all data
        return jsonify({
            'success': True,
            'portfolio_count': len(portfolio_items),
            'portfolio_data': portfolio_items,
            'history_count': len(history_items),
            'history_data': history_items
        })
    except Exception as e:
        logger.error(f"Error debugging database: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/initialize_bitcoin_data', methods=['POST'])
@login_required
def initialize_bitcoin_data():
    """
    Initialize the database with Bitcoin data from the update_local_bitcoin_data.py script.
    """
    try:
        # Bitcoin entries to add (copied from update_local_bitcoin_data.py)
        bitcoin_entries = [
            ("bitcoin", "SolvBTC Arbitrum Avalon", 1, 0),
            ("bitcoin", "Swell Earn BTC Vault", 1, 0),
            ("bitcoin", "Ledger", 50, 0),
            ("bitcoin", "Frankencoin coll", 0.2, 0),
            ("bitcoin", "cbBTC ZeroLend", 3.0677, 0),
            ("bitcoin", "SONIC SolvBTC Silo", 1.0049, 0),
            ("bitcoin", "Aave WBTC", 1.5, 0),
            ("bitcoin", "WBTC Free", 1.5, 0),
            ("bitcoin", "Solana Raydium", 3.2845, 0),
            ("bitcoin", "Nexo", 34.7484, 0),
            ("bitcoin", "Swell swBTC", 1.049, 0),
            ("bitcoin", "swapX Sonic", 1.011, 0),
            ("bitcoin", "LBTC in Lombard vault", 2.9965, 0),
            ("bitcoin", "cbBTC Base Aave", 2, 0),
            ("bitcoin", "Gate.io Earn", 5.0054, 0),
            ("bitcoin", "cbBTC Euler finance", 0.861, 0),
            ("bitcoin", "WBTC Across", 3.0043, 0),
            ("bitcoin", "WBTC Strike", 3.0044, 0),
            ("bitcoin", "BTC Kraken", 5.2453, 0),
            ("bitcoin", "cbBTC Avalon Base", 0.0868, 0),
            ("bitcoin", "Zerolend WBTC & LBTC", 4.1316, 0),
            ("bitcoin", "cbBTC zero base", 0.8, 0),
            ("bitcoin", "eBTC Zerolend", 1, 0)
        ]
        
        # Clear existing portfolio data
        Portfolio.query.delete()
        db.session.commit()
        
        # Add new Bitcoin entries
        for coin_id, source, amount, apy in bitcoin_entries:
            new_entry = Portfolio(coin_id=coin_id, source=source, amount=amount, apy=apy)
            db.session.add(new_entry)
        
        # Calculate total Bitcoin and value
        total_btc = sum(entry[2] for entry in bitcoin_entries)
        btc_price = 65000  # Assuming a Bitcoin price of around $65,000
        total_value = total_btc * btc_price
        
        # Add a history entry for today
        current_date = datetime.datetime.now()
        new_history = PortfolioHistory(date=current_date, total_value=total_value)
        db.session.add(new_history)
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Database initialized with Bitcoin data',
            'total_bitcoin': total_btc,
            'total_value': total_value
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error initializing Bitcoin data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/debug_worker', methods=['GET'])
@login_required
def debug_worker():
    # Status inspection must never create snapshots.
    return jsonify({'success': True, 'data': health_data(db.session)})

@app.route('/fix_sequence', methods=['GET'])
@login_required
def fix_sequence():
    try:
        # Use SQLAlchemy's connection to execute raw SQL
        with db.engine.connect() as connection:
            # Find the maximum ID in the portfolio_history table
            result = connection.execute(db.text("SELECT MAX(id) FROM portfolio_history"))
            max_id = result.scalar()
            
            if max_id is None:
                logger.info("No entries found in portfolio_history table")
                return jsonify({'success': True, 'message': 'No entries found, nothing to fix'})
            
            logger.info(f"Maximum ID in portfolio_history table: {max_id}")
            
            # Reset the sequence to start from max_id + 1
            connection.execute(db.text(f"SELECT setval('portfolio_history_id_seq', {max_id}, true)"))
            
            # Commit the changes
            connection.commit()
            
            logger.info(f"Successfully reset sequence to {max_id + 1}")
            return jsonify({'success': True, 'message': f'Sequence reset to {max_id + 1}'})
        
    except Exception as e:
        logger.error(f"Error fixing sequence: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_zerion_data', methods=['POST'])
@login_required
def update_zerion_data():
    try:
        url = "https://api.zerion.io/v1/wallets/0xa9bA157770045CfFe977601fD46b9Cc3C4429604/positions/?filter[positions]=only_complex&currency=usd&filter[trash]=only_non_trash&sort=value"
        
        headers = {
            "accept": "application/json",
            "authorization": "Basic emtfZGV2XzQ5MDU4MDM1NjA1MjQwNzA5NWYzYjc5ODc3Mjg5M2MwOg=="
        }
        
        # Calculate total Bitcoin before update
        bitcoin_entries_before = Portfolio.query.filter_by(coin_id='bitcoin').all()
        total_bitcoin_before = sum(entry.amount for entry in bitcoin_entries_before)
        logger.info(f"Total Bitcoin before update: {total_bitcoin_before}")
        
        # Get current Bitcoin price
        try:
            bitcoin_price_response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
            bitcoin_price_data = bitcoin_price_response.json()
            bitcoin_price = bitcoin_price_data.get('bitcoin', {}).get('usd', 0)
            logger.info(f"Current Bitcoin price: ${bitcoin_price}")
        except Exception as e:
            logger.error(f"Error fetching Bitcoin price: {e}")
            bitcoin_price = 0
        
        logger.info("Fetching Zerion data...")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch Zerion data: {response.status_code}")
            return jsonify({'success': False, 'message': f'Failed to fetch Zerion data: {response.status_code}'})
        
        # Process the response
        logger.info("Parsing Zerion response...")
        data = json.loads(response.text)
        
        # Format the full JSON response for debugging
        json_preview = json.dumps(data, indent=2)
        
        # Get all portfolio entries
        portfolio_entries = Portfolio.query.all()
        logger.info(f"Found {len(portfolio_entries)} portfolio entries to check")
        updated_entries = []
        not_found_entries = []
        
        # Process each entry
        for entry in portfolio_entries:
            logger.info(f"Checking entry: {entry.coin_id}, {entry.source}, zerion_id: {entry.zerion_id}")
            if entry.zerion_id:
                # Get quantity from Zerion data
                quantity = get_quantity_numeric(data, entry.zerion_id)
                logger.info(f"Zerion ID {entry.zerion_id} - Quantity found: {quantity}")
                
                if quantity is not None:
                    # Update the amount
                    try:
                        new_amount = float(quantity)
                        old_amount = entry.amount
                        entry.amount = new_amount
                        logger.info(f"Updating {entry.coin_id} from {old_amount} to {new_amount}")
                        
                        updated_entries.append({
                            'coin_id': entry.coin_id,
                            'source': entry.source,
                            'zerion_id': entry.zerion_id,
                            'old_amount': old_amount,
                            'new_amount': new_amount
                        })
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting quantity to float for {entry.coin_id}: {e}")
                else:
                    not_found_entries.append({
                        'coin_id': entry.coin_id,
                        'source': entry.source,
                        'zerion_id': entry.zerion_id
                    })
        
        # Commit changes if any entries were updated
        if updated_entries:
            logger.info(f"Committing updates for {len(updated_entries)} entries")
            db.session.commit()
            
            # Calculate total Bitcoin after update
            bitcoin_entries_after = Portfolio.query.filter_by(coin_id='bitcoin').all()
            total_bitcoin_after = sum(entry.amount for entry in bitcoin_entries_after)
            bitcoin_difference = total_bitcoin_after - total_bitcoin_before
            
            # Calculate USD values
            bitcoin_difference_usd = bitcoin_difference * bitcoin_price
            
            logger.info(f"Total Bitcoin after update: {total_bitcoin_after}")
            logger.info(f"Bitcoin difference: {bitcoin_difference} BTC (${bitcoin_difference_usd})")
            
            return jsonify({
                'success': True, 
                'message': f'Updated {len(updated_entries)} entries with Zerion data',
                'bitcoin_before': total_bitcoin_before,
                'bitcoin_after': total_bitcoin_after,
                'bitcoin_difference': bitcoin_difference,
                'bitcoin_price': bitcoin_price,
                'bitcoin_difference_usd': bitcoin_difference_usd,
                'updated_entries': updated_entries,
                'not_found_entries': not_found_entries,
                'json_preview': json_preview
            })
        else:
            logger.info("No entries were updated")
            # Return more detailed information about why no entries were updated
            if not_found_entries:
                return jsonify({
                    'success': True, 
                    'message': f'No entries were updated. {len(not_found_entries)} entries had Zerion IDs but no matching data was found.',
                    'not_found_entries': not_found_entries,
                    'json_preview': json_preview
                })
            else:
                return jsonify({
                    'success': True, 
                    'message': 'No entries were updated. Make sure Zerion IDs are set for your portfolio entries.',
                    'json_preview': json_preview
                })
    
    except Exception as e:
        logger.error(f"Error fetching Zerion data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/debug_zerion', methods=['GET'])
@login_required
def debug_zerion():
    try:
        url = "https://api.zerion.io/v1/wallets/0xa9bA157770045CfFe977601fD46b9Cc3C4429604/positions/?filter[positions]=only_complex&currency=usd&filter[trash]=only_non_trash&sort=value"
        
        headers = {
            "accept": "application/json",
            "authorization": "Basic emtfZGV2XzQ5MDU4MDM1NjA1MjQwNzA5NWYzYjc5ODc3Mjg5M2MwOg=="
        }
        
        logger.info("Fetching Zerion data for debugging...")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'message': f'Failed to fetch Zerion data: {response.status_code}'})
        
        # Parse the response
        logger.info("Parsing Zerion response...")
        data = json.loads(response.text)
        
        # Get all portfolio entries with zerion_id
        portfolio_entries = Portfolio.query.filter(Portfolio.zerion_id.isnot(None)).all()
        
        # Test results for each zerion_id
        test_results = []
        for entry in portfolio_entries:
            if entry.zerion_id:
                quantity = get_quantity_numeric(data, entry.zerion_id)
                test_results.append({
                    'coin_id': entry.coin_id,
                    'source': entry.source,
                    'zerion_id': entry.zerion_id,
                    'current_amount': entry.amount,
                    'zerion_quantity': quantity
                })
        
        # Return debug information
        return jsonify({
            'success': True,
            'test_results': test_results,
            'data_structure': {
                'keys': list(data.keys()) if isinstance(data, dict) else None,
                'data_type': str(type(data)),
                'has_data': 'data' in data if isinstance(data, dict) else False,
                'data_length': len(data.get('data', [])) if isinstance(data, dict) and 'data' in data else 0
            }
        })
    
    except Exception as e:
        logger.error(f"Error debugging Zerion data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/debug_zerion_full', methods=['GET'])
@login_required
def debug_zerion_full():
    try:
        url = "https://api.zerion.io/v1/wallets/0xa9bA157770045CfFe977601fD46b9Cc3C4429604/positions/?filter[positions]=only_complex&currency=usd&filter[trash]=only_non_trash&sort=value"
        
        headers = {
            "accept": "application/json",
            "authorization": "Basic emtfZGV2XzQ5MDU4MDM1NjA1MjQwNzA5NWYzYjc5ODc3Mjg5M2MwOg=="
        }
        
        logger.info("Fetching full Zerion data for debugging...")
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'message': f'Failed to fetch Zerion data: {response.status_code}'})
        
        # Return the full response
        return response.json()
    
    except Exception as e:
        logger.error(f"Error debugging Zerion data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/migrate_zerion_id', methods=['GET'])
@login_required
def migrate_zerion_id_endpoint():
    try:
        # Check if the column exists and get its current type
        with db.engine.connect() as connection:
            # Check PostgreSQL column type
            result = connection.execute(db.text(
                "SELECT character_maximum_length FROM information_schema.columns "
                "WHERE table_name = 'portfolio' AND column_name = 'zerion_id'"
            ))
            column_info = result.fetchone()
            
            if column_info:
                current_length = column_info[0]
                logger.info(f"Current zerion_id column length: {current_length}")
                
                if current_length < 255:
                    # Execute the migration to increase column length
                    logger.info("Altering zerion_id column to VARCHAR(255)")
                    connection.execute(db.text("ALTER TABLE portfolio ALTER COLUMN zerion_id TYPE VARCHAR(255)"))
                    connection.commit()
                    logger.info("Successfully altered zerion_id column to VARCHAR(255)")
                    return jsonify({
                        'success': True, 
                        'message': f'Successfully migrated zerion_id column from VARCHAR({current_length}) to VARCHAR(255)'
                    })
                else:
                    return jsonify({
                        'success': True, 
                        'message': f'No migration needed. zerion_id column is already VARCHAR({current_length})'
                    })
            else:
                return jsonify({
                    'success': False, 
                    'message': 'zerion_id column not found in portfolio table'
                })
    
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/debug_history')
@login_required
def debug_history():
    """
    Debug endpoint to check the most recent history entries
    """
    try:
        # Get the 10 most recent history entries
        recent_entries = PortfolioHistory.query.order_by(PortfolioHistory.date.desc()).limit(10).all()
        
        # Format the entries for display
        entries_data = []
        for entry in recent_entries:
            entries_data.append({
                'id': entry.id,
                'date': entry.date.strftime('%Y-%m-%d %H:%M:%S'),
                'total_value': entry.total_value,
                'btc': entry.btc,
                'actual_btc': entry.actual_btc
            })
        
        # Get the current time
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate time since last entry
        time_since_last = "No entries found"
        if entries_data:
            last_entry_time = datetime.datetime.strptime(entries_data[0]['date'], '%Y-%m-%d %H:%M:%S')
            current_time_obj = datetime.datetime.now()
            time_diff = current_time_obj - last_entry_time
            hours, remainder = divmod(time_diff.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_since_last = f"{int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds"
        
        return jsonify({
            'success': True,
            'current_time': current_time,
            'time_since_last_entry': time_since_last,
            'entries': entries_data
        })
    except Exception as e:
        logger.error(f"Error in debug_history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    # Only run the development server when running locally
    # Railway will use gunicorn to run the application
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
