"""Scheduled snapshot requester. No browser cookies or database credentials needed."""
import logging
import os
import signal
import threading
import time
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv

logger = logging.getLogger('portfolio_worker')


def run_cycle(http, base_url, key, interval, clock=time.time, wait=lambda seconds: time.sleep(seconds), attempts=4):
    slot = int(clock()) // interval * interval
    for path in ('/worker_api/snapshot','/worker_api/new-portfolio-snapshot'):
        confirmed=False
        for attempt in range(attempts):
            try:
                response=http.post(base_url.rstrip('/')+path,json={'slot':slot},headers={'X-Worker-Key':key},timeout=(5,90),allow_redirects=False)
                if response.status_code==200:
                    data=response.json()
                    if data.get('success') is True and isinstance(data.get('history_id'),int):
                        logger.info('%s confirmed%s (id=%s)',path,' (already recorded)' if data.get('duplicate') else '',data['history_id']);confirmed=True;break
                if response.status_code in (400,401,403) or 300<=response.status_code<400:
                    logger.error('Snapshot rejected (HTTP %s). Check WORKER_KEY, BASE_URL and interval configuration.',response.status_code);return False
                logger.warning('Snapshot temporarily unavailable (HTTP %s), attempt %s/%s.',response.status_code,attempt+1,attempts)
            except (requests.RequestException,ValueError,TypeError,AttributeError):
                logger.warning('Snapshot request failed, attempt %s/%s.',attempt+1,attempts)
            if attempt+1<attempts and wait(min(5*2**attempt,30)):return False
        if not confirmed:return False
    return True


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    key = os.environ.get('WORKER_KEY', '')
    if len(key) < 32 or key == 'default_worker_key':
        logger.error('Set a dedicated WORKER_KEY of at least 32 characters on both services. Browser session cookies are not used.')
        return 1
    base_url = os.environ.get('BASE_URL', 'https://crypto-tracker.up.railway.app').rstrip('/')
    parsed = urlparse(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not (parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1'))):
        logger.error('BASE_URL must be HTTPS (HTTP allowed only for local testing).')
        return 1
    try:
        interval = int(os.environ.get('HISTORY_INTERVAL_SECONDS', '3600'))
        delay = int(os.environ.get('INITIAL_DELAY_SECONDS', '10'))
        if not 300 <= interval <= 86400 or not 0 <= delay <= 300: raise ValueError()
    except ValueError:
        logger.error('Invalid history interval or initial delay.')
        return 1
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, lambda *_: stop.set())
    if stop.wait(delay): return 0
    with requests.Session() as http:
        while not stop.is_set():
            success = run_cycle(http, base_url, key, interval, wait=stop.wait)
            # Align successful runs to UTC slots; retry failures after one minute.
            wait_for = max(1, interval-time.time()%interval) if success else 60
            logger.info('Next snapshot attempt in %.0f seconds.', wait_for)
            if stop.wait(wait_for): break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
