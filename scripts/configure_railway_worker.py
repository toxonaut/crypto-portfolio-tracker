#!/usr/bin/env python3
"""Stage cookie-free worker configuration; never print or commit service secrets.

Run after `railway login`, then deploy the tested application commit via GitHub.
Variable updates use --skip-deploys so old code is not restarted mid-configuration.
"""
import argparse
import json
import secrets
import subprocess


def call(args, value=None):
    result = subprocess.run(['railway', *args], input=value, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit('Railway operation failed. Confirm `railway login` and project access, then retry. No secret values were printed.')
    return result.stdout


def configure(project, environment, web_service, worker_service):
    call(['link','--project',project,'--environment',environment,'--service',web_service])
    def variables(service):
        return json.loads(call(['variable','list','--service',service,'--environment',environment,'--json']))
    web, worker = variables(web_service), variables(worker_service)
    candidates = [web.get('WORKER_KEY',''), worker.get('WORKER_KEY','')]
    session_secrets = [web.get('SECRET_KEY'), worker.get('SECRET_KEY')]
    key = next((k for k in candidates if isinstance(k,str) and len(k)>=32 and k!='default_worker_key' and k not in session_secrets), None) or secrets.token_urlsafe(48)
    interval = int(worker.get('HISTORY_INTERVAL_SECONDS','3600'))
    if not 300 <= interval <= 86400: raise SystemExit('Existing worker interval is invalid; choose 300–86400 seconds.')
    for service in (web_service, worker_service):
        call(['variable','set','WORKER_KEY','--stdin','--skip-deploys','--service',service,'--environment',environment],key)
        call(['variable','set',f'HISTORY_INTERVAL_SECONDS={interval}','--skip-deploys','--service',service,'--environment',environment])
    call(['variable','set','BASE_URL=https://crypto-tracker.up.railway.app','--skip-deploys','--service',worker_service,'--environment',environment])
    after_web, after_worker = variables(web_service), variables(worker_service)
    if not all(secrets.compare_digest(v.get('WORKER_KEY',''),key) for v in (after_web,after_worker)):
        raise SystemExit('Worker secret verification failed; do not deploy yet.')
    if not all(str(v.get('HISTORY_INTERVAL_SECONDS')) == str(interval) for v in (after_web,after_worker)):
        raise SystemExit('Worker interval verification failed; do not deploy yet.')
    print('Shared WORKER_KEY and matching interval verified on both services. Configuration staged without deployments. Deploy the tested GitHub commit next.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',default='d437d7b6-9761-4999-8971-88d84c685a68')
    parser.add_argument('--environment',default='c8000574-88ef-4bb2-b0bc-f1b3d7c34cae')
    parser.add_argument('--web-service',default='1a859ee9-9bf8-4599-a547-aa9e7ce94016')
    parser.add_argument('--worker-service',default='5d431bea-c2f5-477c-99a7-b99021f078e3')
    args=parser.parse_args()
    configure(args.project,args.environment,args.web_service,args.worker_service)
