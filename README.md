# Crypto Portfolio Tracker

A web application for tracking cryptocurrency portfolios with real-time price updates and historical value tracking.

## Features

- Real-time cryptocurrency price tracking via CoinGecko API
- Portfolio management with multiple locations per coin
- Historical portfolio value tracking
- TradingView charts integration
- Editable portfolio entries
- Responsive design

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

## Deployment Options

### 1. Railway.app (Recommended)

1. Create a Railway account at https://railway.app
2. Install Railway CLI:
```bash
npm i -g @railway/cli
```

3. Login and deploy:
```bash
railway login
railway init
railway up
```

### 2. Render.com

1. Create a Render account at https://render.com
2. Create a new Web Service
3. Connect your GitHub repository
4. Use the following build settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`

### 3. DigitalOcean App Platform

1. Create a DigitalOcean account
2. Create a new App
3. Connect your GitHub repository
4. Select Python environment
5. Deploy

## Environment Variables

The application uses the following environment variables:

- `PORT` (optional): Port number for the application
- `FLASK_ENV` (optional): Set to 'production' for production environment

## Data Storage

The application currently uses JSON files for data storage:
- `portfolio.json`: Stores portfolio data
- `portfolio_history.json`: Stores historical portfolio values

For production deployment, consider migrating to a proper database system.
