import datetime as dt
import unittest
from unittest.mock import Mock

from bitcoin_price_model import BitcoinPriceModel, BitcoinPriceModelUnavailable, GENESIS_DATE, ALL_HISTORY_START, model_price


class Reply:
    def __init__(self, data, status=200): self.data=data;self.status_code=status
    def json(self): return self.data


class BitcoinPriceModelTests(unittest.TestCase):
    def test_formula_uses_calendar_days_since_genesis(self):
        self.assertEqual(model_price(GENESIS_DATE),0)
        self.assertAlmostEqual(model_price(GENESIS_DATE+dt.timedelta(days=10)),4.42e-17*10**5.6)

    def test_history_range_live_quote_statistics_and_cache(self):
        now=dt.datetime(2026,10,25,tzinfo=dt.timezone.utc).timestamp();http=Mock()
        http.get.return_value=Reply({'data':[
            {'asset':'btc','time':'2025-10-24T00:00:00.000000000Z','PriceUSD':'60000'},
            {'asset':'btc','time':'2026-10-24T00:00:00.000000000Z','PriceUSD':'100000'},
            {'asset':'btc','time':'bad','PriceUSD':'nan'}]})
        service=BitcoinPriceModel(http,lambda:now)
        result=service.read('1y',{'usd':110000,'source':'CoinGecko'})
        self.assertEqual(result['actual'][-1][1],110000)
        self.assertEqual(result['latest_source'],'CoinGecko')
        self.assertEqual(len(result['model']),366)
        self.assertAlmostEqual(result['ratio'],110000/result['current_model'])
        complete=service.read('all',{'usd':110000});self.assertEqual(http.get.call_count,1)
        self.assertEqual(dt.datetime.fromtimestamp(complete['model'][0][0]/1000,dt.timezone.utc).date(),ALL_HISTORY_START)
        self.assertTrue(all(dt.datetime.fromtimestamp(point[0]/1000,dt.timezone.utc).date()>=ALL_HISTORY_START for point in complete['actual']))

    def test_validation_and_initial_provider_failure(self):
        service=BitcoinPriceModel(Mock(),lambda:1)
        with self.assertRaisesRegex(ValueError,'Unsupported'): service.read('bad')
        service.http.get.return_value=Reply({},503)
        with self.assertRaises(BitcoinPriceModelUnavailable): service.read('all')


if __name__=='__main__': unittest.main()
