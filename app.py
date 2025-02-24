from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
elif DATABASE_URL.startswith("railway://"):
    DATABASE_URL = DATABASE_URL.replace("railway://", "postgresql://", 1)
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

def coingecko_request(url, max_retries=2, timeout=5):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 429:  # Too Many Requests
                if attempt < max_retries - 1:
                    time.sleep(60)  # Wait 60 seconds before retrying
                    continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2)  # Wait 2 seconds before retrying other errors
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/edit')
def edit_portfolio():
    return render_template('edit.html')

@app.route('/portfolio')
def get_portfolio():
    try:
        print("Starting portfolio data retrieval...")
        
        # Log database connection info
        print("Database URL:", app.config['SQLALCHEMY_DATABASE_URI'])
        
        # Get all entries from database
        entries = Portfolio.query.all()
        print(f"Found {len(entries)} entries in database")
        for entry in entries:
            print(f"Entry: coin_id={entry.coin_id}, source={entry.source}, amount={entry.amount}")
        
        portfolio_data = get_portfolio_data()
        print("Portfolio data:", portfolio_data)
        
        # Get current prices from CoinGecko
        if portfolio_data:
            coin_ids = list(portfolio_data.keys())
            print("Coin IDs:", coin_ids)
            
            # Combine price and metadata request into one
            markets_url = f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={",".join(coin_ids)}&order=market_cap_desc&per_page=250&page=1&sparkline=false&price_change_percentage=1h,24h,7d'
            print(f"Calling CoinGecko API: {markets_url}")
            
            response = coingecko_request(markets_url, timeout=10)
            if response and response.ok:
                market_data = response.json()
                print("Market data:", market_data)
                
                total_value = 0
                for coin in market_data:
                    coin_id = coin['id']
                    if coin_id in portfolio_data:
                        data = portfolio_data[coin_id]
                        current_price = coin['current_price']
                        data['price'] = current_price
                        data['image'] = coin['image']
                        data['hourly_change'] = coin.get('price_change_percentage_1h_in_currency')
                        data['daily_change'] = coin.get('price_change_percentage_24h')
                        data['seven_day_change'] = coin.get('price_change_percentage_7d_in_currency')
                        
                        # Update price in database
                        entries = Portfolio.query.filter_by(coin_id=coin_id).all()
                        for entry in entries:
                            entry.last_price = current_price
                        
                        # Calculate total value for this coin
                        coin_value = data['total_amount'] * current_price
                        total_value += coin_value
                        data['total_value'] = coin_value
                
                try:
                    db.session.commit()
                except Exception as e:
                    print(f"Error updating prices in database: {str(e)}")
                    db.session.rollback()
                
                print("Final portfolio data:", portfolio_data)
                print("Total value:", total_value)
                
                # Update history if needed
                try:
                    update_history(total_value)
                except Exception as e:
                    print(f"Error updating history: {str(e)}")
                
                return jsonify({
                    'success': True,
                    'data': portfolio_data,
                    'total_value': total_value
                })
            else:
                error_msg = f"Failed to fetch market data: {response.status_code if response else 'No response'}"
                print(error_msg)
                return jsonify({
                    'success': False,
                    'error': error_msg
                })
        else:
            print("No portfolio data found")
            return jsonify({
                'success': True,
                'data': {},
                'total_value': 0
            })
            
    except Exception as e:
        print(f"Error in get_portfolio: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/history')
def get_history():
    history = PortfolioHistory.query.order_by(PortfolioHistory.timestamp.asc()).all()
    history_data = [{'timestamp': h.timestamp, 'datetime': h.datetime, 'total_value': h.total_value} for h in history]
    return jsonify({'success': True, 'data': history_data})

@app.route('/api/add_coin', methods=['POST'])
def add_coin():
    try:
        data = request.get_json()
        coin_id = data.get('coin_id')
        source = data.get('source')
        amount = float(data.get('amount'))
        
        print(f"Adding coin: {coin_id}, source: {source}, amount: {amount}")
        
        # Verify the coin exists in CoinGecko
        url = f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd'
        print(f"Calling CoinGecko API: {url}")
        
        try:
            response = coingecko_request(url)
            if not response:
                return jsonify({'success': False, 'error': 'Failed to fetch price data from CoinGecko'})
            
            print(f"CoinGecko API response status: {response.status_code}")
            print(f"CoinGecko API response body: {response.text}")
            
            response_data = response.json()
            if coin_id not in response_data:
                return jsonify({'success': False, 'error': f'Invalid coin ID: {coin_id}. Make sure to use the CoinGecko ID (e.g., "bitcoin" for Bitcoin)'})
            
            price = response_data[coin_id]['usd']
            print(f"Got price for {coin_id}: ${price}")
            
            # Check if entry already exists
            existing_entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
            if existing_entry:
                existing_entry.amount = amount
                existing_entry.last_price = price
            else:
                new_entry = Portfolio(coin_id=coin_id, source=source, amount=amount, last_price=price)
                db.session.add(new_entry)
            
            db.session.commit()
            return jsonify({'success': True})
            
        except requests.exceptions.RequestException as e:
            print(f"CoinGecko API error: {str(e)}")
            return jsonify({'success': False, 'error': 'Failed to fetch data from CoinGecko API. Please try again later.'})
            
    except Exception as e:
        print(f"Error in add_coin: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/valid_coins')
def get_valid_coins():
    try:
        response = coingecko_request('https://api.coingecko.com/api/v3/coins/list?include_platform=false')
        if response and response.ok:
            coins = response.json()
            return jsonify({
                'success': True,
                'coins': [{'id': coin['id'], 'symbol': coin['symbol'], 'name': coin['name']} for coin in coins]
            })
        return jsonify({'success': False, 'error': 'Failed to fetch coin list'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_coin', methods=['POST'])
def update_coin():
    try:
        data = request.get_json()
        coin_id = data.get('coin_id')
        old_source = data.get('old_source')
        new_source = data.get('new_source')
        new_amount = data.get('new_amount')

        if not all([coin_id, old_source, new_source, new_amount]):
            return jsonify({'success': False, 'error': 'Missing required fields'})

        try:
            new_amount = float(new_amount)
            if new_amount <= 0:
                return jsonify({'success': False, 'error': 'Amount must be greater than 0'})
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid amount'})

        # Get the current entry
        entry = Portfolio.query.filter_by(coin_id=coin_id, source=old_source).first()
        if not entry:
            return jsonify({'success': False, 'error': 'Entry not found'})

        # If source is being changed, check if new source already exists
        if old_source != new_source:
            existing_entry = Portfolio.query.filter_by(coin_id=coin_id, source=new_source).first()
            if existing_entry:
                return jsonify({'success': False, 'error': f'Source {new_source} already exists for {coin_id}'})

        # Update the entry
        entry.source = new_source
        entry.amount = new_amount
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error updating coin: {str(e)}")
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
    port = int(os.environ.get('PORT', 5018))
    app.run(host='0.0.0.0', port=port, debug=True)
