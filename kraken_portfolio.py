"""Read-only Kraken balance portfolio. Credentials never leave the server."""
import base64
import datetime as dt
import hashlib
import hmac
import math
import os
import threading
import time
import urllib.parse
from pathlib import Path
import requests
from dotenv import dotenv_values

BASE_URL = 'https://api.kraken.com'
BALANCE_PATH = '/0/private/Balance'
CREDENTIAL_FILE = Path(__file__).with_name('.kraken_credentials.txt')
COINGECKO_IDS = {
    'AAVE':'aave','ADA':'cardano','ALGO':'algorand','APE':'apecoin','ARB':'arbitrum',
    'ATOM':'cosmos','AVAX':'avalanche-2','BCH':'bitcoin-cash','BTC':'bitcoin',
    'DAI':'dai','DOGE':'dogecoin','DOT':'polkadot','ETC':'ethereum-classic','ETH':'ethereum',
    'FIL':'filecoin','ICP':'internet-computer','LINK':'chainlink','LTC':'litecoin',
    'MATIC':'matic-network','NEAR':'near','OP':'optimism','PAXG':'pax-gold','PEPE':'pepe',
    'SHIB':'shiba-inu','SOL':'solana','SUI':'sui','TRX':'tron','UNI':'uniswap',
    'USDC':'usd-coin','USDT':'tether','XLM':'stellar','XMR':'monero','XRP':'ripple',
    'ZEC':'zcash'
}

class KrakenUnavailable(Exception): pass


def sign_request(path, payload, secret):
    encoded = urllib.parse.urlencode(payload)
    digest = hashlib.sha256((str(payload['nonce']) + encoded).encode()).digest()
    message = path.encode() + digest
    try: key = base64.b64decode(secret, validate=True)
    except (ValueError, TypeError): raise KrakenUnavailable('Kraken private key is invalid.') from None
    return base64.b64encode(hmac.new(key, message, hashlib.sha512).digest()).decode()


def normalize_asset(raw):
    base = raw.split('.', 1)[0]
    aliases = {'XXBT':'BTC','XBT':'BTC','XETH':'ETH','ZEUR':'EUR','ZUSD':'USD','ZGBP':'GBP','ZJPY':'JPY','ZCAD':'CAD','ZCHF':'CHF','ZAUD':'AUD'}
    return aliases.get(base, base)


def parse_number(value):
    try: number=float(value)
    except (TypeError, ValueError): return None
    return number if math.isfinite(number) else None


def aggregate_balances(balances):
    aggregated={}
    for raw,amount in balances.items():
        asset=normalize_asset(raw)
        aggregated[asset]=aggregated.get(asset,0)+amount
    return {asset:amount for asset,amount in aggregated.items() if amount != 0}


def enrich_market_data(result, quote_reader):
    positions=[dict(position) for position in result.get('positions',[])]
    ids={COINGECKO_IDS[position['asset']] for position in positions if position.get('asset') in COINGECKO_IDS}
    quotes=quote_reader(ids) if ids else {}
    for position in positions:
        coin_id=COINGECKO_IDS.get(position.get('asset'));quote=quotes.get(coin_id,{}) if coin_id else {}
        position['market_data']={
            'coin_id':coin_id,'image':quote.get('image') or None,'source':'CoinGecko' if coin_id else None,
            'status':quote.get('status') if coin_id else 'unavailable',
            'change_1h':quote.get('usd_1h_change'),'change_24h':quote.get('usd_24h_change'),
            'change_7d':quote.get('usd_7d_change')
        }
    return {**result,'positions':positions}


class KrakenPortfolio:
    def __init__(self, http=requests, clock=time.time, credentials=None):
        self.http, self.clock, self.credentials = http, clock, credentials
        self.lock=threading.Lock();self.last_nonce=0;self.cached=None;self.cache_time=0
        self.pair_cache={}

    def _credentials(self):
        values = self.credentials if self.credentials is not None else {**dotenv_values(CREDENTIAL_FILE), **os.environ}
        key, secret = values.get('KRAKEN_API_KEY'), values.get('KRAKEN_PRIVATE_KEY')
        if not isinstance(key,str) or not key.strip() or not isinstance(secret,str) or not secret.strip():
            raise KrakenUnavailable('Kraken credentials are not configured on this server.')
        return key.strip(), secret.strip()

    def _json(self, response, label):
        if response.status_code != 200: raise KrakenUnavailable(f'{label} returned HTTP {response.status_code}.')
        try: data=response.json()
        except (ValueError, TypeError): raise KrakenUnavailable(f'{label} returned invalid data.') from None
        if not isinstance(data,dict): raise KrakenUnavailable(f'{label} returned invalid data.')
        errors=data.get('error') or []
        if errors: raise KrakenUnavailable(f'{label} rejected the request: {"; ".join(str(e) for e in errors)[:300]}')
        if not isinstance(data.get('result'),dict): raise KrakenUnavailable(f'{label} returned no result.')
        return data['result']

    def _balances(self, key, secret):
        now=int(self.clock()*1000);self.last_nonce=max(now,self.last_nonce+1)
        payload={'nonce':str(self.last_nonce)}
        response=self.http.post(BASE_URL+BALANCE_PATH,data=payload,
            headers={'API-Key':key,'API-Sign':sign_request(BALANCE_PATH,payload,secret),'User-Agent':'crypto-portfolio-tracker/experimental'},
            timeout=(5,20),allow_redirects=False)
        result=self._json(response,'Kraken balance API')
        balances={}
        for asset,value in result.items():
            amount=parse_number(value)
            if isinstance(asset,str) and amount is not None and amount != 0: balances[asset]=amount
        return balances

    def _asset_pairs(self, asset_class='currency'):
        now=self.clock()
        cached=self.pair_cache.get(asset_class)
        if cached and now-cached[0] < 3600: return cached[1]
        params={'aclass':asset_class} if asset_class!='currency' else None
        response=self.http.get(BASE_URL+'/0/public/AssetPairs',params=params,timeout=(5,20),allow_redirects=False)
        pairs=self._json(response,'Kraken asset-pairs API');self.pair_cache[asset_class]=(now,pairs)
        return pairs

    def _prices(self, balances):
        assets={normalize_asset(asset) for asset in balances}
        selected={}
        classes=['currency']
        if any(asset.endswith('x') for asset in assets): classes.append('tokenized_asset')
        tickers={}
        for asset_class in classes:
            class_selected={}
            for result_key,info in self._asset_pairs(asset_class).items():
                if not isinstance(info,dict) or info.get('status') not in (None,'online'): continue
                base,quote=info.get('base'),info.get('quote')
                normalized_base = normalize_asset(base) if isinstance(base, str) else None
                normalized_quote = normalize_asset(quote) if isinstance(quote, str) else None
                pair_name=info.get('altname') or result_key
                if normalized_base in assets and normalized_quote=='USD': class_selected.setdefault(normalized_base,(pair_name,result_key,False))
                elif normalized_base=='USD' and normalized_quote in assets: class_selected.setdefault(normalized_quote,(pair_name,result_key,True))
            if class_selected:
                params={'pair':','.join(pair for pair,_,_ in class_selected.values())}
                if asset_class!='currency': params['asset_class']=asset_class
                response=self.http.get(BASE_URL+'/0/public/Ticker',params=params,timeout=(5,20),allow_redirects=False)
                result=self._json(response,'Kraken ticker API')
                for asset,(pair,result_key,inverse) in class_selected.items():
                    ticker=result.get(pair) or result.get(result_key) or result.get(pair.replace('USD','/USD')) or {}
                    close=ticker.get('c') if isinstance(ticker,dict) else None
                    price=parse_number(close[0] if isinstance(close,list) and close else None)
                    if price is not None and price>0: selected[asset]=(price,pair,inverse)
        prices={}
        for asset in assets:
            if asset=='USD': prices[asset]=(1.0,'USD')
            elif asset in selected:
                price,pair,inverse=selected[asset];prices[asset]=(1/price if inverse else price,pair)
        return prices

    def read(self, force=False):
        with self.lock:
            now=self.clock()
            if not force and self.cached is not None and now-self.cache_time < 30: return self.cached
            key,secret=self._credentials();balances=aggregate_balances(self._balances(key,secret));prices=self._prices(balances)
            positions=[]
            for asset,amount in balances.items():
                quote=prices.get(asset);price=quote[0] if quote else None
                positions.append({'asset':asset,'balance':amount,'price_usd':price,
                    'value_usd':amount*price if price is not None else None,'price_pair':quote[1] if quote else None,
                    'status':'priced' if quote else 'unpriced'})
            positions.sort(key=lambda p:(p['value_usd'] is None,-abs(p['value_usd'] or 0),p['asset']))
            unpriced=sorted(set(p['asset'] for p in positions if p['value_usd'] is None))
            known=sum(p['value_usd'] for p in positions if p['value_usd'] is not None)
            hidden=sum(1 for p in positions if p['value_usd'] is not None and abs(p['value_usd']) < 10)
            visible=[p for p in positions if p['value_usd'] is None or abs(p['value_usd']) >= 10]
            result={'positions':visible,'known_value_usd':known,'total_value_usd':known if not unpriced else None,
                'unpriced_assets':unpriced,'complete':not unpriced,'as_of':dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat()}
            result['hidden_small_positions']=hidden
            self.cached=result;self.cache_time=now
            return result

portfolio=KrakenPortfolio()
