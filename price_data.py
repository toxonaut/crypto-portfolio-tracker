"""Bounded, process-local price cache with explicit provenance and quality."""
import datetime as dt
import threading
import time
import math
import requests
from snapshot_service import valid_positive


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def timestamp(value):
    try:
        date = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.replace(tzinfo=date.tzinfo or dt.timezone.utc).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def iso(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat() if value is not None else None


class PriceData:
    def __init__(self, http=requests, clock=time.time):
        self.http, self.clock = http, clock
        self.cache, self.attempts = {}, {}
        self.lock = threading.Lock()

    def _get(self, url, params):
        response = self.http.get(url, params=params, timeout=(5, 15), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError('Price provider unavailable')
        return response.json()

    def read(self, coin_ids):
        ids = sorted(set(coin_ids))
        with self.lock:
            now = self.clock()
            # Bound memory even when assets are frequently added and removed.
            self.cache = {k:v for k,v in self.cache.items() if now-v['fetched_at'] <= 86400}
            self.attempts = {k:v for k,v in self.attempts.items() if now-v <= 86400}
            due = [c for c in ids if now-self.attempts.get(c, float('-inf')) >= 60]
            crypto = [c for c in due if c.lower() != 'chf']
            for start in range(0, len(crypto), 100):
                batch = crypto[start:start+100]
                try:
                    data = self._get('https://api.coingecko.com/api/v3/coins/markets',
                        {'ids': ','.join(batch), 'vs_currency':'usd', 'per_page':100,
                         'page':1, 'sparkline':'false', 'price_change_percentage':'1h,24h,7d'})
                    if not isinstance(data, list): raise ValueError()
                    for row in data:
                        if not isinstance(row, dict) or row.get('id') not in batch: continue
                        updated = timestamp(row.get('last_updated'))
                        if not valid_positive(row.get('current_price')) or updated is None or not -60 <= now-updated <= 86400: continue
                        coin = row['id']
                        quote = {'usd':row['current_price'], 'updated_at':updated, 'fetched_at':now,
                            'source':'CoinGecko', 'image':row.get('image') or '',
                            'usd_1h_change':number(row.get('price_change_percentage_1h_in_currency')),
                            'usd_24h_change':number(row.get('price_change_percentage_24h')),
                            'usd_7d_change':number(row.get('price_change_percentage_7d_in_currency'))}
                        if updated >= self.cache.get(coin, {}).get('updated_at', 0): self.cache[coin] = quote
                except (requests.RequestException, ValueError, TypeError, AttributeError):
                    pass  # Never replace a good quote with an error or invalid response.
            chf = [c for c in due if c.lower() == 'chf']
            if chf:
                try:
                    data = self._get('https://api.frankfurter.dev/v1/latest', {'base':'CHF','symbols':'USD'})
                    updated = timestamp(data.get('date'))
                    rate = data.get('rates', {}).get('USD')
                    age = (dt.datetime.fromtimestamp(now, dt.timezone.utc).date()-dt.date.fromisoformat(data.get('date', ''))).days
                    if valid_positive(rate) and 0 <= age <= 7:
                        for coin in chf:
                            self.cache[coin] = {'usd':rate,'updated_at':updated,'fetched_at':now,
                                'source':'Frankfurter (daily reference rate)', 'image':'https://flagcdn.com/w40/ch.png',
                                'usd_1h_change':None,'usd_24h_change':None,'usd_7d_change':None}
                except (requests.RequestException, ValueError, TypeError, AttributeError):
                    pass
            self.attempts.update({c:now for c in due})
            result = {}
            for coin in ids:
                quote = self.cache.get(coin)
                if quote:
                    age = now-quote['updated_at']
                    max_age = 8*86400 if coin.lower() == 'chf' else 86400
                    if age > max_age: quote = None
                if not quote:
                    result[coin] = {'usd':None, 'status':'missing', 'source':None, 'as_of':None,
                        'fetched_at':None, 'cached':False, 'usd_1h_change':None,'usd_24h_change':None,'usd_7d_change':None}
                    continue
                failed_refresh = self.attempts[coin] > quote['fetched_at']
                if coin.lower() == 'chf':
                    fresh = (dt.datetime.fromtimestamp(now, dt.timezone.utc).date()-dt.datetime.fromtimestamp(quote['updated_at'],dt.timezone.utc).date()).days <= 7
                else:
                    fresh = age <= 900
                result[coin] = {**quote,'status':'fresh' if fresh and not failed_refresh else 'stale',
                    'cached':now > quote['fetched_at'], 'as_of':iso(quote['updated_at']), 'fetched_at':iso(quote['fetched_at'])}
            return result


prices = PriceData()


def quality_summary(quotes, required):
    required = set(required)
    missing = sorted(c for c in required if quotes.get(c, {}).get('status', 'missing') == 'missing')
    stale = sorted(c for c in required if quotes.get(c, {}).get('status') == 'stale')
    return {'complete':not missing, 'fresh':not missing and not stale,
            'missing':missing, 'stale':stale, 'priced_assets':len(required)-len(missing), 'required_assets':len(required)}
