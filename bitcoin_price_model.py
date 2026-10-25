"""Cached Bitcoin history and the genesis-date power-law price model."""
import datetime as dt
import math
import threading
import time

import requests


GENESIS_DATE = dt.date(2009, 1, 3)
ALL_HISTORY_START = dt.date(2010, 7, 25)
MODEL_COEFFICIENT = 4.42e-17
MODEL_EXPONENT = 5.6
COIN_METRICS_URL = 'https://community-api.coinmetrics.io/v4/timeseries/asset-metrics'
RANGE_DAYS = {'1y': 365, '2y': 730, '5y': 1826, '10y': 3652, 'all': None}


class BitcoinPriceModelUnavailable(Exception):
    pass


def model_price(date):
    days = (date - GENESIS_DATE).days
    return MODEL_COEFFICIENT * days ** MODEL_EXPONENT if days > 0 else 0.0


class BitcoinPriceModel:
    def __init__(self, http=requests, clock=time.time):
        self.http, self.clock = http, clock
        self.lock = threading.Lock()
        self.cached_history = None
        self.cache_time = 0

    def _history(self):
        now = self.clock()
        if self.cached_history is not None and now - self.cache_time < 3600:
            return self.cached_history
        try:
            response = self.http.get(COIN_METRICS_URL, params={
                'assets': 'btc', 'metrics': 'PriceUSD', 'frequency': '1d',
                'start_time': GENESIS_DATE.isoformat(), 'page_size': 10000,
            }, timeout=(5, 30), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('provider response')
            payload = response.json()
            rows = payload.get('data') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError('provider data')
            parsed = []
            for row in rows:
                try:
                    date = dt.date.fromisoformat(row['time'][:10])
                    price = float(row['PriceUSD'])
                except (KeyError, TypeError, ValueError):
                    continue
                if date >= GENESIS_DATE and math.isfinite(price) and price > 0:
                    parsed.append((date, price))
            if not parsed:
                raise ValueError('empty history')
            parsed.sort(key=lambda item: item[0])
            self.cached_history = parsed
            self.cache_time = now
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            if self.cached_history is None:
                raise BitcoinPriceModelUnavailable('Bitcoin history is temporarily unavailable.') from None
        return self.cached_history

    def read(self, selected_range='all', current_quote=None, projection='none'):
        if selected_range not in RANGE_DAYS:
            raise ValueError('Unsupported price-model range.')
        if projection not in ('none', '5y'):
            raise ValueError('Unsupported price-model projection.')
        now = dt.datetime.fromtimestamp(self.clock(), dt.timezone.utc)
        end = now.date()
        model_end = end + dt.timedelta(days=1826) if projection == '5y' else end
        days = RANGE_DAYS[selected_range]
        start = ALL_HISTORY_START if days is None else max(GENESIS_DATE, end - dt.timedelta(days=days))
        actual = {date: price for date, price in self._history() if start <= date <= end}
        quote = current_quote or {}
        current_price = quote.get('usd')
        if isinstance(current_price, (int, float)) and not isinstance(current_price, bool) and math.isfinite(current_price) and current_price > 0:
            actual[end] = current_price
        model_start = max(start, GENESIS_DATE + dt.timedelta(days=1))
        model = []
        date = model_start
        while date <= model_end:
            model.append([int(dt.datetime.combine(date, dt.time(), dt.timezone.utc).timestamp() * 1000), model_price(date)])
            date += dt.timedelta(days=1)
        actual_points = [[int(dt.datetime.combine(date, dt.time(), dt.timezone.utc).timestamp() * 1000), price]
                         for date, price in sorted(actual.items())]
        current_model = model_price(end)
        latest_actual = actual_points[-1][1] if actual_points else None
        return {
            'range': selected_range, 'actual': actual_points, 'model': model,
            'current_actual': latest_actual, 'current_model': current_model,
            'ratio': latest_actual / current_model if latest_actual is not None and current_model > 0 else None,
            'deviation_percent': (latest_actual / current_model - 1) * 100 if latest_actual is not None and current_model > 0 else None,
            'projection': projection, 'projected_through': model_end.isoformat() if projection == '5y' else None,
            'as_of': now.isoformat(), 'historical_source': 'Coin Metrics Community',
            'latest_source': quote.get('source') if current_price is not None else None,
        }


bitcoin_price_model = BitcoinPriceModel()
