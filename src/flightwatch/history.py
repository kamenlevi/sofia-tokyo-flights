from datetime import date, timedelta
from pathlib import Path

from flightwatch.crypto import decrypt_json, encrypt_json

KEEP_DAYS = 60


def load(path: Path, key: str) -> dict:
    p = Path(path)
    return decrypt_json(p.read_bytes(), key) if p.exists() else {}


def save(path: Path, key: str, hist: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(encrypt_json(hist, key))


def _put(series: list, today: date, value: int) -> None:
    if series and series[-1][0] == today.isoformat():
        series[-1][1] = value
    else:
        series.append([today.isoformat(), value])


def record(hist: dict, entries: list[tuple[str, float]], today: date) -> None:
    trips = hist.setdefault("trips", {})
    for key, pp in entries:
        _put(trips.setdefault(key, []), today, round(pp))
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for key in [k for k, s in trips.items() if s[-1][0] < cutoff]:
        del trips[key]


def record_best(hist: dict, cabin: str, party: int, best_pp: float | None, today: date) -> None:
    if best_pp is not None:
        _put(hist.setdefault("best", {}).setdefault(f"{cabin}|{party}", []), today, round(best_pp))


def trend(hist: dict, key: str) -> str:
    s = hist.get("trips", {}).get(key, [])
    if len(s) < 2:
        return "new today"
    (d0, prev), (_, now) = s[-2], s[-1]
    if now == prev:
        return f"same as {d0}"
    return f"{'down' if now < prev else 'up'} €{abs(now - prev):,} since {d0}"
