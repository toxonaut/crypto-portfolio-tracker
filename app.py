from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import time
from datetime import datetime

app = Flask(__name__)

PORTFOLIO_FILE = 'portfolio.json'
HISTORY_FILE = 'portfolio_history.json'
HISTORY_UPDATE_INTERVAL = 3600  # 1 hour in seconds

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading portfolio: {str(e)}")
    return {}

def save_portfolio(portfolio_data):
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(portfolio_data, f, indent=4)
    except Exception as e:
        print(f"Error saving portfolio: {str(e)}")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading history: {str(e)}")
    return {'last_update': 0, 'data': []}

def save_history(history_data):
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history_data, f, indent=4)
    except Exception as e:
        print(f"Error saving history: {str(e)}")

def update_history(total_value):
    history = load_history()
    current_time = int(time.time())
    
    # Update if this is the first entry or if enough time has passed since last update
    if not history['data'] or (current_time - history['last_update']) >= HISTORY_UPDATE_INTERVAL:
        history['data'].append({
            'timestamp': current_time,
            'datetime': datetime.now().isoformat(),
            'total_value': total_value
        })
        history['last_update'] = current_time
        save_history(history)

# Initialize portfolio from file
portfolio = load_portfolio()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/edit')
def edit_portfolio():
    return render_template('edit_portfolio.html')

@app.route('/api/portfolio')
def get_portfolio():
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
            # Use last known price if update fails
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
    
    # Update historical data
    update_history(total_value)
    
    return jsonify({
        'portfolio': updated_portfolio,
        'total_value': total_value
    })

@app.route('/api/history')
def get_history():
    history = load_history()
    return jsonify(history['data'])

@app.route('/api/add_coin', methods=['POST'])
def add_coin():
    data = request.json
    coin_id = data.get('coin_id')
    amount = float(data.get('amount', 0))
    source = data.get('source', 'Default')
    
    # If coin already exists in portfolio, just update the source
    if coin_id in portfolio:
        portfolio[coin_id]['sources'][source] = amount
        portfolio[coin_id]['total_amount'] = sum(portfolio[coin_id]['sources'].values())
        save_portfolio(portfolio)
        return jsonify({'success': True})
    
    # For new coins, verify with CoinGecko
    try:
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd')
        price_data = response.json()
        
        if coin_id in price_data:
            current_price = price_data[coin_id]['usd']
            portfolio[coin_id] = {
                'sources': {source: amount},
                'total_amount': amount,
                'price': current_price
            }
            save_portfolio(portfolio)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Coin not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_source', methods=['POST'])
def remove_source():
    data = request.json
    coin_id = data.get('coin_id')
    source = data.get('source')
    
    if coin_id in portfolio and source in portfolio[coin_id]['sources']:
        del portfolio[coin_id]['sources'][source]
        
        # Remove coin if no sources left
        if not portfolio[coin_id]['sources']:
            del portfolio[coin_id]
            save_portfolio(portfolio)
            return jsonify({'success': True})
        
        # Update total amount
        portfolio[coin_id]['total_amount'] = sum(portfolio[coin_id]['sources'].values())
        save_portfolio(portfolio)
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Source or coin not found'})

if __name__ == '__main__':
    # Get port from environment variable or use default
    port = int(os.environ.get('PORT', 5000))
    # In production, host should be '0.0.0.0' to accept all incoming connections
    host = '0.0.0.0'
    # Debug mode should be off in production
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    app.run(host=host, port=port, debug=debug)
