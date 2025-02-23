from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:amNbFIoguiKkaUyFyISaRHkEWrXMOgBB@shuttle.proxy.rlwy.net:31198/railway')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coin_id = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
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
        portfolio_data[entry.coin_id]['sources'][entry.source] = entry.amount
        portfolio_data[entry.coin_id]['total_amount'] += entry.amount
    
    return portfolio_data

def update_history(total_value):
    current_time = int(time.time())
    last_update = PortfolioHistory.query.order_by(PortfolioHistory.timestamp.desc()).first()
    
    if not last_update or (current_time - last_update.timestamp) >= HISTORY_UPDATE_INTERVAL:
        history_entry = PortfolioHistory(
            timestamp=current_time,
            datetime=datetime.now().isoformat(),
            total_value=total_value
        )
        db.session.add(history_entry)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/edit')
def edit_portfolio():
    return render_template('index.html')

@app.route('/portfolio')
def get_portfolio():
    try:
        portfolio_data = get_portfolio_data()
        print("Portfolio data:", portfolio_data)  # Debug print
        
        # Get current prices from CoinGecko
        if portfolio_data:
            coin_ids = list(portfolio_data.keys())
            print("Coin IDs:", coin_ids)  # Debug print
            
            prices_url = f'https://api.coingecko.com/api/v3/simple/price?ids={",".join(coin_ids)}&vs_currencies=usd'
            response = requests.get(prices_url)
            prices = response.json()
            print("Price data:", prices)  # Debug print
            
            # Get coin metadata for images
            metadata_url = f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={",".join(coin_ids)}&order=market_cap_desc&per_page=250&page=1&sparkline=false'
            metadata_response = requests.get(metadata_url)
            metadata = {coin['id']: coin['image'] for coin in metadata_response.json()}
            print("Metadata:", metadata)  # Debug print
            
            total_value = 0
            for coin_id, data in portfolio_data.items():
                if coin_id in prices:
                    current_price = prices[coin_id]['usd']
                    data['price'] = current_price
                    data['image'] = metadata.get(coin_id, '')
                    
                    # Update price in database
                    entries = Portfolio.query.filter_by(coin_id=coin_id).all()
                    for entry in entries:
                        entry.last_price = current_price
                    db.session.commit()
                    
                    # Fetch historical prices for hourly, daily, and 7-day changes
                    historical_prices = {}  
                    for coin_id in coin_ids:
                        historical_url = f'https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=7'
                        historical_response = requests.get(historical_url)
                        if historical_response.ok:
                            historical_prices[coin_id] = historical_response.json()['prices']

                        # Calculate price changes if historical data is available
                        if coin_id in historical_prices:
                            historical_data = historical_prices[coin_id]
                            current_time = int(time.time() * 1000)  # Current time in milliseconds
                            
                            # Hourly change
                            one_hour_ago = current_time - 3600 * 1000
                            hourly_price = next((price for timestamp, price in historical_data if timestamp >= one_hour_ago), None)
                            if hourly_price:
                                data['hourly_change'] = ((current_price - hourly_price) / hourly_price) * 100
                            
                            # Daily change
                            one_day_ago = current_time - 86400 * 1000
                            daily_price = next((price for timestamp, price in historical_data if timestamp >= one_day_ago), None)
                            if daily_price:
                                data['daily_change'] = ((current_price - daily_price) / daily_price) * 100
                            
                            # 7-day change
                            seven_days_ago = current_time - 7 * 86400 * 1000
                            seven_day_price = next((price for timestamp, price in historical_data if timestamp >= seven_days_ago), None)
                            if seven_day_price:
                                data['seven_day_change'] = ((current_price - seven_day_price) / seven_day_price) * 100
                    
                    # Calculate total value for this coin
                    coin_value = data['total_amount'] * current_price
                    total_value += coin_value
                    data['total_value'] = coin_value
            
            print("Final portfolio data:", portfolio_data)  # Debug print
            print("Total value:", total_value)  # Debug print
            
            # Update history if needed
            update_history(total_value)
            
            return jsonify({
                'success': True,
                'data': portfolio_data,
                'total_value': total_value
            })
        else:
            return jsonify({
                'success': True,
                'data': {},
                'total_value': 0
            })
            
    except Exception as e:
        print("Error in get_portfolio:", str(e))  # Debug print
        return jsonify({'success': False, 'error': str(e)})

@app.route('/history')
def get_history():
    history = PortfolioHistory.query.order_by(PortfolioHistory.timestamp.asc()).all()
    history_data = [{'timestamp': h.timestamp, 'datetime': h.datetime, 'total_value': h.total_value} for h in history]
    return jsonify({'success': True, 'data': history_data})

@app.route('/add_coin', methods=['POST'])
def add_coin():
    try:
        data = request.get_json()
        coin_id = data.get('coin_id')
        source = data.get('source')
        amount = float(data.get('amount', 0))
        
        # Validate input
        if not coin_id or not source or amount <= 0:
            return jsonify({'success': False, 'error': 'Invalid input'})
        
        # Check if coin exists in CoinGecko
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd')
        if not response.ok or coin_id not in response.json():
            return jsonify({'success': False, 'error': 'Invalid coin ID'})
        
        current_price = response.json()[coin_id]['usd']
        
        # Add or update portfolio entry
        entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
        if entry:
            entry.amount = amount
            entry.last_price = current_price
        else:
            entry = Portfolio(coin_id=coin_id, source=source, amount=amount, last_price=current_price)
            db.session.add(entry)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/remove_source', methods=['POST'])
def remove_source():
    try:
        data = request.get_json()
        coin_id = data.get('coin_id')
        source = data.get('source')
        
        if not coin_id or not source:
            return jsonify({'success': False, 'error': 'Invalid input'})
        
        entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
            
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def create_tables():
    with app.app_context():
        db.create_all()

create_tables()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5016))
    host = '0.0.0.0'
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    app.run(host=host, port=port, debug=debug)
