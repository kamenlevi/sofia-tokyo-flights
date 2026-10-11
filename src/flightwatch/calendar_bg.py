import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class DaysOff:
    ranges: tuple[tuple[date, date], ...]
    school_year_end: date
    source: str

    @classmethod
    def load(cls, path: Path | None = None) -> "DaysOff":
        text = (path.read_text() if path else
                resources.files("flightwatch.data").joinpath("bg_calendar_2026_27.toml").read_text())
        raw = tomllib.loads(text)
        return cls(tuple((date.fromisoformat(a), date.fromisoformat(b)) for a, b in raw["off"]),
                   date.fromisoformat(raw["school_year_end"]), raw["source"])

    def is_off(self, d: date) -> bool:
        return d.weekday() >= 5 or d > self.school_year_end or any(a <= d <= b for a, b in self.ranges)

    def school_days_missed(self, first: date, last: date) -> int:
        return sum(1 for i in range((last - first).days + 1) if not self.is_off(first + timedelta(days=i)))
