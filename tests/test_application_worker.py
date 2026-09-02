"""Full application smoke test, isolated from .env and production databases."""
import subprocess
import sys
import unittest


class ApplicationWorkerTest(unittest.TestCase):
    def test_real_application_routes_and_cookie_free_worker(self):
        script = r'''
import os, time
from unittest.mock import patch
from types import SimpleNamespace
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['WORKER_KEY']='integration-test-key-01234567890123456789'
os.environ['SECRET_KEY']='isolated-test-session-key'
os.environ['HISTORY_INTERVAL_SECONDS']='3600'
with patch('dotenv.load_dotenv',return_value=False):
    import app as module
with module.app.app_context():
    module.db.session.add(module.Portfolio(coin_id='bitcoin',source='Test wallet',amount=2,apy=0))
    module.db.session.commit()
client=module.app.test_client()
assert client.get('/health').status_code==200
assert client.get('/history/composition').status_code==302
assert client.get('/experimental-portfolio').status_code==302
assert client.get('/api/experimental/kraken-portfolio').status_code==302
assert client.get('/new-portfolio/history/summary').status_code==302
assert client.post('/api/new-portfolio/manual',json={}).status_code==302
assert client.post('/worker_api/snapshot',json={'slot':int(time.time())//3600*3600}).status_code==401
assert client.post('/worker_api/new-portfolio-snapshot',json={'slot':int(time.time())//3600*3600}).status_code==401
reply=SimpleNamespace(status_code=200,json=lambda:{'bitcoin':{'usd':100,'last_updated_at':time.time()}})
with patch('snapshot_service.requests.get',return_value=reply):
    response=client.post('/worker_api/snapshot',json={'slot':int(time.time())//3600*3600},headers={'X-Worker-Key':os.environ['WORKER_KEY']})
    assert response.status_code==200, response.json
    repeat=client.post('/worker_api/snapshot',json={'slot':int(time.time())//3600*3600},headers={'X-Worker-Key':os.environ['WORKER_KEY']})
    assert repeat.json['duplicate'] is True
routes={rule.rule for rule in module.app.url_map.iter_rules()}
for path in ['/worker_portfolio','/worker_add_history','/api/portfolio','/api/add_history','/api/update_worker_status','/worker_api/portfolio','/worker_api/add_history']:
    assert path not in routes, path
with module.app.app_context():
    assert module.PortfolioHistory.query.count()==1
    assert module.PortfolioHistory.query.first().total_value==200
# Exercise authenticated UI endpoints without real Google OAuth in this isolated test.
with module.app.app_context():
    user=module.User(email='test@example.invalid',name='Test')
    module.db.session.add(user);module.db.session.commit();uid=user.id
with client.session_transaction() as session:
    session['_user_id']=str(uid);session['_fresh']=True
quotes={'bitcoin':{'usd':None,'status':'missing','source':None,'as_of':None,'cached':False}}
with patch('price_data.prices.read',return_value=quotes):
    response=client.get('/portfolio')
    assert response.status_code==200, response.json
    assert response.json['total_value'] is None
    assert response.json['data']['bitcoin']['price'] is None
    assert response.json['total_monthly_yield'] is None
    assert response.json['price_quality']['missing']==['bitcoin']
quotes['bitcoin'].update(usd=100,status='stale')
with patch('price_data.prices.read',return_value=quotes):
    response=client.get('/portfolio')
    assert response.json['total_value']==200
    assert response.json['price_error']
with patch('snapshot_service.fresh_prices',return_value={'bitcoin':100}):
    response=client.post('/add_history',json={'total_value':999999,'btc_value':99,'actual_btc':99})
    assert response.status_code==200, response.json
with module.app.app_context():
    assert module.PortfolioHistory.query.order_by(module.PortfolioHistory.id.desc()).first().total_value==200
    count=module.PortfolioHistory.query.count()
from snapshot_service import SnapshotUnavailable
with patch('snapshot_service.fresh_prices',side_effect=SnapshotUnavailable('Prices unavailable')):
    assert client.post('/add_history',json={}).status_code==503
with module.app.app_context():
    assert module.PortfolioHistory.query.count()==count
with patch('app.kraken_portfolio.read',return_value={'positions':[],'known_value_usd':0,'total_value_usd':0,'unpriced_assets':[],'complete':True,'as_of':'2026-09-01T00:00:00+00:00'}):
    assert client.get('/experimental-portfolio').status_code==200
    assert client.post('/api/new-portfolio/manual',json={'coin_id':'bitcoin','origin':'Ledger','amount':0,'apy':4}).status_code==400
    added=client.post('/api/new-portfolio/manual',json={'coin_id':'bitcoin','origin':'Ledger','amount':1.5,'apy':4})
    assert added.status_code==201,added.json
    manual_quotes={'bitcoin':{'usd':100,'image':'btc.png','status':'fresh'}}
    with patch('price_data.prices.read',return_value=manual_quotes):
        kraken=client.get('/api/experimental/kraken-portfolio')
        new_overview=client.get('/api/new-portfolio/overview')
    assert kraken.status_code==200 and kraken.json['data']['complete'] is True
    assert kraken.json['data']['total_value_usd']==150
    assert kraken.json['data']['positions'][0]['origin']=='Ledger'
    assert new_overview.status_code==200,new_overview.json
    assert new_overview.json['data']['total_value_usd']==150
    assert new_overview.json['data']['btc_value']==1.5
    assert new_overview.json['data']['monthly_yield_usd']==0.5
    with patch('price_data.prices.read',return_value=manual_quotes):
        snapshot=client.post('/worker_api/new-portfolio-snapshot',json={'slot':int(time.time())//3600*3600},headers={'X-Worker-Key':os.environ['WORKER_KEY']})
        assert snapshot.status_code==200,snapshot.json
        repeat=client.post('/worker_api/new-portfolio-snapshot',json={'slot':int(time.time())//3600*3600},headers={'X-Worker-Key':os.environ['WORKER_KEY']})
        assert repeat.json['duplicate'] is True
    assert client.get('/new-portfolio/history/summary').status_code==200
    with module.app.app_context():
        assert module.NewPortfolioHistory.query.count()==1
        assert module.NewPortfolioHistory.query.first().total_value==150
        assert module.db.session.execute(module.db.select(module.new_compositions)).first() is not None
    updated=client.patch('/api/new-portfolio/manual/'+str(added.json['id']),json={'origin':'Cold wallet','amount':2,'apy':5.5})
    assert updated.status_code==200,updated.json
    with module.app.app_context():
        saved=module.NewPortfolioEntry.query.get(added.json['id'])
        assert (saved.origin,saved.amount,saved.apy)==('Cold wallet',2,5.5)
    assert client.delete('/api/new-portfolio/manual/'+str(added.json['id'])).status_code==200
    with module.app.app_context(): assert module.NewPortfolioEntry.query.count()==0
response=client.get('/history/composition?range=all')
assert response.status_code==200
assert len(response.json['data'])==1
for row in response.json['data']:
    assert row['positions'][0]['source']=='Ledger'
    assert row['positions'][0]['amount']==1.5
    assert sum(p['value_usd'] for p in row['positions'])==row['total_value']==150
print('Full application price quality, worker and composition integration passed')
'''
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
