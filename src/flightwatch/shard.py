from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from flightwatch.crypto import decrypt_json, encrypt_json
from flightwatch.dates import date_pairs, hub_pairs_today, shard
from flightwatch.google.client import BudgetExceeded, SearchFailed
from flightwatch.google.parse import ConsentPageError
from flightwatch.model import Trip, trip_from_dict, trip_to_dict
from flightwatch.search import search_pair_all_parties
from flightwatch.selftransfer import search_hub_pair


@dataclass
class Coverage:
    pairs_planned: int = 0
    pairs_done: int = 0
    hub_pairs_planned: int = 0
    hub_pairs_done: int = 0
    requests: int = 0
    failures: list[str] = field(default_factory=list)
    stopped_early: bool = False
    shards_seen: int = 1
    shards_expected: int = 1
    window_pairs: int = 0          # pair×cabin searches in the whole window, across all shards
    window_hub_pairs: int = 0

    @property
    def complete(self) -> bool:
        return (not self.stopped_early and self.shards_seen == self.shards_expected
                and self.pairs_done == self.pairs_planned and self.hub_pairs_done == self.hub_pairs_planned)

    def merge(self, o: "Coverage") -> None:
        for f in ("pairs_planned", "pairs_done", "hub_pairs_planned", "hub_pairs_done", "requests"):
            setattr(self, f, getattr(self, f) + getattr(o, f))
        self.failures += o.failures
        self.stopped_early |= o.stopped_early


@dataclass
class ShardResult:
    trips: list[Trip]
    coverage: Coverage


def run_shard(client, cfg, today: date, index: int, total: int, limit_days: int | None = None) -> ShardResult:
    all_pairs = date_pairs(today, cfg, limit_days)
    pairs = shard(all_pairs, total, index)
    hub_pairs = shard(hub_pairs_today(all_pairs, today, cfg.hub_rotation_days), total, index)
    cabins = list(cfg.budget_pp_eur)
    all_hub = hub_pairs_today(all_pairs, today, cfg.hub_rotation_days)
    cov = Coverage(pairs_planned=len(pairs) * len(cabins),
                   hub_pairs_planned=len(hub_pairs) * len(cabins) * len(cfg.hubs),
                   window_pairs=len(all_pairs) * len(cabins),
                   window_hub_pairs=len(all_hub) * len(cabins) * len(cfg.hubs))
    trips: list[Trip] = []
    try:
        for d, r in pairs:
            for cabin in cabins:
                try:
                    trips += search_pair_all_parties(client, cfg, d, r, cabin)
                    cov.pairs_done += 1
                except SearchFailed as e:
                    cov.failures.append(f"{cabin} {d}→{r}: {e}")
        cache: dict = {}
        for hub in cfg.hubs:
            for d, r in hub_pairs:
                for cabin in cabins:
                    try:
                        for adults in cfg.parties:
                            trips += search_hub_pair(client, cfg, hub, d, r, cabin, adults, cache)
                        cov.hub_pairs_done += 1
                    except SearchFailed as e:
                        cov.failures.append(f"hub {hub} {cabin} {d}→{r}: {e}")
    except ConsentPageError as e:
        cov.stopped_early = True
        cov.failures.insert(0, f"Google consent page: {e}")
    except BudgetExceeded as e:
        cov.stopped_early = True
        cov.failures.insert(0, f"request budget reached: {e}")
    cov.requests = client.requests
    empty = getattr(client, "empty", 0)
    if client.requests >= 20 and empty >= 0.9 * client.requests:
        # Real results always list flights on most dates; this looks like a changed page, not empty skies
        cov.stopped_early = True
        cov.failures.insert(0, f"Google returned no flights for {empty} of {client.requests} searches; "
                               "its page layout may have changed")
    return ShardResult(trips, cov)


def save_shard(res: ShardResult, path: Path, key: str) -> None:
    path.write_bytes(encrypt_json({"trips": [trip_to_dict(t) for t in res.trips],
                                   "coverage": asdict(res.coverage)}, key))


def merge_shards(paths: list[Path], key: str, expected: int) -> ShardResult:
    trips: list[Trip] = []
    cov = Coverage(shards_seen=0, shards_expected=expected)
    for p in paths:
        data = decrypt_json(Path(p).read_bytes(), key)
        trips += [trip_from_dict(t) for t in data["trips"]]
        part = Coverage(**{k: v for k, v in data["coverage"].items() if k not in ("shards_seen", "shards_expected")})
        cov.merge(part)
        cov.window_pairs, cov.window_hub_pairs = part.window_pairs, part.window_hub_pairs
        cov.shards_seen += 1
    if cov.shards_seen < expected:
        cov.failures.insert(0, f"{expected - cov.shards_seen} of {expected} search jobs produced no results")
        # measure coverage against the whole window, not only the shards that arrived
        cov.pairs_planned = max(cov.window_pairs, 1)
        cov.hub_pairs_planned = cov.window_hub_pairs
    return ShardResult(trips, cov)
