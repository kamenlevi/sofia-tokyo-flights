from datetime import date, datetime, timezone
from flightwatch.config import load_config
from flightwatch.dates import today_in, add_months, date_pairs, shard, hub_pairs_today

CFG = load_config()


def test_sofia_date_at_cron_time():
    # 22:30 UTC on 31 Dec is already 1 Jan in Sofia
    assert today_in("Europe/Sofia", datetime(2026, 12, 31, 22, 30, tzinfo=timezone.utc)) == date(2027, 1, 1)


def test_add_months_clamps_day():
    assert add_months(date(2026, 5, 31), 9) == date(2027, 2, 28)


def test_window_bounds_and_gaps_across_new_year():
    pairs = date_pairs(date(2026, 12, 20), CFG)
    outs = sorted({d for d, _ in pairs})
    assert outs[0] == date(2027, 1, 3)              # +14 days
    assert outs[-1] == date(2027, 9, 20)            # +9 months
    gaps = sorted({(r - d).days for d, r in pairs})
    assert gaps == list(range(11, 24))              # landing is the next day or the one after
    assert len(pairs) == len(outs) * 13


def test_limit_days_for_smoke_runs():
    assert len(date_pairs(date(2026, 10, 11), CFG, limit_days=1)) == 13


def test_shards_partition_everything():
    pairs = date_pairs(date(2026, 10, 11), CFG)
    parts = [shard(pairs, 16, i) for i in range(16)]
    assert sum(len(p) for p in parts) == len(pairs)
    assert set().union(*map(set, parts)) == set(pairs)


def test_hub_rotation_covers_each_pair_once_per_week():
    days = [date(2026, 11, 1 + i) for i in range(7)]
    pair = (date(2027, 2, 10), date(2027, 2, 24))
    hits = [day for day in days if pair in hub_pairs_today([pair], day, 7)]
    assert len(hits) == 1
