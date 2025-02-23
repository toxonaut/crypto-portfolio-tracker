from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import os
import time
from datetime import datetime

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('postgres://', 'postgresql://', 1)
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
        new_history = PortfolioHistory(
            timestamp=current_time,
            datetime=datetime.now().isoformat(),
            total_value=total_value
        )
        db.session.add(new_history)
        db.session.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/edit')
def edit_portfolio():
    return render_template('edit_portfolio.html')

@app.route('/api/portfolio')
def get_portfolio():
    portfolio = get_portfolio_data()
    updated_portfolio = {}
    total_value = 0
    
    for coin_id, data in portfolio.items():
        try:
            response = requests.get(
                f'https://api.coingecko.com/api/v3/simple/price',
                params={
                    'ids': coin_id,
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true',
                    'include_1hr_change': 'true',
                    'include_7d_change': 'true'
                }
            )
            price_data = response.json()
            current_price = price_data[coin_id]['usd']
            
            # Update price in database
            entries = Portfolio.query.filter_by(coin_id=coin_id).all()
            for entry in entries:
                entry.last_price = current_price
            db.session.commit()
            
            value = data['total_amount'] * current_price
            total_value += value
            
            updated_portfolio[coin_id] = {
                'sources': data['sources'],
                'total_amount': data['total_amount'],
                'price': current_price,
                'value': value,
                'price_change_1h': price_data[coin_id].get('usd_1h_change', 0),
                'price_change_24h': price_data[coin_id].get('usd_24h_change', 0),
                'price_change_7d': price_data[coin_id].get('usd_7d_change', 0)
            }
        except Exception as e:
            print(f"Error updating {coin_id}: {str(e)}")
            value = data['total_amount'] * data.get('price', 0)
            total_value += value
            updated_portfolio[coin_id] = {
                'sources': data['sources'],
                'total_amount': data['total_amount'],
                'price': data.get('price', 0),
                'value': value,
                'price_change_1h': 0,
                'price_change_24h': 0,
                'price_change_7d': 0
            }
    
    update_history(total_value)
    
    return jsonify({
        'portfolio': updated_portfolio,
        'total_value': total_value
    })

@app.route('/api/history')
def get_history():
    history = PortfolioHistory.query.order_by(PortfolioHistory.timestamp.asc()).all()
    return jsonify([{
        'timestamp': h.timestamp,
        'datetime': h.datetime,
        'total_value': h.total_value
    } for h in history])

@app.route('/api/add_coin', methods=['POST'])
def add_coin():
    data = request.json
    coin_id = data.get('coin_id')
    amount = float(data.get('amount', 0))
    source = data.get('source', 'Default')
    
    try:
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd')
        price_data = response.json()
        
        if coin_id in price_data:
            current_price = price_data[coin_id]['usd']
            
            # Check if entry exists
            entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
            if entry:
                entry.amount = amount
                entry.last_price = current_price
            else:
                entry = Portfolio(
                    coin_id=coin_id,
                    source=source,
                    amount=amount,
                    last_price=current_price
                )
                db.session.add(entry)
            
            db.session.commit()
            return jsonify({'success': True})
            
        return jsonify({'success': False, 'error': 'Coin not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_source', methods=['POST'])
def remove_source():
    data = request.json
    coin_id = data.get('coin_id')
    source = data.get('source')
    
    try:
        entry = Portfolio.query.filter_by(coin_id=coin_id, source=source).first()
        if entry:
            db.session.delete(entry)
            db.session.commit()
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'Source not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def create_tables():
    with app.app_context():
        db.create_all()

create_tables()

def import_existing_data():
    try:
        if os.path.exists('portfolio.json'):
            with open('portfolio.json', 'r') as f:
                portfolio_data = json.load(f)
                
            for coin_id, data in portfolio_data.items():
                for source, amount in data['sources'].items():
                    entry = Portfolio(
                        coin_id=coin_id,
                        source=source,
                        amount=amount,
                        last_price=data.get('price', 0)
                    )
                    db.session.add(entry)
            
        if os.path.exists('portfolio_history.json'):
            with open('portfolio_history.json', 'r') as f:
                history_data = json.load(f)
                
            for entry in history_data.get('data', []):
                history_entry = PortfolioHistory(
                    timestamp=entry['timestamp'],
                    datetime=entry['datetime'],
                    total_value=entry['total_value']
                )
                db.session.add(history_entry)
        
        db.session.commit()
    except Exception as e:
        print(f"Error importing existing data: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5016))
    host = '0.0.0.0'
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    # Import existing data if running for the first time
    with app.app_context():
        if not Portfolio.query.first():
            import_existing_data()
    
    app.run(host=host, port=port, debug=debug)
