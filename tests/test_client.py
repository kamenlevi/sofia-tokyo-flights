import pytest
from googlefake import FakeTransport, page, itin, seg, CONSENT
from flightwatch.google.client import GoogleClient, SearchFailed, BudgetExceeded
from flightwatch.google.parse import ConsentPageError

OK = (200, page([itin("TK", [seg("SOF", "IST", [2027, 3, 5], [9, 30], [2027, 3, 5], [12], 90, "TK", "1")], 90, [], 500)]))


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def now(self):
        return self.t


def client(responses, **kw):
    c = Clock()
    t = FakeTransport(responses)
    return GoogleClient(transport=t, sleep=c.sleep, clock=c.now, **kw), t, c


def test_throttles_between_requests():
    g, t, c = client([OK, OK], min_interval=1.0)
    g.search({"tfs": "a"})
    g.search({"tfs": "b"})
    assert c.sleeps == [1.0]
    assert g.requests == 2


def test_retries_then_succeeds():
    g, t, c = client([(503, ""), OK], min_interval=0)
    assert len(g.search({})) == 1
    assert g.requests == 2 and g.failures == 0


def test_gives_up_after_retries_and_counts_failure():
    g, t, c = client([(500, "")] * 3, min_interval=0)
    with pytest.raises(SearchFailed):
        g.search({})
    assert g.failures == 1


def test_consent_page_is_not_retried():
    g, t, c = client([(200, CONSENT)], min_interval=0)
    with pytest.raises(ConsentPageError):
        g.search({})
    assert g.requests == 1


def test_layout_change_counts_as_failure_not_empty():
    g, t, c = client([(200, "<html>new layout</html>")] * 3, min_interval=0)
    with pytest.raises(SearchFailed):
        g.search({})


def test_request_budget():
    g, t, c = client([OK], min_interval=0, max_requests=1)
    g.search({})
    with pytest.raises(BudgetExceeded):
        g.search({})


def test_counts_pages_with_flights_but_no_prices():
    nop = (200, page([itin("TK", [seg("SOF", "IST", [2027, 3, 5], [9, 30], [2027, 3, 5], [12], 90, "TK", "1")], 90, [], None)]))
    g, t, c = client([nop, OK], min_interval=0)
    g.search({})
    g.search({})
    assert g.priceless == 1 and g.empty == 0


def test_stops_at_deadline_so_partial_results_are_kept():
    g, t, c = client([OK, OK], min_interval=0, deadline_s=100)
    g.search({})
    c.t = 101
    with pytest.raises(BudgetExceeded, match="time"):
        g.search({})
