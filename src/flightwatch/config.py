import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Config:
    origin: str
    destination: str
    tokyo_airports: tuple[str, ...]
    timezone: str
    lead_days: int
    horizon_months: int
    stay_min: int
    stay_max: int
    stay_recommended: int
    max_leg_minutes: int
    max_segments_per_leg: int
    parties: tuple[int, ...]
    checked_bags: int
    stage2_margin: float
    party_b_margin: float
    min_request_interval_s: float
    max_requests_per_run: int
    shards: int
    hub_rotation_days: int
    hubs: tuple[str, ...]
    budget_pp_eur: dict[str, int]
    same_airport_min: int
    city_change_min: int
    city_pairs: tuple[frozenset[str], ...]
    notify_github_user: str = "kamenlevi"


def load_config(path: Path | None = None) -> Config:
    text = path.read_text() if path else resources.files("flightwatch.data").joinpath("config.toml").read_text()
    raw = tomllib.loads(text)
    st = raw.pop("self_transfer")
    raw.pop("hubs_disabled", None)
    fields = {k: tuple(v) if isinstance(v, list) else v for k, v in raw.items()}
    return Config(**fields,
                  same_airport_min=st["same_airport_min"],
                  city_change_min=st["city_change_min"],
                  city_pairs=tuple(frozenset(p) for p in st["city_pairs"]))
