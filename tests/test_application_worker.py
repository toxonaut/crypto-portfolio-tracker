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
assert client.post('/worker_api/snapshot',json={'slot':int(time.time())//3600*3600}).status_code==401
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
print('Full application worker integration passed')
'''
        result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
