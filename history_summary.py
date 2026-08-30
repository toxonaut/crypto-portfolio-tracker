"""Bounded history lookups shared by the summary endpoint and offline tests."""
import datetime
import math
from sqlalchemy import select


def read_history_summary(session, table, now=None):
    # Existing writers store server-local naive datetimes; use the same clock.
    now = now or datetime.datetime.now()
    tolerance = datetime.timedelta(hours=12)
    comparisons = {}
    for name, days in [('change24h', 1), ('change7d', 7), ('change30d', 30)]:
        target = now - datetime.timedelta(days=days)
        base = select(table.c.date, table.c.total_value)
        before = session.execute(base.where(
            table.c.date >= target - tolerance, table.c.date <= target
        ).order_by(table.c.date.desc()).limit(1)).first()
        after = session.execute(base.where(
            table.c.date > target, table.c.date <= target + tolerance,
            table.c.date <= now
        ).order_by(table.c.date.asc()).limit(1)).first()
        candidates = [row for row in [before, after] if row is not None]
        row = min(candidates, key=lambda r: abs(r.date - target)) if candidates else None
        # Do not skip an invalid nearest sample and silently substitute a different one.
        if row is None or row.total_value is None or not math.isfinite(row.total_value) or row.total_value <= 0:
            comparisons[name] = None
        else:
            comparisons[name] = {
                'datetime': row.date.isoformat(),
                'total_value': row.total_value,
                'offset_seconds': (row.date - target).total_seconds(),
            }
    return {'as_of': now.isoformat(), 'tolerance_hours': 12, 'comparisons': comparisons}
