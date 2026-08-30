import unittest
from unittest.mock import Mock
import datetime as dt
from price_data import PriceData, quality_summary


class PriceDataTests(unittest.TestCase):
    def setUp(self):
        self.now=1800000000
        self.http=Mock()
        self.service=PriceData(self.http,lambda:self.now)
    def market(self, **changes):
        return dict(id='bitcoin',current_price=100,last_updated=dt.datetime.fromtimestamp(self.now,dt.timezone.utc).isoformat(),**changes)
    def reply(self,data):
        self.http.get.return_value.status_code=200
        self.http.get.return_value.json.return_value=data
    def test_subset_cache_and_unknown_changes(self):
        self.reply([self.market()])
        result=self.service.read(['bitcoin'])['bitcoin']
        self.assertEqual(result['status'],'fresh')
        self.assertIsNone(result['usd_1h_change'])
        self.assertEqual(self.http.get.call_args.kwargs['params']['ids'],'bitcoin')
        self.now+=10
        self.assertTrue(self.service.read(['bitcoin'])['bitcoin']['cached'])
        self.assertEqual(self.http.get.call_count,1)
    def test_outage_marks_fallback_then_expires_and_recovers(self):
        self.reply([self.market()]);self.service.read(['bitcoin'])
        self.now+=61;self.http.get.return_value.status_code=429
        quote=self.service.read(['bitcoin'])['bitcoin']
        self.assertEqual(quote['usd'],100);self.assertEqual(quote['status'],'stale')
        self.now+=86401
        self.assertEqual(self.service.read(['bitcoin'])['bitcoin']['status'],'missing')
        self.now+=61;self.reply([self.market()])
        self.assertEqual(self.service.read(['bitcoin'])['bitcoin']['status'],'fresh')
    def test_partial_invalid_future_and_stale_quotes(self):
        row=self.market();row['current_price']=float('nan');self.reply([row])
        self.assertIsNone(self.service.read(['bitcoin'])['bitcoin']['usd'])
        self.now+=61;row=self.market();row['last_updated']=dt.datetime.fromtimestamp(self.now+120,dt.timezone.utc).isoformat();self.reply([row])
        self.assertIsNone(self.service.read(['bitcoin'])['bitcoin']['usd'])
        self.now+=61;row=self.market();row['last_updated']=dt.datetime.fromtimestamp(self.now-1000,dt.timezone.utc).isoformat();self.reply([row])
        result=self.service.read(['bitcoin','unknown'])
        self.assertEqual(result['bitcoin']['status'],'stale')
        self.assertEqual(quality_summary(result,result)['missing'],['unknown'])
        self.assertFalse(quality_summary(result,result)['complete'])
    def test_chf_weekend_and_unavailable_changes(self):
        date=dt.datetime.fromtimestamp(self.now,dt.timezone.utc).date()-dt.timedelta(days=2)
        self.reply({'date':date.isoformat(),'rates':{'USD':1.2}})
        quote=self.service.read(['CHF'])['CHF']
        self.assertEqual(quote['status'],'fresh');self.assertIsNone(quote['usd_24h_change'])
        self.assertIn('/v1/latest',self.http.get.call_args.args[0])
    def test_malformed_response_and_zero_do_not_become_quotes(self):
        for data in [{}, [dict(self.market(),current_price=0)], [dict(self.market(),current_price=True)], [dict(self.market(),last_updated=None)]]:
            self.now+=61;self.reply(data)
            self.assertEqual(self.service.read(['bitcoin'])['bitcoin']['status'],'missing')

if __name__=='__main__':unittest.main()
