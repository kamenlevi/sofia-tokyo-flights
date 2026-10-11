from datetime import date
from flightwatch.crypto import new_key
from flightwatch.history import load, save, record, trend, record_best


def test_missing_file_is_empty(tmp_path):
    assert load(tmp_path / "h.bin", new_key()) == {}


def test_record_and_trend(tmp_path):
    k, h = new_key(), {}
    record(h, [("A", 1150.0)], date(2026, 10, 12))
    assert trend(h, "A") == "new today"
    record(h, [("A", 1100.0)], date(2026, 10, 13))
    assert trend(h, "A") == "down €50 since 2026-10-12"
    save(tmp_path / "h.bin", k, h)
    assert load(tmp_path / "h.bin", k) == h


def test_same_day_rerun_replaces_value():
    h = {}
    record(h, [("A", 1150.0)], date(2026, 10, 12))
    record(h, [("A", 1140.0)], date(2026, 10, 12))
    assert h["trips"]["A"] == [["2026-10-12", 1140]]


def test_best_per_day_series():
    h = {}
    record_best(h, "economy", 4, 1180.4, date(2026, 10, 12))
    assert h["best"]["economy|4"] == [["2026-10-12", 1180]]
