"""Composition helpers for the isolated replacement portfolio editor."""
import math
from kraken_portfolio import COINGECKO_IDS


def manual_positions(entries, quote_reader):
    entries=list(entries)
    coin_ids={entry['coin_id'] for entry in entries}
    quotes=quote_reader(coin_ids) if coin_ids else {}
    symbols={coin_id:asset for asset,coin_id in COINGECKO_IDS.items()}
    positions=[]
    for entry in entries:
        quote=quotes.get(entry['coin_id'],{});price=quote.get('usd')
        if not isinstance(price,(int,float)) or isinstance(price,bool) or not math.isfinite(price) or price <= 0: price=None
        asset=symbols.get(entry['coin_id'],entry['coin_id'].upper())
        positions.append({'asset':asset,'coin_id':entry['coin_id'],'origin':entry['origin'],
            'balance':entry['amount'],'apy':entry['apy'],'apy_source':'Manual',
            'price_usd':price,'value_usd':entry['amount']*price if price is not None else None,
            'price_pair':'CoinGecko USD' if price is not None else None,
            'status':'priced' if price is not None else 'unpriced','entry_id':entry['id'],'editable':True,
            'market_data':{'coin_id':entry['coin_id'],'image':quote.get('image') or None,
                'source':'CoinGecko','status':quote.get('status','missing')}})
    return positions


def merge_portfolios(kraken, manual):
    positions=[*kraken.get('positions',[]),*manual]
    positions.sort(key=lambda p:(p.get('asset','').casefold(),p.get('origin','').casefold()))
    manual_known=sum(p['value_usd'] for p in manual if p['value_usd'] is not None)
    missing=sorted(set(kraken.get('unpriced_assets',[])) | {p['asset'] for p in manual if p['value_usd'] is None})
    known=kraken.get('known_value_usd',0)+manual_known
    return {**kraken,'positions':positions,'known_value_usd':known,
        'total_value_usd':known if not missing else None,'unpriced_assets':missing,'complete':not missing,
        'manual_positions':len(manual)}
