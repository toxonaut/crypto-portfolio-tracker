import math
import unittest
from unittest.mock import Mock
from kraken_portfolio import KrakenPortfolio, KrakenUnavailable, sign_request, normalize_asset, aggregate_balances, enrich_market_data

class Reply:
    def __init__(self,data,status=200):self.data=data;self.status_code=status
    def json(self):return self.data

class KrakenPortfolioTests(unittest.TestCase):
    def test_official_signature_vector(self):
        payload={'nonce':'1616492376594','ordertype':'limit','pair':'XBTUSD','price':37500,'type':'buy','volume':1.25}
        secret='kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=='
        self.assertEqual(sign_request('/0/private/AddOrder',payload,secret),'4/dpxb3iT4tp/ZCVEwSnEsLxx0bqyhLpdfOpc6fn7OR8+UClSV5n9E6aSS8MPtnRfp32bAb0nmbRn6H8ndwLUQ==')
    def test_balance_only_private_call_and_public_usd_valuation(self):
        http=Mock();clock=Mock(return_value=1700000000)
        http.post.return_value=Reply({'error':[],'result':{'XXBT':'2','ZUSD':'50','XETH':'3','ZCHF':'2','EMPTY':'0','BAD':'nan'}})
        pairs={'XXBTZUSD':{'base':'XXBT','quote':'ZUSD','altname':'XBTUSD','status':'online'},'XETHZUSD':{'base':'XETH','quote':'ZUSD','altname':'ETHUSD','status':'online'},'ZUSDZCHF':{'base':'ZUSD','quote':'ZCHF','altname':'USDCHF','status':'online'}}
        ticker={'XXBTZUSD':{'c':['100','1']},'XETHZUSD':{'c':['10','1']},'ZUSDZCHF':{'c':['0.8','1']}}
        http.get.side_effect=[Reply({'error':[],'result':pairs}),Reply({'error':[],'result':ticker})]
        service=KrakenPortfolio(http,clock,{'KRAKEN_API_KEY':'public','KRAKEN_PRIVATE_KEY':'c2VjcmV0'})
        result=service.read()
        self.assertEqual(http.post.call_args_list[0].args[0],'https://api.kraken.com/0/private/Balance')
        self.assertNotIn('key',str(result).lower());self.assertEqual(result['total_value_usd'],282.5);self.assertTrue(result['complete'])
        self.assertEqual([(p['asset'],p['value_usd']) for p in result['positions']],[('BTC',200),('USD',50),('ETH',30)])
        self.assertEqual(result['hidden_small_positions'],1)
        self.assertTrue(all('raw_asset' not in p for p in result['positions']))
        self.assertEqual(service.read(),result);self.assertEqual(http.post.call_count,1)
        clock.return_value+=31;http.post.return_value=Reply({'error':[],'result':{'ZUSD':'1'}})
        self.assertEqual(service.read()['total_value_usd'],1);self.assertEqual(http.post.call_count,2)
        nonces=[call.kwargs['data']['nonce'] for call in http.post.call_args_list];self.assertLess(int(nonces[0]),int(nonces[1]))

    def test_spot_and_earn_balances_are_combined_before_valuation(self):
        http=Mock();http.post.side_effect=[
            Reply({'error':[],'result':{'XETH':'2','ETH.F':'3','SOL':'4','SOL.F':'-4'}}),
            Reply({'error':[],'result':{'items':[{'native_asset':'ETH','strategy_id':'eth-flex','amount_allocated':{'total':{'native':'3'}}}]}}),
            Reply({'error':[],'result':{'items':[{'id':'eth-flex','apr_estimate':{'low':'4','high':'6'}}]}})]
        pairs={'XETHZUSD':{'base':'XETH','quote':'ZUSD','altname':'ETHUSD','status':'online'}}
        ticker={'XETHZUSD':{'c':['10','1']}}
        http.get.side_effect=[Reply({'error':[],'result':pairs}),Reply({'error':[],'result':ticker})]
        result=KrakenPortfolio(http,lambda:1,{'KRAKEN_API_KEY':'a','KRAKEN_PRIVATE_KEY':'Yg=='}).read()
        self.assertEqual(result['positions'],[{'asset':'ETH','origin':'Kraken','balance':5,'apy':3,'apy_source':'Kraken Earn estimate','price_usd':10,'value_usd':50,'price_pair':'ETHUSD','status':'priced'}])
        self.assertEqual(result['total_value_usd'],50)
        self.assertEqual(result['unpriced_assets'],[])
        self.assertEqual(aggregate_balances({'XXBT':1,'XBT':2,'XBT.F':3}),{'BTC':6})

    def test_market_data_enrichment_uses_only_curated_coingecko_matches(self):
        base={'positions':[{'asset':'BTC'},{'asset':'HYPE'},{'asset':'AAPLx'}],'known_value_usd':1}
        requested=[]
        def read(ids):
            requested.extend(ids)
            return {'bitcoin':{'image':'https://example.test/btc.png','status':'fresh'},'hyperliquid':{'image':'https://example.test/hype.png','status':'fresh'}}
        result=enrich_market_data(base,read)
        self.assertEqual(set(requested),{'bitcoin','hyperliquid'});self.assertNotIn('market_data',base['positions'][0])
        self.assertEqual(result['positions'][0]['market_data']['image'],'https://example.test/btc.png')
        self.assertEqual(result['positions'][1]['market_data']['coin_id'],'hyperliquid')
        self.assertIsNone(result['positions'][2]['market_data']['coin_id'])
        self.assertEqual(result['positions'][2]['market_data']['status'],'unavailable')
    def test_unpriced_assets_make_total_explicitly_unavailable(self):
        http=Mock();http.post.return_value=Reply({'error':[],'result':{'MYSTERY':'4','ZUSD':'3'}})
        http.get.return_value=Reply({'error':[],'result':{}})
        result=KrakenPortfolio(http,lambda:1,{'KRAKEN_API_KEY':'a','KRAKEN_PRIVATE_KEY':'Yg=='}).read()
        self.assertIsNone(result['total_value_usd']);self.assertEqual(result['known_value_usd'],3)
        self.assertEqual(result['unpriced_assets'],['MYSTERY']);self.assertFalse(result['complete']);self.assertEqual(result['hidden_small_positions'],1)
    def test_tokenized_stock_uses_kraken_asset_class_and_filters_dust(self):
        http=Mock();http.post.return_value=Reply({'error':[],'result':{'AAPLx.T':'0.1','MSFTx.T':'0.01'}})
        standard=Reply({'error':[],'result':{}})
        stocks=Reply({'error':[],'result':{
            'AAPLxUSD':{'base':'AAPLx','quote':'ZUSD','altname':'AAPLxUSD','status':'online'},
            'MSFTxUSD':{'base':'MSFTx','quote':'ZUSD','altname':'MSFTxUSD','status':'online'}}})
        tickers=Reply({'error':[],'result':{'AAPLxUSD':{'c':['250','1']},'MSFTxUSD':{'c':['300','1']}}})
        http.get.side_effect=[standard,stocks,tickers]
        result=KrakenPortfolio(http,lambda:1,{'KRAKEN_API_KEY':'a','KRAKEN_PRIVATE_KEY':'Yg=='}).read()
        self.assertEqual(result['total_value_usd'],28)
        self.assertEqual([(p['asset'],p['price_usd'],p['value_usd']) for p in result['positions']],[('AAPLx',250,25)])
        self.assertEqual(result['hidden_small_positions'],1)
        self.assertEqual(http.get.call_args_list[1].kwargs['params'],{'aclass':'tokenized_asset'})
        self.assertEqual(http.get.call_args_list[2].kwargs['params']['asset_class'],'tokenized_asset')

    def test_provider_and_configuration_fail_closed_without_secret_leak(self):
        with self.assertRaisesRegex(KrakenUnavailable,'not configured'):
            KrakenPortfolio(Mock(),lambda:1,{}).read()
        http=Mock();http.post.return_value=Reply({'error':['EAPI:Invalid key'],'result':None})
        with self.assertRaisesRegex(KrakenUnavailable,'Invalid key') as raised:
            KrakenPortfolio(http,lambda:1,{'KRAKEN_API_KEY':'sensitive-public','KRAKEN_PRIVATE_KEY':'c2Vuc2l0aXZl'}).read()
        self.assertNotIn('sensitive',str(raised.exception))
        for raw,expected in [('XXBT','BTC'),('XETH','ETH'),('XZEC','ZEC'),('ZUSD','USD'),('ETH.F','ETH'),('SOL','SOL')]:self.assertEqual(normalize_asset(raw),expected)

if __name__=='__main__':unittest.main()
