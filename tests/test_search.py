from datetime import date
from googlefake import FakeTransport, page, itin, seg
from flightwatch.config import load_config
from flightwatch.google.client import GoogleClient
from flightwatch.search import search_pair, search_pair_all_parties

CFG = load_config()
D, R = date(2027, 3, 5), date(2027, 3, 20)


def out_opt(price, num="50"):
    return itin("TK", [seg("SOF", "IST", [2027, 3, 5], [9, 30], [2027, 3, 5], [12], 90, "TK", "1028"),
                       seg("IST", "NRT", [2027, 3, 5], [15, 25], [2027, 3, 6], [8, 40], 675, "TK", num)], 970, [205], price)


def ret_opt(price, num="51"):
    return itin("TK", [seg("NRT", "IST", [2027, 3, 20], [10], [2027, 3, 20], [17], 780, "TK", num),
                       seg("IST", "SOF", [2027, 3, 20], [19], [2027, 3, 20], [20, 30], 90, "TK", "1027")], 1050, [120], price)


def make(responses):
    t = FakeTransport([(200, r) for r in responses])
    return GoogleClient(transport=t, min_interval=0), t


def test_cheap_outbound_gets_stage2_and_every_return_becomes_a_trip():
    g, t = make([page([out_opt(4400), out_opt(9000, "52")]), page([ret_opt(4400), ret_opt(4700, "53")])])
    res = search_pair(g, CFG, D, R, "economy", 4)
    assert res.min_pp == 1100
    assert len(t.calls) == 2                       # the €9,000 outbound is skipped: over budget × 1.10
    assert sorted(x.total_eur for x in res.trips) == [4400, 4700]
    assert res.trips[0].tickets[0].booking_url.startswith("https://www.google.com/travel/flights/booking?tfs=")


def test_nothing_near_budget_means_one_request():
    g, t = make([page([out_opt(8000)])])
    res = search_pair(g, CFG, D, R, "economy", 4)
    assert res.trips == [] and res.min_pp == 2000 and len(t.calls) == 1


def test_party_b_searched_only_when_party_a_within_1_5x():
    g, t = make([page([out_opt(6800)]),            # A: €1,700 pp is within 1.5 × €1,200, so search B
                 page([out_opt(3300)]), page([ret_opt(3300)])])   # B: €1,100 pp
    trips = search_pair_all_parties(g, CFG, D, R, "economy")
    assert [x.party for x in trips] == [3]
    g2, t2 = make([page([out_opt(9000)])])          # A: €2,250 pp, so B is not searched
    assert search_pair_all_parties(g2, CFG, D, R, "economy") == [] and len(t2.calls) == 1


def test_party_b_searched_when_party_a_finds_nothing():
    g, t = make([page([]), page([out_opt(3300)]), page([ret_opt(3300)])])
    trips = search_pair_all_parties(g, CFG, D, R, "economy")
    assert [x.party for x in trips] == [3]
