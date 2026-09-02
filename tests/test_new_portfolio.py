import unittest
from new_portfolio import manual_positions, merge_portfolios, overview_data


class NewPortfolioTests(unittest.TestCase):
    def test_manual_entries_are_priced_and_keep_admin_identity(self):
        rows=manual_positions([{'id':7,'coin_id':'bitcoin','origin':'Ledger','amount':2,'apy':4}],
            lambda ids:{'bitcoin':{'usd':100,'image':'btc.png','status':'fresh'}})
        self.assertEqual(rows[0]['asset'],'BTC');self.assertEqual(rows[0]['value_usd'],200)
        self.assertEqual(rows[0]['entry_id'],7);self.assertTrue(rows[0]['editable']);self.assertEqual(rows[0]['apy'],4)

    def test_manual_missing_price_makes_combined_total_incomplete(self):
        kraken={'positions':[{'asset':'ETH','origin':'Kraken','value_usd':50}],
            'known_value_usd':50,'total_value_usd':50,'unpriced_assets':[],'complete':True}
        manual=manual_positions([{'id':1,'coin_id':'unknown-coin','origin':'Wallet','amount':2,'apy':0}],lambda ids:{})
        result=merge_portfolios(kraken,manual)
        self.assertEqual(result['known_value_usd'],50);self.assertIsNone(result['total_value_usd'])
        self.assertEqual(result['unpriced_assets'],['UNKNOWN-COIN']);self.assertFalse(result['complete'])

    def test_combined_positions_sort_by_asset_then_origin(self):
        kraken={'positions':[{'asset':'ETH','origin':'Kraken','value_usd':50},{'asset':'BTC','origin':'Kraken','value_usd':100}],
            'known_value_usd':150,'total_value_usd':150,'unpriced_assets':[],'complete':True}
        manual=[{'asset':'eth','origin':'A wallet','value_usd':20},{'asset':'BTC','origin':'Ledger','value_usd':30}]
        result=merge_portfolios(kraken,manual)
        self.assertEqual([(p['asset'],p['origin']) for p in result['positions']],
            [('BTC','Kraken'),('BTC','Ledger'),('eth','A wallet'),('ETH','Kraken')])

    def test_overview_places_assets_without_one_hour_changes_last(self):
        portfolio={'positions':[
            {'asset':'ADA','origin':'Kraken','balance':1,'price_usd':1,'value_usd':1,'apy':0,'market_data':{}},
            {'asset':'ETH','origin':'Kraken','balance':1,'price_usd':2,'value_usd':2,'apy':0,'market_data':{'change_1h':0}},
            {'asset':'BTC','origin':'Kraken','balance':1,'price_usd':3,'value_usd':3,'apy':0,'market_data':{'change_1h':-1}},
            {'asset':'XRP','origin':'Kraken','balance':1,'price_usd':1,'value_usd':1,'apy':0,'market_data':{}}],
            'total_value_usd':7,'known_value_usd':7,'complete':True,'unpriced_assets':[]}
        result=overview_data(portfolio,3)
        self.assertEqual([row['asset'] for row in result['assets']],['BTC','ETH','ADA','XRP'])

    def test_overview_aggregates_origins_and_groups_xstocks(self):
        portfolio={'positions':[
            {'asset':'BTC','origin':'Kraken','balance':1,'price_usd':100,'value_usd':100,'apy':2,'market_data':{'image':'btc.png','change_24h':3}},
            {'asset':'BTC','origin':'Ledger','balance':2,'price_usd':100,'value_usd':200,'apy':0,'market_data':{'image':'btc.png','change_24h':3}},
            {'asset':'SNX','origin':'Wallet','balance':10,'price_usd':2,'value_usd':20,'apy':0,'market_data':{}},
            {'asset':'AAPLx','origin':'Kraken','balance':2,'price_usd':100,'value_usd':200,'apy':1,'market_data':{'change_24h':4}},
            {'asset':'SPYx','origin':'Broker','balance':1,'price_usd':500,'value_usd':500,'apy':0,'market_data':{}},
            {'asset':'TSLAx','origin':'Kraken','balance':-0.5,'price_usd':200,'value_usd':-100,'apy':0,'market_data':{}}],
            'total_value_usd':920,'known_value_usd':920,'complete':True,'unpriced_assets':[],'as_of':'now'}
        result=overview_data(portfolio,100)
        self.assertEqual([row['asset'] for row in result['assets']],['BTC','SNX','xStocks'])
        self.assertEqual(result['assets'][0]['total_balance'],3);self.assertEqual(result['assets'][0]['total_value'],300)
        self.assertEqual(result['assets'][0]['origins'],['Kraken','Ledger']);self.assertEqual(result['assets'][0]['daily_change'],3)
        xstocks=result['assets'][2]
        self.assertIsNone(xstocks['total_balance']);self.assertIsNone(xstocks['price'])
        self.assertIsNone(xstocks['daily_change']);self.assertEqual(xstocks['total_value'],600)
        self.assertEqual(xstocks['origins'],['Broker','Kraken']);self.assertTrue(xstocks['is_xstocks'])
        self.assertEqual(result['btc_value'],9.2);self.assertAlmostEqual(result['monthly_yield_usd'],(100*0.02+200*0.01)/12)
        self.assertEqual(result['exposure']['assets'],[('xStocks',600),('BTC',300),('SNX',20)])
        self.assertEqual(result['exposure']['platforms'],[('Broker',500),('Kraken',200),('Ledger',200),('Wallet',20)])
        self.assertEqual(result['exposure']['total'],920);self.assertEqual(result['exposure']['excluded'],0)
        self.assertEqual([row['coin'] for row in result['scenario']['positions']],['BTC','BTC','SNX','xStocks','xStocks','xStocks'])
        self.assertEqual(sum(row['value'] for row in result['scenario']['positions'] if row['coin']=='xStocks'),600)
        self.assertEqual(result['scenario']['excluded'],0);self.assertEqual(result['scenario']['unknownYield'],0)
        self.assertEqual(result['price_quality'],{'required_assets':3,'priced_assets':3,'complete':True,'stale':[],'sources':['Kraken']})


if __name__=='__main__':unittest.main()
