import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class DayBreakdown:
    total: int
    weekdays: int
    weekend: int
    school_days: int
    holidays: tuple[tuple[date, str], ...]


@dataclass(frozen=True)
class DaysOff:
    ranges: tuple[tuple[date, date], ...]
    school_year_end: date
    next_school_year_start: date
    source: str
    holidays: tuple[tuple[date, str], ...] = ()     # official holidays as listed on почивнидни.com

    @classmethod
    def load(cls, path: Path | None = None) -> "DaysOff":
        text = (path.read_text() if path else
                resources.files("flightwatch.data").joinpath("bg_calendar_2026_27.toml").read_text())
        raw = tomllib.loads(text)
        return cls(tuple((date.fromisoformat(a), date.fromisoformat(b)) for a, b in raw["off"]),
                   date.fromisoformat(raw["school_year_end"]), date.fromisoformat(raw["next_school_year_start"]),
                   raw["source"], tuple((date.fromisoformat(d), name) for d, name in raw.get("holidays", [])))

    def is_off(self, d: date) -> bool:
        summer = self.school_year_end < d < self.next_school_year_start
        return d.weekday() >= 5 or summer or any(a <= d <= b for a, b in self.ranges)

    def school_days_missed(self, first: date, last: date) -> int:
        return sum(1 for i in range((last - first).days + 1) if not self.is_off(first + timedelta(days=i)))

    def breakdown(self, first: date, last: date) -> DayBreakdown:
        days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
        weekdays = sum(1 for d in days if d.weekday() < 5)
        return DayBreakdown(len(days), weekdays, len(days) - weekdays,
                            sum(1 for d in days if not self.is_off(d)),
                            tuple((d, n) for d, n in self.holidays if first <= d <= last))

