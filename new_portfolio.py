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
                'source':'CoinGecko','status':quote.get('status','missing'),
                'change_1h':quote.get('usd_1h_change'),'change_24h':quote.get('usd_24h_change'),
                'change_7d':quote.get('usd_7d_change')}})
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


def overview_data(portfolio, bitcoin_price=None):
    grouped={}
    for position in portfolio.get('positions',[]):
        asset=position.get('asset','Unknown');group=grouped.setdefault(asset,{
            'asset':asset,'total_balance':0,'total_value':0,'price':None,'image':None,
            'hourly_change':None,'daily_change':None,'seven_day_change':None,
            'monthly_yield':0,'complete':True,'yield_complete':True,'origins':set()})
        group['total_balance']+=position.get('balance') or 0;group['origins'].add(position.get('origin','Unknown'))
        value=position.get('value_usd');price=position.get('price_usd');apy=position.get('apy')
        if price is not None and group['price'] is None: group['price']=price
        if value is None: group['complete']=False;group['total_value']=None
        elif group['total_value'] is not None: group['total_value']+=value
        if value is None or apy is None: group['yield_complete']=False;group['monthly_yield']=None
        elif group['monthly_yield'] is not None: group['monthly_yield']+=value*apy/100/12
        market=position.get('market_data') or {}
        if market.get('image') and not group['image']: group['image']=market['image']
        for source,target in [('change_1h','hourly_change'),('change_24h','daily_change'),('change_7d','seven_day_change')]:
            if group[target] is None and market.get(source) is not None: group[target]=market[source]
    rows=[]
    for group in grouped.values():
        group['origins']=sorted(group['origins'],key=str.casefold);rows.append(group)
    rows.sort(key=lambda row:row['asset'].casefold())
    total=portfolio.get('total_value_usd');monthly=None if any(not row['yield_complete'] for row in rows) else sum(row['monthly_yield'] for row in rows)
    btc=total/bitcoin_price if total is not None and isinstance(bitcoin_price,(int,float)) and bitcoin_price>0 else None
    return {'assets':rows,'total_value_usd':total,'known_value_usd':portfolio.get('known_value_usd',0),
        'btc_value':btc,'monthly_yield_usd':monthly,'complete':portfolio.get('complete',False),
        'unpriced_assets':portfolio.get('unpriced_assets',[]),'as_of':portfolio.get('as_of')}
