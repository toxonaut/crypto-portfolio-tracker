from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import json
import datetime
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Version indicator
APP_VERSION = "1.3.0"
print(f"Starting Crypto Portfolio Tracker v{APP_VERSION}")

# Database configuration - use Railway PostgreSQL for both local and Railway environments
# The DATABASE_URL environment variable is automatically set by Railway in production
# For local development, you'll need to set this environment variable to your Railway PostgreSQL URL
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@containers-us-west-141.railway.app:7617/railway')

# If the URL starts with postgres://, change it to postgresql:// (SQLAlchemy requirement)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

print(f"Using database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'PostgreSQL'}")

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PORT'] = os.environ.get('PORT', 5000)

db = SQLAlchemy(app)

# Create the database tables if they don't exist
with app.app_context():
    db.create_all()

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
    try:
        portfolio = Portfolio.query.all()
        return [item.to_dict() for item in portfolio]
    except Exception as e:
        logging.error(f"Error fetching portfolio data: {e}")
        return []

def get_history_data():
    try:
        history = PortfolioHistory.query.order_by(PortfolioHistory.date).all()
        return [item.to_dict() for item in history]
    except Exception as e:
        logging.error(f"Error fetching history data: {e}")
        return []

def get_coin_prices(coin_ids):
    if not coin_ids:
        return {}
    
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={','.join(coin_ids)}&vs_currencies=usd&include_24hr_change=true&include_1h_change=true&include_7d_change=true"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Error fetching prices: {response.status_code}")
            return {}
    except Exception as e:
        logging.error(f"Exception fetching prices: {e}")
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
        logging.error(f"Error adding coin: {e}")
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
        logging.error(f"Error adding coin: {e}")
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
        logging.error(f"Error updating coin: {e}")
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
        logging.error(f"Error updating coin: {e}")
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
        logging.error(f"Error deleting coin: {e}")
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
        logging.error(f"Error deleting coin: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_history', methods=['POST'])
def add_history():
    try:
        data = request.json
        
        new_entry = PortfolioHistory(
            date=datetime.datetime.now(),
            total_value=float(data['total_value'])
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({'success': True, 'id': new_entry.id})
    except Exception as e:
        logging.error(f"Error adding history: {e}")
        return jsonify({'success': False, 'error': str(e)})

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
        logging.error(f"Error debugging database: {e}")
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
        logging.error(f"Error initializing Bitcoin data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)
