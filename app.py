from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import datetime
import json
import logging
import requests
import time
from dotenv import load_dotenv

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

db = SQLAlchemy(app)

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()

class Portfolio(db.Model):
    __tablename__ = 'portfolio'  # Explicitly set lowercase table name
    id = db.Column(db.Integer, primary_key=True)
    coin_id = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    apy = db.Column(db.Float, default=0.0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'coin_id': self.coin_id,
            'source': self.source,
            'amount': self.amount,
            'apy': self.apy
        }

class PortfolioHistory(db.Model):
    __tablename__ = 'portfolio_history'  # Explicitly set lowercase table name
    id = db.Column(db.Integer, primary_key=True)
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
                    coin_data[coin['id']] = {
                        'usd': coin['current_price'],
                        'usd_1h_change': coin['price_change_percentage_1h_in_currency'],
                        'usd_24h_change': coin['price_change_percentage_24h_in_currency'],
                        'usd_7d_change': coin['price_change_percentage_7d_in_currency'],
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
                'apy': apy
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
                grouped_data[coin_id]['image'] = price_data.get('image', "https://assets.coingecko.com/coins/images/1/small/bitcoin.png")
            
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

if 1==2:  # Disable request-based history checking to rely solely on worker process
    @app.before_request
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
def index():
    db_type = "PostgreSQL" if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite"
    return render_template('index.html', version="1.3.0", db_type=db_type)

@app.route('/edit_portfolio')
def edit_portfolio():
    db_type = "PostgreSQL" if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite"
    return render_template('edit_portfolio.html', version="1.3.0", db_type=db_type)

@app.route('/portfolio')
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
            'apy': apy
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
def add_coin_api():
    try:
        data = request.json
        
        new_entry = Portfolio(
            coin_id=data['coin_id'],
            source=data['source'],
            amount=float(data['amount']),
            apy=float(data.get('apy', 0))
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error adding coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_coin', methods=['POST'])
def add_coin():
    try:
        data = request.json
        
        new_entry = Portfolio(
            coin_id=data['coin_id'],
            source=data['source'],
            amount=float(data['amount']),
            apy=float(data.get('apy', 0))
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({'success': True, 'id': new_entry.id})
    except Exception as e:
        logger.error(f"Error adding coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/update_coin/<int:coin_id>', methods=['PUT'])
def update_coin(coin_id):
    try:
        data = request.json
        entry = Portfolio.query.get(coin_id)
        
        if not entry:
            return jsonify({'success': False, 'error': 'Entry not found'})
        
        entry.amount = float(data['amount'])
        if 'apy' in data:
            entry.apy = float(data['apy'])
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_coin', methods=['POST'])
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
        
        # Update the entry
        entry.source = data['new_source']
        entry.amount = float(data['new_amount'])
        
        # Check if new_apy is explicitly defined (including 0 values)
        if 'new_apy' in data:
            entry.apy = float(data['new_apy'])
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_source', methods=['POST'])
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
def add_history():
    try:
        data = request.get_json()
        logger.info(f"Received add_history request with data: {data}")
        
        if not data or 'total_value' not in data:
            logger.error("Invalid data received in add_history request")
            return jsonify({'success': False, 'error': 'Invalid data'}), 400
        
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
                btc_value = float(data['total_value']) / bitcoin_price
                
            actual_btc = actual_bitcoin_amount
                
            logger.info(f"Calculated Bitcoin price: {bitcoin_price}, BTC value: {btc_value}, Actual BTC: {actual_btc}")
        else:
            logger.info(f"Using provided BTC value: {btc_value}, Actual BTC: {actual_btc}")
        
        new_entry = PortfolioHistory(
            date=datetime.datetime.now(),
            total_value=float(data['total_value']),
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

if __name__ == '__main__':
    # Only run the development server when running locally
    # Railway will use gunicorn to run the application
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
