"""Pure flow-metric calculations (Little's Law family). No I/O, no Linear.

cycle time ~= WIP / throughput. Everything here is an input or output of that.
Leading (act now): WIP, work item age. Lagging (report/forecast): throughput, cycle time.
"""
from datetime import datetime, timezone


def _parse(ts):
    # Linear returns ISO 8601 like "2026-06-20T10:00:00.000Z"
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def cycle_times_days(completed):
    """Days from startedAt to completedAt. Skips cards that never hit 'started'."""
    out = []
    for i in completed:
        if i.get("startedAt") and i.get("completedAt"):
            d = (_parse(i["completedAt"]) - _parse(i["startedAt"])).total_seconds() / 86400
            out.append(d)
    return out


def percentile(values, p):
    """p in 0..100, linear interpolation between ranks. Empty -> None."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def throughput_per_week(completed_count, weeks):
    return completed_count / weeks if weeks else 0.0


def ages_days(active, now=None):
    """now - startedAt for in-flight cards. Returns each card + 'age_days'."""
    now = now or datetime.now(timezone.utc)
    out = []
    for i in active:
        if i.get("startedAt"):
            age = (now - _parse(i["startedAt"])).total_seconds() / 86400
            out.append({**i, "age_days": age})
    return sorted(out, key=lambda x: x["age_days"], reverse=True)
