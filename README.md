# Crypto Portfolio Tracker

A web application for tracking cryptocurrency portfolios with real-time price updates and historical value tracking.

## Features

- Real-time cryptocurrency price tracking via CoinGecko API
- Portfolio management with multiple locations per coin
- Historical portfolio value tracking
- TradingView charts integration
- Editable portfolio entries
- Responsive design
- Exposure map by asset and platform/location
- Scenario Lab: per-asset price shocks, proportional one-time contributions, and yield multipliers, with a fixed baseline and no changes to saved holdings

### Scenario Lab checks

Run the calculation tests with Node.js 18 or later:

```bash
node --test tests/scenario.test.cjs
```

Scenario contributions buy positions proportionally at baseline prices before the selected price shocks. Estimated monthly income uses scenario values multiplied by adjusted APY divided by 12; it does not model compounding, fees, or taxes. Reset uses the most recently loaded portfolio. Assumptions remain in memory only and are discarded on reload.

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

### Historical change summaries

The dashboard requests `/history/summary` on each portfolio refresh. Six bounded indexed queries select the nearest snapshots for 24 hours, 7 days, and 30 days, returning at most three comparison records. Snapshots more than 12 hours from their target, or invalid/zero comparison values, show as unavailable. Returns describe portfolio value changes, including deposits and withdrawals.

Range-filtered `/history` data loads only when the user requests or refreshes the chart (on either page), changes an already-loaded chart's range, or adds a history entry with the chart open. Scale and currency toggles redraw locally. Statistics extrema are calculated on unsampled records from the selected range. Stored timestamps retain their time component; existing naive server-time conventions are preserved. Startup creates the date index on existing databases (concurrently on PostgreSQL).

Run the summary checks without connecting to the application database:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_history_summary.py'
node --test tests/history-summary.test.cjs
```

### Portfolio History explorer

- `/history?range=90&max_points=600` filters dates in the database. Supported ranges are 7, 30, 90, 180, 365, 730 days and `all`; point limits are 32–1200. The UI requests 600 points (240 on iPhone Chrome). Small ranges keep every usable snapshot.
- Larger ranges stream through time buckets, retaining each bucket's endpoints and USD, BTC and adjusted-USD minima/maxima. This bounds response size while preserving peaks and drops, but it does not reproduce every movement. The server still scans records in the selected range.
- Gaps over three hours break lines; invalid values also break segments. Freshness uses the latest database timestamp, independently of the selected range. Null BTC values remain missing, not zero. All timestamp coordinates retain the existing server-time convention.
- The new additive `portfolio_cash_flows` table stores explicit USD deposits/withdrawals. Authenticated, CSRF-protected create/delete operations affect annotations only. UI save retries reuse a request ID to avoid duplicate entries. No historical flows are inferred or backfilled.
- Dashed event markers and the ledger list annotate flows. The optional adjusted USD line subtracts cumulative net recorded flows after the first selected snapshot. It is **not investment return or verified profit**; results depend on complete, correctly dated records and do not distinguish rewards or fees. Transfers between your own locations should not be recorded as external flows. Demo Mode scales display values only; annotation inputs always use actual USD.
- Responses include at most 500 annotations. If the range contains more, the UI warns and disables the adjusted line until a shorter range is chosen.

Offline checks (SQLite only; no production database access):

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_history*.py'
node --test tests/*.test.cjs
```
