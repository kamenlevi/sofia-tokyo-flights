import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def today_in(tz: str, now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(tz)).date()


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def date_pairs(today: date, cfg, limit_days: int | None = None) -> list[tuple[date, date]]:
    """Every (leave Sofia, leave Tokyo) date pair to search. Landing in Tokyo is the next day, or the
    day after for late-evening departures, so the gap runs from stay_min + 1 to stay_max + 2."""
    first, last = today + timedelta(days=cfg.lead_days), add_months(today, cfg.horizon_months)
    if limit_days is not None:
        last = min(last, first + timedelta(days=limit_days - 1))
    pairs, d = [], first
    while d <= last:
        pairs += [(d, d + timedelta(days=g)) for g in range(cfg.stay_min + 1, cfg.stay_max + 3)]
        d += timedelta(days=1)
    return pairs


def shard(items: list, total: int, index: int) -> list:
    return items[index::total]


def hub_pairs_today(pairs: list[tuple[date, date]], today: date, days: int) -> list[tuple[date, date]]:
    """Stable rotation: each pair is searched on exactly one day in every `days`-day cycle."""
    return [(d, r) for d, r in pairs if (d.toordinal() * 31 + (r - d).days) % days == today.toordinal() % days]
