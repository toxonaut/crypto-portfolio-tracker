import datetime as dt
import unittest
from types import SimpleNamespace
from flask import Flask
from flask_login import LoginManager
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from composition_history import compositions, save_composition, create_composition_blueprint


class CompositionTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        compositions.create(self.engine)
        self.session=Session(self.engine)
        self.app=Flask(__name__);self.app.secret_key='test';self.app.config['LOGIN_DISABLED']=True
        LoginManager(self.app)
        self.app.register_blueprint(create_composition_blueprint(SimpleNamespace(session=self.session)))
        self.client=self.app.test_client()
    def tearDown(self):
        self.session.close();self.engine.dispose()
    def test_immutable_signed_positions_and_transaction_rollback(self):
        row=SimpleNamespace(coin_id='bitcoin',source='Loan',amount=-2)
        save_composition(self.session,1,dt.datetime.now(),[row],{'bitcoin':100},-200)
        self.session.commit();row.amount=123;row.source='Renamed'
        saved=self.session.execute(select(compositions)).mappings().one()
        self.assertEqual(saved['positions'][0],dict(coin_id='bitcoin',source='Loan',amount=-2,price_usd=100,value_usd=-200))
        save_composition(self.session,2,dt.datetime.now(),[row],{'bitcoin':100},12300)
        self.session.rollback()
        self.assertEqual(len(self.session.execute(select(compositions)).all()),1)
    def test_bounded_pages_filters_and_no_fabricated_legacy_data(self):
        self.assertEqual(self.client.get('/history/composition').json['data'],[])
        now=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        self.session.execute(compositions.insert(),[dict(history_id=i,date=now-dt.timedelta(minutes=206-i),total_value=1,positions=[]) for i in range(1,206)])
        self.session.execute(compositions.insert().values(history_id=206,date=now-dt.timedelta(days=60),total_value=1,positions=[]));self.session.commit()
        first=self.client.get('/history/composition?range=7').json
        self.assertEqual(len(first['data']),200);self.assertEqual(first['next_before'],6)
        self.assertEqual(first['data'][0]['history_id'],6);self.assertEqual(first['data'][-1]['history_id'],205)
        second=self.client.get('/history/composition?range=7&before=6').json
        self.assertEqual([r['history_id'] for r in second['data']],list(range(1,6)))
        self.assertIsNone(second['next_before'])
        self.assertEqual(self.client.get('/history/composition?range=all&before=6').json['data'][0]['history_id'],206)
        for query in ['range=bad','before=bad','before=-1']:
            self.assertEqual(self.client.get('/history/composition?'+query).status_code,400)

if __name__=='__main__':unittest.main()
