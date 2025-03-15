from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import json
import datetime
import logging

app = Flask(__name__)

# Version indicator
APP_VERSION = "1.3.0"
print(f"Starting Crypto Portfolio Tracker v{APP_VERSION}")

# Database configuration - separate paths for local and Railway environments
is_railway = 'RAILWAY_ENVIRONMENT' in os.environ
if is_railway:
    # On Railway, use a path in the persistent filesystem
    SQLITE_PATH = '/data/railway_portfolio.db'
    print(f"Running on Railway - using database at {SQLITE_PATH}")
else:
    # Locally, use the regular path
    SQLITE_PATH = 'portfolio.db'
    print(f"Running locally - using database at {SQLITE_PATH}")

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
    
    # Enrich portfolio data with prices
    for item in portfolio_data:
        coin_id = item['coin_id']
        if coin_id in prices:
            price_data = prices[coin_id]
            item['price'] = price_data.get('usd', 0)
            item['price_change_1h'] = price_data.get('usd_1h_change', 0)
            item['price_change_24h'] = price_data.get('usd_24h_change', 0)
            item['price_change_7d'] = price_data.get('usd_7d_change', 0)
            item['value'] = item['amount'] * item['price']
            
            # Calculate daily yield based on APY
            if 'apy' in item and item['apy'] > 0:
                daily_rate = (1 + item['apy'] / 100) ** (1/365) - 1
                item['daily_yield'] = item['value'] * daily_rate
            else:
                item['daily_yield'] = 0
        else:
            item['price'] = 0
            item['price_change_1h'] = 0
            item['price_change_24h'] = 0
            item['price_change_7d'] = 0
            item['value'] = 0
            item['daily_yield'] = 0
    
    return jsonify(portfolio_data)

@app.route('/history')
def get_history():
    history_data = get_history_data()
    return jsonify(history_data)

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
        db.create_all()
    app.run(debug=True)
