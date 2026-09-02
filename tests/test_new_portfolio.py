import unittest
from new_portfolio import manual_positions, merge_portfolios


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


if __name__=='__main__':unittest.main()
