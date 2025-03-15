from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import json
import datetime
import logging
import time

app = Flask(__name__)

# Version indicator
APP_VERSION = "1.3.0"
print(f"Starting Crypto Portfolio Tracker v{APP_VERSION}")

# Database configuration - separate paths for local and Railway environments
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ
print(f"Is Railway environment: {is_railway}")
print(f"RAILWAY_PRESERVE_DB: {os.environ.get('RAILWAY_PRESERVE_DB')}")
print(f"Testing database preservation - deployment timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if is_railway:
    # On Railway, use a path in the persistent storage volume
    SQLITE_PATH = '/data/railway_portfolio.db'
    print(f"Running on Railway - using database at {SQLITE_PATH}")
    
    # Make sure the directory exists
    os.makedirs('/data', exist_ok=True)
    
    # Check for marker file that indicates the database has user data
    MARKER_FILE = '/data/db_has_data.marker'
    if os.path.exists(MARKER_FILE):
        print(f"Found marker file at {MARKER_FILE} - database has user data")
        os.environ['RAILWAY_PRESERVE_DB'] = 'true'
        print("Set RAILWAY_PRESERVE_DB=true to preserve database")
    
    # Set a flag to prevent database initialization on Railway
    # Only initialize if the database doesn't exist AND we're not preserving it
    preserve_db = os.environ.get('RAILWAY_PRESERVE_DB') == 'true'
    INITIALIZE_DB = not preserve_db
    
    print(f"RAILWAY_PRESERVE_DB: {preserve_db}, INITIALIZE_DB: {INITIALIZE_DB}")
    
    # Check if we need to initialize the database
    if not os.path.exists(SQLITE_PATH):
        print(f"Railway database does not exist yet at {SQLITE_PATH} - it will be created")
        # Even if we're preserving the DB, we need to create it if it doesn't exist
        INITIALIZE_DB = True
    else:
        print(f"Railway database exists at {SQLITE_PATH} with size {os.path.getsize(SQLITE_PATH)} bytes")
        if preserve_db:
            print("Preserving existing database - will not initialize")
            INITIALIZE_DB = False
else:
    # Locally, use the regular path
    SQLITE_PATH = 'portfolio.db'
    print(f"Running locally - using database at {SQLITE_PATH}")
    INITIALIZE_DB = True

# Database URL configuration
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{SQLITE_PATH}')
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

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PORT'] = os.environ.get('PORT', 5000)

db = SQLAlchemy(app)

class Portfolio(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    total_value = db.Column(db.Float, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d'),
            'total_value': self.total_value
        }

def get_portfolio_data():
    portfolio = Portfolio.query.all()
    return [item.to_dict() for item in portfolio]

def get_history_data():
    history = PortfolioHistory.query.order_by(PortfolioHistory.date).all()
    return [item.to_dict() for item in history]

def get_coin_prices(coin_ids):
    if not coin_ids:
        return {}
    
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coin_ids)}&vs_currencies=usd&include_24hr_change=true&include_1h_change=true&include_7d_change=true"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching prices: {response.status_code}")
            return {}
    except Exception as e:
        print(f"Exception fetching prices: {e}")
        return {}

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
            # Default image for the coin
            image_url = f"https://assets.coingecko.com/coins/images/1/small/{coin_id}.png"
            
            # Get price data if available
            price = 0
            hourly_change = None
            daily_change = None
            seven_day_change = None
            
            if coin_id in prices:
                price_data = prices[coin_id]
                price = price_data.get('usd', 0)
                hourly_change = price_data.get('usd_1h_change')
                daily_change = price_data.get('usd_24h_change')
                seven_day_change = price_data.get('usd_7d_change')
                
                # Try to get image URL
                if 'image' in price_data:
                    image_url = price_data['image']
            
            grouped_data[coin_id] = {
                'price': price,
                'image': image_url,
                'hourly_change': hourly_change,
                'daily_change': daily_change,
                'seven_day_change': seven_day_change,
                'total_amount': 0,  # Initialize total amount
                'total_value': 0,   # Initialize total value
                'monthly_yield': 0,  # Initialize monthly yield
                'sources': {}
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
        price = coin_data['price']
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
            'total_value': item['total_value']
        })
    
    return jsonify({
        'success': True,
        'data': formatted_data
    })

@app.route('/api/add_coin', methods=['POST'])
def add_coin_api():
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

@app.route('/add_coin', methods=['POST'])
def add_coin():
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

@app.route('/update_coin/<int:coin_id>', methods=['PUT'])
def update_coin(coin_id):
    data = request.json
    entry = Portfolio.query.get(coin_id)
    
    if not entry:
        return jsonify({'success': False, 'error': 'Entry not found'})
    
    entry.amount = float(data['amount'])
    if 'apy' in data:
        entry.apy = float(data['apy'])
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/update_coin', methods=['POST'])
def update_coin_api():
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

@app.route('/api/remove_source', methods=['POST'])
def delete_coin_api():
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

@app.route('/delete_coin/<int:coin_id>', methods=['DELETE'])
def delete_coin(coin_id):
    entry = Portfolio.query.get(coin_id)
    
    if not entry:
        return jsonify({'success': False, 'error': 'Entry not found'})
    
    db.session.delete(entry)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/add_history', methods=['POST'])
def add_history():
    data = request.json
    
    new_entry = PortfolioHistory(
        date=datetime.datetime.now(),
        total_value=float(data['total_value'])
    )
    
    db.session.add(new_entry)
    db.session.commit()
    
    return jsonify({'success': True, 'id': new_entry.id})

@app.route('/debug_db')
def debug_db():
    """Debug endpoint to check database contents directly"""
    try:
        # Check if the database file exists
        if DATABASE_URL.startswith('sqlite:///'):
            db_path = DATABASE_URL.replace('sqlite:///', '')
            file_exists = os.path.exists(db_path)
            file_size = os.path.getsize(db_path) if file_exists else 0
        else:
            file_exists = True  # Assume PostgreSQL is available
            file_size = 0  # Not applicable for PostgreSQL
        
        # Get portfolio data
        portfolio = Portfolio.query.all()
        portfolio_data = [item.to_dict() for item in portfolio]
        
        # Get history data
        history = PortfolioHistory.query.all()
        history_data = [item.to_dict() for item in history]
        
        # List tables in the database
        tables = []
        if DATABASE_URL.startswith('sqlite:///'):
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
        
        # Return debug information
        return jsonify({
            'database_info': {
                'url': DATABASE_URL,
                'file_exists': file_exists,
                'file_size': file_size,
                'tables': tables
            },
            'portfolio_count': len(portfolio_data),
            'portfolio_data': portfolio_data,
            'history_count': len(history_data),
            'history_data': history_data,
            'app_version': APP_VERSION
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'database_url': DATABASE_URL,
            'app_version': APP_VERSION
        })

if __name__ == '__main__':
    with app.app_context():
        if INITIALIZE_DB:
            db.create_all()
    app.run(debug=True)
