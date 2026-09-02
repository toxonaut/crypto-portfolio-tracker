# Crypto Portfolio Tracker

A web application for tracking an API-backed and manually administered portfolio with real-time price updates and historical value tracking.

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

Scenario Lab uses New Portfolio Editor positions. Lowercase-`x` stock tokens share one `xStocks` price-change control while their signed values and origin-specific APYs remain separate in the calculation. Contributions buy positive positions proportionally at baseline prices before the selected price shocks. Estimated monthly income uses scenario values multiplied by adjusted APY divided by 12; it does not model compounding, fees, or taxes. Reset uses the most recently loaded portfolio. Assumptions remain in memory only and are discarded on reload.

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

Portfolio entries, history, composition snapshots, cash-flow annotations, and worker health are stored in PostgreSQL in production. The retired `portfolio` and `portfolio_history` tables remain read-only during the rollback window.

### Historical change summaries

The New Portfolio dashboard requests `/new-portfolio/history/summary` on each refresh. Six bounded indexed queries select the signed-in user's nearest snapshots for 24 hours, 7 days, and 30 days, returning at most three comparison records. Snapshots more than 12 hours from their target, or invalid/zero comparison values, show as unavailable. Returns describe portfolio value changes, including deposits and withdrawals.

Range-filtered `/new-portfolio/history` data loads only when the user requests or refreshes the chart (on either page), changes an already-loaded chart's range, or adds a history entry with the chart open. Scale and currency toggles redraw locally. Statistics extrema are calculated on unsampled New Portfolio records from the selected range. Stored timestamps retain their time component; existing naive server-time conventions are preserved.

Run the summary checks without connecting to the application database:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_history_summary.py'
```

### Portfolio History explorer

- `/new-portfolio/history?range=90&max_points=600` filters the signed-in user's New Portfolio snapshots. Supported ranges are 7, 30, 90, 180, 365, 730 days and `all`; point limits are 32–1200. The UI requests 600 points (240 on iPhone Chrome). Small ranges keep every usable snapshot.
- Larger ranges stream through time buckets, retaining each bucket's endpoints and USD, BTC and adjusted-USD minima/maxima. This bounds response size while preserving peaks and drops, but it does not reproduce every movement. The server still scans records in the selected range.
- Gaps over three hours are flagged, while straight lines connect the last available point before a gap to the first one after it. These connections do not imply observations during the gap. Freshness uses the latest database timestamp, independently of the selected range. Null BTC values remain missing, not zero; the chart connects the surrounding available BTC points. All timestamp coordinates retain the existing server-time convention.
- The additive, per-user `new_portfolio_cash_flows` table stores explicit USD deposits/withdrawals for New Portfolio history. Authenticated, CSRF-protected create/delete operations affect annotations only. UI save retries reuse a request ID to avoid duplicate entries. On upgrade, legacy annotations are copied only when the database has exactly one user and the new ledger is empty; otherwise they remain untouched because ownership is ambiguous.
- Dashed event markers and the ledger list annotate flows. The optional adjusted USD line subtracts cumulative net recorded flows after the first selected snapshot. It is **not investment return or verified profit**; results depend on complete, correctly dated records and do not distinguish rewards or fees. Transfers between your own locations should not be recorded as external flows. Demo Mode scales display values only; annotation inputs always use actual USD.
- Responses include at most 500 annotations. If the range contains more, the UI warns and disables the adjusted line until a shorter range is chosen.

Offline checks (SQLite only; no production database access):

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_history*.py'
node --test tests/*.test.cjs
```

### Automatic snapshots without session cookies

The worker sends a dedicated `X-Worker-Key` to **POST `/worker_api/new-portfolio-snapshot`**. It no longer reads browser session cookies or needs database credentials. Configure a matching `WORKER_KEY` of at least 32 characters and `HISTORY_INTERVAL_SECONDS` (default 3600) on the web and worker services. Never use the web session `SECRET_KEY` as the worker credential.

The authenticated server reads Kraken balances and ticker prices plus required manual-entry and Bitcoin reference quotes. It rejects incomplete or stale manual pricing and computes USD/BTC values itself. Negative positions reduce net portfolio value, matching the dashboard. No cached or partial valuation is silently written. Manual Add History uses the same New Portfolio valuation and composition transaction; browser-provided and demo values are ignored.

A unique UTC schedule slot and an atomic database receipt prevent duplicates across retries, restarts and simultaneous workers. Retries use delays of 5, 10 and 20 seconds, bounded HTTP timeouts, and the same slot. Redirects and rejected credentials fail closed. After an unsuccessful cycle, the worker tries again after a minute. Successful cycles align to the next schedule boundary; shutdown signals stop waits cleanly. Missed slots are not backfilled with fabricated valuations.

The unique `(user_id, slot)` constraint makes hourly retries idempotent. `new_portfolio_worker_health` stores the last automatic attempt, success, and sanitized error shown by `/new-portfolio/worker_status`; manual snapshots do not alter automatic health. The dashboard warns after two missed intervals or when no automatic success exists. Wrong credentials cannot update health. No external email/SMS notifications are enabled.

One-time Railway rollout:

1. Authenticate the Railway CLI with `railway login`.
2. Run `python3 scripts/configure_railway_worker.py`. It reuses a suitable existing worker credential or generates one, sends it via stdin (not command-line arguments), stages matching configuration on both services, and verifies equality without printing secrets. It does not trigger deployments.
3. Push the tested commit to the connected GitHub branch and verify both deployments.
4. Verify a successful `/worker_api/new-portfolio-snapshot` result and the dashboard's latest automatic success. Existing `SESSION_COOKIE` variables are ignored and can be removed after the successful rollout; they never need refreshing again.

To rotate credentials, stage the same new value on both services and deploy both. Until configured, the worker exits with an error and the API rejects snapshot requests. Do not deploy the replacement worker before staging its key.

Checks (temporary SQLite database and mocked providers; no production writes):

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/*.test.cjs
```


### Price-data quality

The dashboard requests only held CoinGecko IDs (plus Bitcoin for conversion), with a 60-second process-local cache to reduce provider traffic. Each asset shows its source, provider timestamp, and current/cached/stale/missing status. Crypto quotes older than 15 minutes or quotes retained after a failed refresh are labeled stale. Last-known crypto prices are retained for at most 24 hours; the cache resets on a web-process restart. CHF uses dated daily Frankfurter reference rates, allowing up to seven calendar days for weekends and holidays. Missing percentage changes display a dash, never a fabricated 0%.

If a nonzero holding lacks a usable quote, portfolio totals and yield are unavailable rather than silently partial. Stale quotes may support an explicitly labeled estimate, but historical comparisons are withheld until all required quotes recover. Exposure and scenario views retain their incomplete-price warnings. Manual and automatic history writes use fresh server-side quotes, never this fallback cache.

Exposure Map uses the New Portfolio Editor positions and signed net values: negative balances reduce the asset, origin, and overall total. Assets whose symbols end in `x` are combined into one `xStocks` exposure. Negative totals appear left of zero in red. Shares use positive net portfolio value (and may exceed 100%); shares are unavailable if net value is zero or negative. Missing-price positions remain explicitly excluded.


### Portfolio composition history

Each automatic New Portfolio history snapshot also stores an immutable breakdown of asset, origin, signed quantity, USD unit price, and USD value in `new_portfolio_compositions`. Lowercase-`x` stock tokens are combined by origin as `xStocks`, with no artificial shared quantity or unit price. The total and composition records commit together, so failed pricing/storage and worker retries cannot create an incomplete or duplicate composition. Later API balance changes, edits, or removal of a position do not rewrite past snapshots. Existing legacy composition records remain stored but are not mixed into the New Portfolio chart, and no older New Portfolio composition is fabricated or backfilled.

The Composition History panel on Overview and Statistics loads only when requested. Select asset or platform grouping and USD or net allocation percentage, then inspect a snapshot's positions. Responses contain at most 200 snapshots, with an Older snapshots button for earlier pages. Load latest returns to the newest page. Negative balances remain deductions, shares may exceed 100%, and shares are unavailable when the net total is not positive. Demo Mode scales recorded quantities and USD position values, without changing unit prices or percentages. Snapshots record holdings at collection time, not every intervening trade; allocation changes combine holdings and market-price changes and are not return attribution.


Scenario Lab uses signed position values. Negative balances reduce the baseline, respond to the same asset price shock as positive balances, and generate negative income when they carry a positive APY. Contributions are allocated proportionally across gross positive holdings only, so a small or negative net portfolio cannot amplify a contribution and liabilities are never increased. Scenarios remain available for zero or negative net portfolios when valid priced positions exist.

### New Portfolio Editor

`/experimental-portfolio` is the login-protected New Portfolio Editor linked from the top navigation. It combines read-only Kraken positions with per-user manual entries stored in `new_portfolio_entry`. Manual rows contain a CoinGecko ID, origin/location, signed amount, and APY and can be added, edited inline, and removed. Kraken rows remain read-only because their origin, balance, and yield come from the API.

The browser receives Kraken positions and calculated values but never API credentials or request signatures. The server calls Kraken Spot REST `POST /0/private/Balance` with the private key; Kraken's public `AssetPairs` and `Ticker` endpoints supply USD prices. Tokenized stocks use Kraken's separate `tokenized_asset` asset class so holdings such as AAPLx receive their xStocks/USD ticker price. When Kraken reports an Earn balance-code suffix, the editor also reads `Earn/Allocations` and `Earn/Strategies`. It displays a midpoint APR estimate weighted by the Earn amount and divided across the consolidated Spot + Earn balance, preventing the Earn rate from being applied to non-Earn units. Earn metadata failure never blocks balances and is shown as unavailable. Balance responses cache for 30 seconds and asset-pair metadata for one hour. The Refresh button explicitly bypasses the balance cache.

Create `.kraken_credentials.txt` beside `app.py` with `KRAKEN_API_KEY=...` and `KRAKEN_PRIVATE_KEY=...`, or set the same environment variables. The local file is Git-ignored and should have owner-only permissions. The API key needs only Kraken's **Funds permissions – Query** permission; trading and withdrawal permissions are unnecessary and should remain disabled. Private keys are used solely to generate the HMAC-SHA512 `API-Sign` header and are never transmitted.

Kraken balance codes remain server-side; the page displays normalized asset names only. Spot, Earn, and other Kraken balance-code variants that normalize to the same asset are added together before pricing, so each coin appears once. The Origin column labels these API-backed positions as Kraken and leaves room for future manual and additional API sources. Positions with a known absolute USD value below $10 are omitted from the table and derived views while still contributing to the portfolio total. Direct Kraken USD pairs and inverse USD pairs are valued from the latest public ticker close; USD cash is valued at $1. Curated CoinGecko matches supply icons, but never replace Kraken prices or values. Unmatched assets use an initials icon. Assets without a Kraken Spot USD price are labeled unpriced, and complete totals are withheld.

The main Portfolio Overview groups New Portfolio Editor rows by asset across all origins, sums signed balances and USD values, and calculates monthly yield from each origin's value and effective APY. Kraken remains the price source for Kraken assets, including xStocks; CoinGecko prices manual entries and supplies icons and market changes where a curated match exists.

The New Portfolio client owns the two-minute page refresh cycle (five minutes on iPhone Chrome), including its overview, compact history summary, worker status, Exposure Map, Scenario Lab, and dynamic market-pair menu. The pair menu ranks supported non-xStock assets by their signed values and preserves the selected chart across refreshes. Demo Mode divides balances, USD totals, position values, monthly yield, and historical dollar changes by 15 while leaving unit prices, percentages, and BTC-denominated values unchanged.

New Portfolio Historical Changes, the full history chart, and Statistics use `new_portfolio_history`, keyed by signed-in user and worker slot. New records include USD and BTC-denominated totals; records created before the BTC column was added retain a missing BTC observation rather than a fabricated value. The cookie-free worker now records only the New Portfolio. The summary endpoint reads only bounded snapshots nearest 24 hours, 7 days, and 30 days, so it never loads a chart-sized history payload. Changes include both market movement and deposits, withdrawals, API-balance changes, or manual edits. A period remains unavailable until a valid snapshot exists within 12 hours of its target.

All legacy `portfolio_history` rows are copied into New Portfolio history when the database has exactly one user, preserving their original timestamps, USD totals, BTC totals, and actual BTC balances. Each copied row stores its legacy ID and a synthetic negative slot; a unique `(user_id, legacy_history_id)` index makes the migration idempotent across restarts and concurrent deployments. The legacy rows remain untouched. With multiple users the copy is deliberately skipped because the old table has no ownership information.
