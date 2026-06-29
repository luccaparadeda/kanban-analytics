"""Run: uv run python test_metrics.py  (asserts, no framework)."""
from datetime import datetime, timezone, timedelta
from metrics import cycle_times_days, percentile, throughput_per_week, ages_days


def test_cycle_times():
    c = [
        {"startedAt": "2026-06-01T00:00:00Z", "completedAt": "2026-06-06T00:00:00Z"},  # 5d
        {"startedAt": "2026-06-01T00:00:00Z", "completedAt": "2026-06-02T12:00:00Z"},  # 1.5d
        {"completedAt": "2026-06-02T00:00:00Z"},  # no startedAt -> skipped
    ]
    assert cycle_times_days(c) == [5.0, 1.5]


def test_percentile():
    assert percentile([], 50) is None
    assert percentile([4], 85) == 4.0
    assert percentile([1, 2, 3, 4, 5], 50) == 3.0
    # 85th pct of 1..5: k=(5-1)*0.85=3.4 -> 4 + (5-4)*0.4 = 4.4
    assert abs(percentile([1, 2, 3, 4, 5], 85) - 4.4) < 1e-9


def test_throughput():
    assert throughput_per_week(20, 4) == 5.0
    assert throughput_per_week(5, 0) == 0.0


def test_ages():
    now = datetime(2026, 6, 29, tzinfo=timezone.utc)
    active = [
        {"identifier": "GR-1", "startedAt": (now - timedelta(days=9)).isoformat()},
        {"identifier": "GR-2", "startedAt": (now - timedelta(days=2)).isoformat()},
        {"identifier": "GR-3"},  # not started -> skipped
    ]
    out = ages_days(active, now=now)
    assert [x["identifier"] for x in out] == ["GR-1", "GR-2"]  # sorted oldest first
    assert abs(out[0]["age_days"] - 9) < 1e-6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
    print("all passed")
