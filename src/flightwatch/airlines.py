import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass(frozen=True)
class Layout:
    match: str
    cabin: str
    layout: str
    pitch_in: float | None
    width_in: float | None


@dataclass(frozen=True)
class Airline:
    code: str
    name: str
    site: str
    meals_longhaul: str | None
    meals_shorthaul: str | None
    paid_meal_eur: float | None
    extra_legroom: str | None
    extra_legroom_eur: tuple[int, int] | None
    exit_row_min_age: int | None
    source: str
    checked: str
    layouts: tuple[Layout, ...]


class AirlineTable:
    def __init__(self, airlines: dict[str, Airline]):
        self.airlines = airlines

    @classmethod
    def load(cls, path: Path | None = None) -> "AirlineTable":
        text = path.read_text() if path else resources.files("flightwatch.data").joinpath("airlines.toml").read_text()
        out = {}
        for code, a in tomllib.loads(text).items():
            lays = tuple(Layout(l["match"], l["cabin"], l["layout"], l.get("pitch_in"), l.get("width_in"))
                         for l in a.get("layouts", []))
            ele = a.get("extra_legroom_eur")
            out[code] = Airline(code, a["name"], a["site"], a.get("meals_longhaul"), a.get("meals_shorthaul"),
                                a.get("paid_meal_eur"), a.get("extra_legroom"), tuple(ele) if ele else None,
                                a.get("exit_row_min_age"), a["source"], a["checked"], lays)
        return cls(out)

    def get(self, code: str) -> Airline | None:
        return self.airlines.get(code)

    def layout_for(self, code: str, aircraft: str, cabin: str) -> Layout | None:
        a = self.get(code)
        if a is None:
            return None
        for lay in a.layouts:
            if lay.cabin == cabin and lay.match.lower() in aircraft.lower():
                return lay
        return None
