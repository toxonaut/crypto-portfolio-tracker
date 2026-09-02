"""Shared validation and scheduling helpers for portfolio snapshots."""
import datetime as dt
import math
import os


class SnapshotUnavailable(Exception):
    pass


def worker_key():
    key = os.environ.get('WORKER_KEY', '')
    return key if len(key) >= 32 and key != 'default_worker_key' else None


def snapshot_interval():
    try:
        interval = int(os.environ.get('HISTORY_INTERVAL_SECONDS', '3600'))
    except ValueError:
        raise SnapshotUnavailable('Invalid snapshot interval configuration.')
    if not 300 <= interval <= 86400:
        raise SnapshotUnavailable('Snapshot interval must be between 300 and 86400 seconds.')
    return interval


def utcnow():
    # Existing database uses naive timestamps; production runs UTC.
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def valid_positive(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
