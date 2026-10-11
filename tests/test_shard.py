from datetime import date
from googlefake import FakeTransport, page, CONSENT
from flightwatch.config import load_config
from flightwatch.crypto import new_key, encrypt_json, decrypt_json
from flightwatch.google.client import GoogleClient
from flightwatch.shard import run_shard, save_shard, merge_shards, Coverage
from dataclasses import replace

CFG = replace(load_config(), hubs=())


def test_crypto_round_trip():
    k = new_key()
    assert decrypt_json(encrypt_json({"a": 1}, k), k) == {"a": 1}


def test_shard_with_no_flights_is_complete_and_empty():
    cfg = replace(CFG, horizon_months=0, lead_days=0)          # window = today only: 13 pairs × 2 cabins
    t = FakeTransport([(200, page([]))] * 26)
    res = run_shard(GoogleClient(transport=t, min_interval=0), cfg, date(2027, 1, 10), 0, 1)
    assert res.trips == [] and res.coverage.pairs_planned == 26 and res.coverage.pairs_done == 26


def test_failures_are_recorded_and_consent_stops_shard():
    cfg = replace(CFG, horizon_months=0, lead_days=0)
    t = FakeTransport([(200, CONSENT)])
    res = run_shard(GoogleClient(transport=t, min_interval=0), cfg, date(2027, 1, 10), 0, 1)
    assert res.coverage.stopped_early and "consent" in res.coverage.failures[0].lower()
    assert not res.coverage.complete


def test_merge_flags_missing_shards(tmp_path):
    k = new_key()
    cfg = replace(CFG, horizon_months=0, lead_days=0)
    t = FakeTransport([(200, page([]))] * 26)
    res = run_shard(GoogleClient(transport=t, min_interval=0), cfg, date(2027, 1, 10), 0, 1)
    save_shard(res, tmp_path / "shard-0.bin", k)
    merged = merge_shards([tmp_path / "shard-0.bin"], k, expected=2)
    assert merged.coverage.shards_seen == 1 and not merged.coverage.complete
