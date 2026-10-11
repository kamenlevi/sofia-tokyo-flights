import time
from collections.abc import Callable

from flightwatch.google.parse import ConsentPageError, GoogleFormatError, Option, parse_options

URL = "https://www.google.com/travel/flights"
Transport = Callable[[dict[str, str]], tuple[int, str]]


class SearchFailed(Exception):
    """A search kept failing after retries."""


class BudgetExceeded(Exception):
    """This process reached its request budget."""


def primp_transport() -> Transport:
    from primp import Client
    c = Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)
    c.set_cookies("https://www.google.com", {"SOCS": "CAI"})   # consent: reject all

    def get(params: dict[str, str]) -> tuple[int, str]:
        r = c.get(URL, params=params)
        return r.status_code, r.text
    return get


class GoogleClient:
    def __init__(self, transport: Transport | None = None, min_interval: float = 1.0, max_requests: int = 937,
                 retries: int = 3, sleep=time.sleep, clock=time.monotonic):
        self.transport = transport or primp_transport()
        self.min_interval = min_interval
        self.max_requests = max_requests
        self.retries = retries
        self.sleep = sleep
        self.clock = clock
        self.requests = 0
        self.failures = 0
        self._last: float | None = None

    def _throttle(self) -> None:
        if self._last is not None:
            wait = self._last + self.min_interval - self.clock()
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()

    def search(self, params: dict[str, str]) -> list[Option]:
        last = "no attempt"
        for attempt in range(self.retries):
            if self.requests >= self.max_requests:
                raise BudgetExceeded(f"{self.requests} requests made")
            self._throttle()
            self.requests += 1
            try:
                status, text = self.transport(params)
                if status == 200:
                    return parse_options(text)
                last = f"HTTP {status}"
                backoff = 60 * (attempt + 1) if status == 429 else 5 * 2 ** attempt
            except ConsentPageError:
                raise
            except GoogleFormatError as e:
                last, backoff = str(e), 5 * 2 ** attempt
            except Exception as e:  # network errors
                last, backoff = f"{type(e).__name__}: {e}", 5 * 2 ** attempt
            if attempt < self.retries - 1:
                self.sleep(backoff)
        self.failures += 1
        raise SearchFailed(last)
