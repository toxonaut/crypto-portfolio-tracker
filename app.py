from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import os
import datetime
import json
import logging
import requests
import time
from dotenv import load_dotenv
from typing import Any, Optional
from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()

# Get the database URL from environment variable
database_url = os.environ.get('DATABASE_URL')

# If running on Railway, use the internal connection string
if 'RAILWAY_ENVIRONMENT' in os.environ:
    logger.info("Running on Railway - using internal PostgreSQL connection")
    # Use the internal connection string for better performance and security
    database_url = "postgresql://postgres:RyWIsfflSCUOVGjjfrBvSVLGfqeGGYet@postgres.railway.internal:5432/railway"
    logger.info(f"Using internal Railway database connection")
else:
    logger.info("Running locally - using external PostgreSQL connection")
    # Local environment should have DATABASE_URL in .env file
    if not database_url:
        logger.warning("DATABASE_URL environment variable not set locally, using default SQLite")
        database_url = 'sqlite:///portfolio.db'
    else:
        logger.info(f"Using external Railway database connection")

# If the URL starts with postgres://, change it to postgresql:// (SQLAlchemy requirement)
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

logger.info(f"Starting Crypto Portfolio Tracker v1.3.0")
logger.info(f"Using database: {database_url.split('@')[1] if database_url and '@' in database_url else 'Unknown'}")

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
    except Exception as e:
        logger.error(f"Error adding zerion_id column: {e}")

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

class PortfolioHistory(db.Model):
    __tablename__ = 'portfolio_history'  # Explicitly set lowercase table name
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.DateTime, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    btc = db.Column(db.Float, nullable=True)  # Total value divided by Bitcoin price
    actual_btc = db.Column(db.Float, nullable=True)  # Actual Bitcoin amount in portfolio
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d'),
            'total_value': self.total_value,
            'btc': self.btc if self.btc is not None else 0,
            'actual_btc': self.actual_btc if self.actual_btc is not None else 0
        }

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

def get_coin_prices(coin_ids):
    if not coin_ids:
        return {}
    
    try:
        # Get data from the markets endpoint which includes more comprehensive information
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=180&page=1&sparkline=false&price_change_percentage=1h%2C24h%2C7d&locale=en"
        response = requests.get(url)
        
        if response.status_code == 200:
            market_data = response.json()
            # Create a dictionary mapping coin IDs to their market data
            coin_data = {}
            for coin in market_data:
                if coin['id'] in coin_ids:
                    # Check if the price change percentages exist and are not None
                    price_1h = coin.get('price_change_percentage_1h_in_currency', 0)
                    price_24h = coin.get('price_change_percentage_24h', 0)  
                    price_7d = coin.get('price_change_percentage_7d_in_currency', 0)
                    
                    # Ensure we have valid numbers, not None
                    if price_1h is None: price_1h = 0
                    if price_24h is None: price_24h = 0
                    if price_7d is None: price_7d = 0
                    
                    coin_data[coin['id']] = {
                        'usd': coin['current_price'],
                        'usd_1h_change': price_1h,
                        'usd_24h_change': price_24h,
                        'usd_7d_change': price_7d,
                        'image': coin['image']
                    }
            
            # If any requested coins are missing from the first 100 coins, try to fetch them directly
            missing_coins = [coin_id for coin_id in coin_ids if coin_id not in coin_data]
            if missing_coins:
                logger.info(f"Fetching additional data for coins not in top 100: {missing_coins}")
                additional_url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(missing_coins)}&vs_currencies=usd&include_24hr_change=true&include_1h_change=true&include_7d_change=true"
                additional_response = requests.get(additional_url)
                if additional_response.status_code == 200:
                    additional_data = additional_response.json()
                    for coin_id, data in additional_data.items():
                        if coin_id in missing_coins:
                            coin_data[coin_id] = data
            
            return coin_data
        else:
            logger.error(f"Error fetching market data: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Exception fetching market data: {e}")
        return {}

def get_quantity_numeric(blob: Any, target_id: str) -> Optional[str]:
    """
    Recursively search for a target_id in the blob and return its quantity.numeric value.
    
    For Zerion API, we need to handle these cases:
    1. Direct ID match in data items
    2. Partial ID match (some IDs might have different formats)
    3. Search in nested structures
    """
    # Log the target_id we're looking for
    logger.info(f"Searching for Zerion ID: {target_id}")
    
    # Case 1 – dict: check id, then recurse into values
    if isinstance(blob, dict):
        # Check if this is the target object with exact ID match
        blob_id = blob.get("id")
        if blob_id == target_id:
            logger.info(f"Found exact ID match: {blob_id}")
            try:
                return blob["attributes"]["quantity"]["numeric"]
            except (KeyError, TypeError):
                logger.info("Found ID but couldn't extract quantity.numeric")
                return None
        
        # Check for partial ID match (Zerion IDs might have different formats)
        if blob_id and isinstance(blob_id, str) and target_id in blob_id:
            logger.info(f"Found partial ID match: {blob_id} contains {target_id}")
            try:
                return blob["attributes"]["quantity"]["numeric"]
            except (KeyError, TypeError):
                logger.info("Found partial ID match but couldn't extract quantity.numeric")
                pass
                
        # Special case for the Zerion API response structure
        if "data" in blob and isinstance(blob["data"], list):
            logger.info(f"Checking data array with {len(blob['data'])} items")
            for i, item in enumerate(blob["data"]):
                # Try exact match first
                item_id = item.get("id")
                if item_id == target_id:
                    logger.info(f"Found exact ID match in data[{i}]: {item_id}")
                    try:
                        numeric = item["attributes"]["quantity"]["numeric"]
                        logger.info(f"Extracted quantity.numeric: {numeric}")
                        return numeric
                    except (KeyError, TypeError) as e:
                        logger.info(f"Found ID but couldn't extract quantity.numeric: {e}")
                        pass
                
                # Try partial match
                if item_id and isinstance(item_id, str) and target_id in item_id:
                    logger.info(f"Found partial ID match in data[{i}]: {item_id} contains {target_id}")
                    try:
                        numeric = item["attributes"]["quantity"]["numeric"]
                        logger.info(f"Extracted quantity.numeric: {numeric}")
                        return numeric
                    except (KeyError, TypeError) as e:
                        logger.info(f"Found partial ID match but couldn't extract quantity.numeric: {e}")
                        pass
                
                # Also check if target_id contains item_id (reverse partial match)
                if item_id and isinstance(item_id, str) and item_id in target_id:
                    logger.info(f"Found reverse partial ID match in data[{i}]: {target_id} contains {item_id}")
                    try:
                        numeric = item["attributes"]["quantity"]["numeric"]
                        logger.info(f"Extracted quantity.numeric: {numeric}")
                        return numeric
                    except (KeyError, TypeError) as e:
                        logger.info(f"Found reverse partial ID match but couldn't extract quantity.numeric: {e}")
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
    # Skip authentication for login routes
    if request.path.startswith('/login') or request.path == '/favicon.ico':
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

@app.route('/')
@login_required
def index():
    db_type = "PostgreSQL" if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite"
    return render_template('index.html', version="1.3.0", db_type=db_type)

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
    db_type = "PostgreSQL" if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite"
    return render_template('edit_portfolio.html', version="1.3.0", db_type=db_type)

@app.route('/portfolio')
@login_required
def get_portfolio():
    portfolio_data = get_portfolio_data()
    
    # Get unique coin IDs
    coin_ids = list(set(item['coin_id'] for item in portfolio_data))
    
    # Get current prices
    prices = get_coin_prices(coin_ids)
    
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
        total_monthly_yield += coin_monthly_yield
    
    # Return formatted data
    return jsonify({
        'success': True,
        'data': grouped_data,
        'total_value': total_value,
        'total_monthly_yield': total_monthly_yield
    })

@app.route('/history')
@login_required
def get_history():
    history_data = get_history_data()
    
    # Format the data for the frontend
    formatted_data = []
    for item in history_data:
        formatted_data.append({
            'datetime': item['date'],
            'total_value': item['total_value'],
            'btc': item['btc'],
            'actual_btc': item['actual_btc']
        })
    
    return jsonify({
        'success': True,
        'data': formatted_data
    })

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
    try:
        data = request.get_json()
        logger.info(f"Received add_history request with data: {data}")
        
        if not data or 'total_value' not in data:
            logger.error("Invalid data received in add_history request")
            return jsonify({'success': False, 'error': 'Invalid data'}), 400
        
        # Validate total_value
        total_value = float(data['total_value'])
        if total_value <= 0:
            logger.error(f"Invalid total_value: {total_value}")
            return jsonify({'success': False, 'error': 'Total value must be greater than 0'}), 400
            
        # Check if BTC values were provided in the request
        btc_value = data.get('btc_value', 0)
        actual_btc = data.get('actual_btc', 0)
        
        # If BTC values were not provided, calculate them
        if btc_value == 0 or actual_btc == 0:
            # Get portfolio data to calculate Bitcoin price and amount
            portfolio_data = get_portfolio_data()
            coin_ids = list(set(item['coin_id'] for item in portfolio_data))
            prices = get_coin_prices(coin_ids)
            
            # Initialize variables
            bitcoin_price = 0
            actual_bitcoin_amount = 0
            
            # Find Bitcoin in the portfolio
            for item in portfolio_data:
                if item['coin_id'] == 'bitcoin':
                    actual_bitcoin_amount += item['amount']
            
            # Get Bitcoin price
            if 'bitcoin' in prices:
                bitcoin_price = prices['bitcoin'].get('usd', 0)
            
            # Calculate total value in BTC
            if bitcoin_price > 0:
                btc_value = total_value / bitcoin_price
            else:
                logger.error("Cannot calculate BTC value: Bitcoin price is 0")
                return jsonify({'success': False, 'error': 'Bitcoin price is 0'}), 400
                
            actual_btc = actual_bitcoin_amount
                
            logger.info(f"Calculated Bitcoin price: {bitcoin_price}, BTC value: {btc_value}, Actual BTC: {actual_btc}")
        else:
            # Validate provided BTC values
            if btc_value <= 0:
                logger.error(f"Invalid btc_value: {btc_value}")
                return jsonify({'success': False, 'error': 'BTC value must be greater than 0'}), 400
                
            logger.info(f"Using provided BTC value: {btc_value}, Actual BTC: {actual_btc}")
        
        new_entry = PortfolioHistory(
            date=datetime.datetime.now(),
            total_value=total_value,
            btc=btc_value,
            actual_btc=actual_btc
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        logger.info(f"Manually added history entry with total value: {data['total_value']}, BTC value: {btc_value}")
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error in add_history: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

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
    """
    Debug endpoint to check worker status and manually trigger history addition
    """
    try:
        # Get the current portfolio data
        portfolio_data = get_portfolio_data()
        
        # Get unique coin IDs
        coin_ids = list(set(item['coin_id'] for item in portfolio_data))
        
        # Get current prices
        prices = get_coin_prices(coin_ids)
        
        # Calculate total value
        total_value = 0
        for item in portfolio_data:
            coin_id = item['coin_id']
            amount = item['amount']
            
            if coin_id in prices:
                price = prices[coin_id].get('usd', 0)
                item_value = amount * price
                total_value += item_value
        
        # Add a new history entry
        new_entry = PortfolioHistory(
            date=datetime.datetime.now(),
            total_value=total_value
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        # Get the most recent history entries
        recent_entries = PortfolioHistory.query.order_by(PortfolioHistory.date.desc()).limit(10).all()
        recent_entries_data = [entry.to_dict() for entry in recent_entries]
        
        return jsonify({
            'success': True,
            'message': f'Added new history entry with value: {total_value}',
            'recent_entries': recent_entries_data,
            'worker_info': {
                'environment': os.environ.get('RAILWAY_ENVIRONMENT', 'local'),
                'server_time': datetime.datetime.now().isoformat(),
                'database_url': app.config['SQLALCHEMY_DATABASE_URI'].split('@')[1] if '@' in app.config['SQLALCHEMY_DATABASE_URI'] else 'hidden'
            }
        })
    except Exception as e:
        logger.error(f"Error in debug_worker: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

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

if __name__ == '__main__':
    # Only run the development server when running locally
    # Railway will use gunicorn to run the application
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
