import datetime as dt
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import requests
from flask import Flask, request, redirect
from flask_login import LoginManager, UserMixin, current_user
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, DateTime, Float, String, select, func
from sqlalchemy.orm import Session
from snapshot_service import (create_snapshot_blueprint, initialize_snapshot_tables, health, receipts,
                              fresh_prices, SnapshotUnavailable, health_data)
from worker import run_cycle

KEY = 'test-only-dedicated-secret-0123456789'


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ, {'WORKER_KEY':KEY,'HISTORY_INTERVAL_SECONDS':'3600'})
        self.env.start()
        self.engine=create_engine('sqlite://')
        metadata=MetaData()
        self.portfolio=Table('portfolio',metadata,Column('id',Integer,primary_key=True),Column('coin_id',String),Column('amount',Float))
        self.history=Table('portfolio_history',metadata,Column('id',Integer,primary_key=True),Column('date',DateTime),Column('total_value',Float),Column('btc',Float),Column('actual_btc',Float))
        metadata.create_all(self.engine);initialize_snapshot_tables(self.engine)
        self.session=Session(self.engine)
        self.session.execute(self.portfolio.insert(),[{'coin_id':'bitcoin','amount':2},{'coin_id':'ethereum','amount':3}]);self.session.commit()
        self.prices=Mock(return_value={'bitcoin':100,'ethereum':10})
        self.app=Flask(__name__);self.app.secret_key='test-only'
        manager=LoginManager(self.app);user=UserMixin();user.id='1';manager.user_loader(lambda id:user)
        self.app.register_blueprint(create_snapshot_blueprint(SimpleNamespace(session=self.session),self.portfolio,self.history,self.prices))
        # Compile the actual global guard to catch accidental cookie interception.
        import ast
        from pathlib import Path
        definition=next(n for n in ast.parse(Path('app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='before_request')
        exec(compile(ast.Module(body=[definition],type_ignores=[]),'app.py','exec'),dict(app=self.app,request=request,current_user=current_user,redirect=redirect,url_for=lambda _: '/login'))
        self.client=self.app.test_client()
        self.slot=int(time.time())//3600*3600
    def tearDown(self):
        self.session.close();self.engine.dispose();self.env.stop()
    def post(self,key=KEY,slot=None):
        return self.client.post('/worker_api/snapshot',json={'slot':self.slot if slot is None else slot},headers={'X-Worker-Key':key})
    def count(self,table):return self.session.execute(select(func.count()).select_from(table)).scalar()

    def test_cookie_free_snapshot_is_complete_and_retry_is_idempotent(self):
        response=self.post();self.assertEqual(response.status_code,200)
        self.assertFalse(response.json['duplicate']);self.assertEqual(self.count(self.history),1)
        value=self.session.execute(select(self.history)).mappings().one()
        self.assertEqual(value['total_value'],230);self.assertEqual(value['btc'],2.3);self.assertEqual(value['actual_btc'],2)
        retry=self.post();self.assertTrue(retry.json['duplicate']);self.assertEqual(retry.json['history_id'],response.json['history_id'])
        self.assertEqual(self.count(self.history),1);self.prices.assert_called_once()
        self.assertIsNotNone(health_data(self.session)['last_success'])

    def test_auth_fails_closed_no_cookie_bypass(self):
        self.assertEqual(self.post('').status_code,401)
        self.assertEqual(self.post('default_worker_key').status_code,401)
        with self.client.session_transaction() as session:session['_user_id']='1'
        self.assertEqual(self.post('wrong').status_code,401)
        with patch.dict(os.environ,{'WORKER_KEY':''}):self.assertEqual(self.post().status_code,503)
        self.assertEqual(self.count(self.history),0)

    def test_status_requires_login_and_reports_overdue(self):
        self.assertEqual(self.client.get('/worker_status').status_code,401)
        with self.client.session_transaction() as session:session['_user_id']='1'
        data=self.client.get('/worker_status').json['data']
        self.assertTrue(data['overdue']);self.assertTrue(data['configured'])
        self.post();data=self.client.get('/worker_status').json['data'];self.assertFalse(data['overdue'])
        self.assertNotIn(KEY,str(data))

    def test_bad_prices_cannot_create_partial_snapshot_and_recovery_works(self):
        for prices in [{'bitcoin':100},{'bitcoin':0,'ethereum':10},{'bitcoin':100,'ethereum':float('nan')}]:
            self.prices.return_value=prices
            self.assertEqual(self.post().status_code,503)
            self.assertEqual(self.count(self.history),0);self.assertEqual(self.count(receipts),0)
            self.assertIsNotNone(health_data(self.session)['last_error'])
        self.prices.return_value={'bitcoin':100,'ethereum':10}
        self.assertEqual(self.post().status_code,200);self.assertIsNone(health_data(self.session)['last_error'])

    def test_price_exception_and_concurrent_edit_are_not_saved(self):
        self.prices.side_effect=SnapshotUnavailable('Provider unavailable')
        self.assertEqual(self.post().status_code,503)
        def edit(ids):
            self.session.execute(self.portfolio.update().where(self.portfolio.c.coin_id=='bitcoin').values(amount=3));self.session.commit()
            return {'bitcoin':100,'ethereum':10}
        self.prices.side_effect=edit
        self.assertEqual(self.post().status_code,503);self.assertEqual(self.count(self.history),0)

    def test_slots_and_interval_mismatch_rejected(self):
        self.assertEqual(self.post(slot=self.slot-7200).status_code,400)
        self.assertEqual(self.post(slot=self.slot+3600).status_code,400)
        self.assertEqual(self.post(slot=True).status_code,400)
        self.assertEqual(self.post(slot=self.slot-3600).status_code,200)

    def test_lost_response_retries_same_slot_without_duplicate(self):
        class Http:
            def __init__(inner):inner.calls=[]
            def post(inner,url,**kwargs):
                inner.calls.append(kwargs)
                response=self.client.post('/worker_api/snapshot',json=kwargs['json'],headers=kwargs['headers'])
                if len(inner.calls)==1:raise requests.Timeout()
                return SimpleNamespace(status_code=response.status_code,json=lambda:response.json)
        http=Http()
        self.assertTrue(run_cycle(http,'https://test.invalid',KEY,3600,clock=lambda:self.slot+1,wait=lambda _:False))
        self.assertEqual(self.count(self.history),1);self.assertEqual(len(http.calls),2)
        self.assertEqual(http.calls[0]['json'],http.calls[1]['json'])
        self.assertFalse(http.calls[0]['allow_redirects'])
        self.assertNotIn('cookies',http.calls[0])


class ProviderAndWorkerTests(unittest.TestCase):
    def test_fresh_prices_missing_stale_and_invalid_json(self):
        now=time.time();http=Mock()
        http.get.return_value=SimpleNamespace(status_code=200,json=lambda:{'bitcoin':{'usd':100,'last_updated_at':now}})
        self.assertEqual(fresh_prices({'bitcoin'},http,now),{'bitcoin':100})
        for data in [{}, {'bitcoin':{'usd':100,'last_updated_at':now-901}}, {'bitcoin':{'usd':True,'last_updated_at':now}}, []]:
            http.get.return_value=SimpleNamespace(status_code=200,json=lambda:data)
            with self.assertRaises(SnapshotUnavailable):fresh_prices({'bitcoin'},http,now)

    def test_forex_valid_weekend_and_stale(self):
        now=time.time();http=Mock()
        today=dt.datetime.fromtimestamp(now,dt.timezone.utc).date()
        http.get.return_value=SimpleNamespace(status_code=200,json=lambda:{'rates':{'USD':1.1},'date':(today-dt.timedelta(days=2)).isoformat()})
        self.assertEqual(fresh_prices({'CHF'},http,now),{'CHF':1.1})
        http.get.return_value=SimpleNamespace(status_code=200,json=lambda:{'rates':{'USD':1.1},'date':(today-dt.timedelta(days=8)).isoformat()})
        with self.assertRaises(SnapshotUnavailable):fresh_prices({'CHF'},http,now)

    def test_backoff_stable_slot_and_auth_redirect_stop(self):
        http=Mock();http.post.return_value=SimpleNamespace(status_code=503,json=lambda:{'success':False})
        waits=[]
        self.assertFalse(run_cycle(http,'https://test.invalid',KEY,3600,clock=lambda:7201,wait=lambda s:waits.append(s)))
        self.assertEqual(waits,[5,10,20]);self.assertEqual(http.post.call_count,4)
        self.assertTrue(all(call.kwargs['json']=={'slot':7200} for call in http.post.call_args_list))
        for status in [302,401,403,400]:
            http.reset_mock();http.post.return_value=SimpleNamespace(status_code=status)
            self.assertFalse(run_cycle(http,'https://test.invalid',KEY,3600,wait=lambda _:False));self.assertEqual(http.post.call_count,1)

if __name__=='__main__':unittest.main()
