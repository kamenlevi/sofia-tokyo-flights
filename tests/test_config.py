from flightwatch.config import load_config


def test_defaults_match_spec():
    cfg = load_config()
    assert cfg.origin == "SOF" and cfg.destination == "TYO"
    assert cfg.parties == (4, 3)
    assert cfg.budget_pp_eur == {"economy": 1200, "premium-economy": 1300}
    assert (cfg.stay_min, cfg.stay_max, cfg.stay_recommended) == (10, 21, 14)
    assert cfg.max_leg_minutes == 1200
    assert cfg.same_airport_min == 180 and cfg.city_change_min == 300
    assert frozenset({"IST", "SAW"}) in cfg.city_pairs
    assert cfg.max_requests_per_run // cfg.shards == 937
