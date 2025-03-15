from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)

# Version indicator
APP_VERSION = "1.2.0"
print(f"Starting Crypto Portfolio Tracker v{APP_VERSION}")

# Database configuration - simplified for Railway deployment
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Log which database we're using and environment variables
print(f"Connecting to database: {DATABASE_URL}")
print(f"Environment variables: {[key for key in os.environ.keys() if 'DATABASE' in key]}")

# For SQLite, ensure the database directory exists
if DATABASE_URL.startswith('sqlite:///'):
    db_path = DATABASE_URL.replace('sqlite:///', '')
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
    print(f"Using SQLite database at: {db_path}")

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PORT'] = os.environ.get('PORT', 5000)

db = SQLAlchemy(app)

# Models
class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coin_id = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    apy = db.Column(db.Float, nullable=True, default=0.0)  # Added APY field
    last_price = db.Column(db.Float)
    
    __table_args__ = (
        db.UniqueConstraint('coin_id', 'source', name='unique_coin_source'),
    )

class PortfolioHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.Integer, nullable=False)
    datetime = db.Column(db.String(50), nullable=False)
    total_value = db.Column(db.Float, nullable=False)

HISTORY_UPDATE_INTERVAL = 3600  # 1 hour in seconds

def get_portfolio_data():
    portfolio_data = {}
    entries = Portfolio.query.all()
    
    for entry in entries:
        if entry.coin_id not in portfolio_data:
            portfolio_data[entry.coin_id] = {
                'sources': {},
                'total_amount': 0,
                'price': entry.last_price or 0
            }
        
        portfolio_data[entry.coin_id]['sources'][entry.source] = {
            'amount': entry.amount,
            'apy': entry.apy or 0.0  # Include APY in the sources data
        }
        portfolio_data[entry.coin_id]['total_amount'] += entry.amount
    
    return portfolio_data

def update_history(total_value):
    current_time = int(time.time())
    last_history = PortfolioHistory.query.order_by(PortfolioHistory.timestamp.desc()).first()
    
    if not last_history or (current_time - last_history.timestamp) >= HISTORY_UPDATE_INTERVAL:
        new_history = PortfolioHistory(
            timestamp=current_time,
            datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            total_value=total_value
        )
        db.session.add(new_history)
        db.session.commit()

def coingecko_request(url, max_retries=2, timeout=5):
    retries = 0
    while retries <= max_retries:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            retries += 1
            if retries > max_retries:
                print(f"Failed after {max_retries} retries: {e}")
                return None
            time.sleep(1)  # Wait before retrying

@app.route('/')
def index():
    db_type = "PostgreSQL" if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite"
    return render_template('index.html', version=APP_VERSION, db_type=db_type)

@app.route('/edit_portfolio')
def edit_portfolio():
    db_type = "PostgreSQL" if "postgresql" in app.config['SQLALCHEMY_DATABASE_URI'] else "SQLite"
    return render_template('edit_portfolio.html', version=APP_VERSION, db_type=db_type)

@app.route('/portfolio')
def get_portfolio():
    try:
        portfolio_data = get_portfolio_data()
        
        if not portfolio_data:
            return jsonify({'success': True, 'data': {}, 'total_value': 0})
        
        # Get coin IDs
        coin_ids = list(portfolio_data.keys())
        
        # Fetch current prices from CoinGecko
        coins_data = {}
        if coin_ids:
            url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={','.join(coin_ids)}&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=1h,24h,7d"
            coins_data = coingecko_request(url) or []
        
        # Create a map of coin_id to price data
        price_data = {}
        for coin in coins_data:
            price_data[coin['id']] = {
                'price': coin['current_price'],
                'image': coin['image'],
                'hourly_change': coin.get('price_change_percentage_1h_in_currency', 0),
                'daily_change': coin.get('price_change_percentage_24h', 0),
                'seven_day_change': coin.get('price_change_percentage_7d_in_currency', 0)
            }
        
        # Update portfolio with price data
        total_value = 0
        for coin_id, details in portfolio_data.items():
            # Default values if coin not found in CoinGecko response
            price = 0
            image = ''
            hourly_change = 0
            daily_change = 0
            seven_day_change = 0
            
            # Update with actual data if available
            if coin_id in price_data:
                price = price_data[coin_id]['price']
                image = price_data[coin_id]['image']
                hourly_change = price_data[coin_id]['hourly_change']
                daily_change = price_data[coin_id]['daily_change']
                seven_day_change = price_data[coin_id]['seven_day_change']
                
                # Update last_price in database
                for entry in Portfolio.query.filter_by(coin_id=coin_id).all():
                    entry.last_price = price
                db.session.commit()
            
            # Calculate total value for this coin
            coin_value = details['total_amount'] * price
            total_value += coin_value
            
            # Update portfolio data with price and value
            portfolio_data[coin_id]['price'] = price
            portfolio_data[coin_id]['total_value'] = coin_value
            portfolio_data[coin_id]['image'] = image
            portfolio_data[coin_id]['hourly_change'] = hourly_change
            portfolio_data[coin_id]['daily_change'] = daily_change
            portfolio_data[coin_id]['seven_day_change'] = seven_day_change
            
            # Convert sources from dict with amount and apy to just amount for backward compatibility
            sources_dict = {}
            for source, source_data in details['sources'].items():
                sources_dict[source] = {
                    'amount': source_data['amount'],
                    'apy': source_data['apy']
                }
            
            portfolio_data[coin_id]['sources'] = sources_dict
        
        # Update history if needed
        update_history(total_value)
        
        return jsonify({
            'success': True,
            'data': portfolio_data,
            'total_value': total_value
        })
    
    except Exception as e:
        print(f"Error in get_portfolio: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/history')
def get_history():
    history = PortfolioHistory.query.order_by(PortfolioHistory.timestamp.asc()).all()
    history_data = [{'timestamp': h.timestamp, 'datetime': h.datetime, 'value': h.total_value} for h in history]
    return jsonify({'success': True, 'data': history_data})

@app.route('/api/add_coin', methods=['POST'])
def add_coin():
    try:
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        coin_id = data.get('coin_id', '').strip().lower()
        source = data.get('source', '').strip()
        amount = data.get('amount', 0)
        apy = data.get('apy', 0)  # Get APY from request
        
        # Validate inputs
        if not coin_id or not source:
            return jsonify({'success': False, 'error': 'Coin ID and source are required'})
        
        try:
            amount = float(amount)
            apy = float(apy)  # Convert APY to float
        except ValueError:
            return jsonify({'success': False, 'error': 'Amount and APY must be valid numbers'})
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than zero'})
        
        if apy < 0:
            return jsonify({'success': False, 'error': 'APY cannot be negative'})
        
        # Check if coin exists in CoinGecko
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false"
        coin_data = coingecko_request(url)
        
        if not coin_data:
            return jsonify({'success': False, 'error': f"Coin '{coin_id}' not found on CoinGecko"})
        
        # Check if entry already exists
        existing_entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
        
        if existing_entry:
            existing_entry.amount += amount
            existing_entry.apy = apy  # Update APY
        else:
            new_entry = Portfolio(coin_id=coin_id, source=source, amount=amount, apy=apy)
            db.session.add(new_entry)
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error in add_coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/coins')
def get_valid_coins():
    try:
        url = "https://api.coingecko.com/api/v3/coins/list"
        coins_data = coingecko_request(url)
        
        if not coins_data:
            return jsonify({'success': False, 'error': 'Failed to fetch coins list from CoinGecko'})
        
        return jsonify({'success': True, 'data': coins_data})
    
    except Exception as e:
        print(f"Error in get_valid_coins: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_coin', methods=['POST'])
def update_coin():
    try:
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        coin_id = data.get('coin_id', '').strip().lower()
        old_source = data.get('old_source', '').strip()
        new_source = data.get('new_source', '').strip()
        new_amount = data.get('new_amount')
        new_apy = data.get('new_apy')  # Get new APY from request
        
        # Validate inputs
        if not coin_id or not old_source:
            return jsonify({'success': False, 'error': 'Coin ID and old source are required'})
        
        # Find the entry to update
        entry = Portfolio.query.filter_by(coin_id=coin_id, source=old_source).first()
        
        if not entry:
            return jsonify({'success': False, 'error': f"Entry for {coin_id} at {old_source} not found"})
        
        # Update source if provided and different
        if new_source and new_source != old_source:
            # Check if there's already an entry with the new source
            existing_entry = Portfolio.query.filter_by(coin_id=coin_id, source=new_source).first()
            
            if existing_entry:
                return jsonify({'success': False, 'error': f"Entry for {coin_id} at {new_source} already exists"})
            
            entry.source = new_source
        
        # Update amount if provided
        if new_amount is not None:
            try:
                new_amount = float(new_amount)
                if new_amount <= 0:
                    return jsonify({'success': False, 'error': 'Amount must be greater than zero'})
                entry.amount = new_amount
            except ValueError:
                return jsonify({'success': False, 'error': 'Amount must be a valid number'})
        
        # Update APY if provided
        if new_apy is not None:
            try:
                new_apy = float(new_apy)
                if new_apy < 0:
                    return jsonify({'success': False, 'error': 'APY cannot be negative'})
                entry.apy = new_apy
            except ValueError:
                return jsonify({'success': False, 'error': 'APY must be a valid number'})
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error in update_coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_source', methods=['POST'])
def remove_source():
    try:
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        coin_id = data.get('coin_id', '').strip().lower()
        source = data.get('source', '').strip()
        
        # Validate inputs
        if not coin_id or not source:
            return jsonify({'success': False, 'error': 'Coin ID and source are required'})
        
        # Find the entry to remove
        entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
        
        if not entry:
            return jsonify({'success': False, 'error': f"Entry for {coin_id} at {source} not found"})
        
        db.session.delete(entry)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        print(f"Error in remove_source: {e}")
        return jsonify({'success': False, 'error': str(e)})

def create_tables():
    with app.app_context():
        db.create_all()

create_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5004))
    app.run(debug=True, host='0.0.0.0', port=port)
