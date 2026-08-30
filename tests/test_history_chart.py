import datetime as dt
import unittest
from decimal import Decimal
from types import SimpleNamespace
from flask import Flask
from flask_login import LoginManager, UserMixin
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, DateTime, Float
from sqlalchemy.orm import Session
from history_chart import read_chart, parse_flow, cash_flows, create_history_blueprint


def fixture_app():
    engine=create_engine('sqlite://')
    metadata=MetaData()
    history=Table('portfolio_history',metadata,Column('id',Integer,primary_key=True),Column('date',DateTime,index=True),Column('total_value',Float),Column('btc',Float))
    metadata.create_all(engine);cash_flows.create(engine,checkfirst=True)
    session=Session(engine)
    app=Flask(__name__);app.secret_key='fixture-only'
    login=LoginManager(app)
    user=UserMixin();user.id='1'
    login.user_loader(lambda id:user)
    app.register_blueprint(create_history_blueprint(SimpleNamespace(session=session),history))
    return app,session,history,engine


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.app,self.session,self.history,self.engine=fixture_app()
        self.now=dt.datetime(2026,8,30,12)
    def tearDown(self):
        self.session.close();self.engine.dispose()
    def add(self,hours,value,btc=1):
        self.session.execute(self.history.insert().values(date=self.now-dt.timedelta(hours=hours),total_value=value,btc=btc))
    def read(self,days='90',points=600):return read_chart(self.session,self.history,days,points,self.now)

    def test_range_filter_cap_and_extrema_preserved_in_large_history(self):
        rows=[dict(date=self.now-dt.timedelta(minutes=30000-i),total_value=100+i%9,btc=1) for i in range(30000)]
        rows[-200]['total_value']=90000;rows[-199]['total_value']=-500
        rows[-198]['btc']=90;rows[-197]['btc']=.01
        self.session.execute(self.history.insert(),rows)
        r=self.read('7',240)
        self.assertLessEqual(len(r['data']),240)
        self.assertLess(r['meta']['source_count'],len(rows))
        self.assertTrue(r['meta']['sampled'])
        self.assertEqual(max(p['total_value'] for p in r['data']),90000)
        self.assertEqual(min(p['total_value'] for p in r['data']),-500)
        self.assertEqual(max(p['btc'] for p in r['data']),90)
        self.assertEqual(min(p['btc'] for p in r['data']),.01)
        self.assertEqual(r['data'][-1]['datetime'],rows[-1]['date'].isoformat())
        self.assertTrue(all(dt.datetime.fromisoformat(p['datetime'])>=self.now-dt.timedelta(days=7) for p in r['data']))

    def test_gap_stale_missing_btc_and_invalid_values(self):
        self.add(48,100);self.add(47,None);self.add(12,120,None)
        r=self.read()
        self.assertTrue(r['meta']['stale']);self.assertEqual(r['meta']['invalid_count'],1)
        self.assertEqual(r['meta']['gap_count'],1)
        self.assertNotEqual(r['data'][0]['segment'],r['data'][-1]['segment'])
        self.assertIsNone(r['data'][-1]['btc'])

    def test_cash_flow_adjustment_and_endpoint_preservation(self):
        self.add(48,100);self.add(24,160);self.add(0,150)
        self.session.execute(cash_flows.insert(),[
            {'date':self.now-dt.timedelta(hours=49),'amount_usd':100,'note':'Opening'},
            {'date':self.now-dt.timedelta(hours=30),'amount_usd':50,'note':'Deposit'},
            {'date':self.now-dt.timedelta(hours=12),'amount_usd':-20,'note':'Withdrawal'}])
        r=self.read()
        self.assertEqual([p['adjusted_usd'] for p in r['data']],[100,110,120])
        self.assertEqual([p['total_value'] for p in r['data']],[100,160,150])

    def test_extremes_use_unsampled_hourly_history(self):
        for hours in range(100):self.add(hours,100+(100-hours))
        r=self.read(points=32)
        self.assertEqual(r['extremes']['largestDollarGain']['value'],24)

    def test_truncated_flows_disable_adjustment(self):
        self.add(24,100);self.add(0,100)
        self.session.execute(cash_flows.insert(),[{'date':self.now-dt.timedelta(minutes=i),'amount_usd':1,'note':''} for i in range(501)])
        r=self.read()
        self.assertEqual(len(r['flows']),500);self.assertTrue(r['meta']['flows_truncated'])
        self.assertTrue(all(p['adjusted_usd'] is None for p in r['data']))

    def test_input_validation(self):
        for amount in ['NaN','Infinity','0','-1','1000000000001','0.000000001']:
            with self.assertRaises(ValueError):parse_flow({'datetime':'2026-08-29T12:00','kind':'deposit','amount_usd':amount},self.now)
        for date in ['2027-01-01T00:00:00', '2026-08-29T12:00:00Z', '1999-01-01T00:00:00']:
            with self.assertRaises(ValueError):parse_flow({'datetime':date,'kind':'deposit','amount_usd':'1'},self.now)
        with self.assertRaises(ValueError):self.read('evil')
        with self.assertRaises(ValueError):self.read(points=5000)
        self.assertEqual(parse_flow({'datetime':'2026-08-29T12:00','kind':'withdrawal','amount_usd':'12.34'},self.now)['amount_usd'],Decimal('-12.34'))

    def test_api_login_csrf_add_delete_and_holdings_unchanged(self):
        client=self.app.test_client()
        self.assertEqual(client.get('/history').status_code,401)
        self.assertEqual(client.post('/history/flows',json={}).status_code,401)
        with client.session_transaction() as s:s['_user_id']='1';s['_fresh']=True
        self.assertEqual(client.get('/history?range=bad').status_code,400)
        self.assertEqual(client.get('/history?max_points=abc').status_code,400)
        token=client.get('/history').json['csrf_token']
        data={'datetime':(dt.datetime.now()-dt.timedelta(hours=1)).isoformat(),'kind':'deposit','amount_usd':'123.45','note':'<script>test</script>','request_id':'retry-test'}
        self.assertEqual(client.post('/history/flows',json=data).status_code,403)
        saved=client.post('/history/flows',json=data,headers={'X-CSRF-Token':token})
        self.assertEqual(saved.status_code,201)
        retried=client.post('/history/flows',json=data,headers={'X-CSRF-Token':token})
        self.assertEqual(retried.json['id'],saved.json['id'])
        result=client.get('/history').json
        self.assertEqual(result['flows'][0]['amount_usd'],123.45)
        self.assertEqual(result['data'],[])
        self.assertEqual(client.delete('/history/flows/'+str(saved.json['id']),headers={'X-CSRF-Token':token}).status_code,200)
        self.assertEqual(client.get('/history').json['flows'],[])

if __name__=='__main__':unittest.main()
