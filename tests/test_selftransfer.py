from datetime import date
from googlefake import FakeTransport, page, itin, seg
from flightwatch.config import load_config
from flightwatch.google.client import GoogleClient
from flightwatch.selftransfer import search_hub_pair, join
from flightwatch.google.parse import parse_options

CFG = load_config()

LH_OUT = itin("TK", [seg("IST", "NRT", [2027, 3, 5], [15, 25], [2027, 3, 6], [8, 40], 675, "TK", "50")], 675, [], 3000)
LH_RET = itin("TK", [seg("NRT", "IST", [2027, 3, 20], [10], [2027, 3, 20], [17], 780, "TK", "51")], 780, [], 3000)
FEED_OUT = itin("FB", [seg("SOF", "IST", [2027, 3, 5], [9], [2027, 3, 5], [11], 60, "FB", "471")], 60, [], 400)
FEED_RET = itin("FB", [seg("IST", "SOF", [2027, 3, 20], [20, 30], [2027, 3, 20], [21, 30], 60, "FB", "472")], 60, [], 400)


def test_join_computes_layover_and_total():
    a = parse_options(page([FEED_OUT]))[0].leg
    b = parse_options(page([LH_OUT]))[0].leg
    j = join(a, b)
    assert j.layovers == (265,)                    # 11:00 to 15:25
    assert j.minutes == 60 + 265 + 675


def test_hub_pair_builds_three_ticket_trip_and_fetches_feeders_lazily():
    t = FakeTransport([(200, page([LH_OUT])), (200, page([LH_RET])), (200, page([FEED_OUT])), (200, page([FEED_RET]))])
    g = GoogleClient(transport=t, min_interval=0)
    trips = search_hub_pair(g, CFG, "IST", date(2027, 3, 5), date(2027, 3, 20), "economy", 4, {})
    [trip] = trips
    assert [tk.seller for tk in trip.tickets] == ["FB", "TK", "FB"]
    assert trip.total_eur == 3800 and trip.self_transfer
    assert [s.code for s in trip.outbound.segments] == ["FB471", "TK50"]


def test_expensive_long_haul_skips_feeders():
    pricey = itin("TK", LH_OUT[0][2], 675, [], 6000)
    t = FakeTransport([(200, page([pricey]))])
    g = GoogleClient(transport=t, min_interval=0)
    assert search_hub_pair(g, CFG, "IST", date(2027, 3, 5), date(2027, 3, 20), "economy", 4, {}) == []
    assert len(t.calls) == 1


def test_long_haul_ticket_with_two_sellers_is_multi():
    ret_other = itin("NH", [seg("NRT", "IST", [2027, 3, 20], [10], [2027, 3, 20], [17], 780, "NH", "51")], 780, [], 3000)
    t = FakeTransport([(200, page([LH_OUT])), (200, page([ret_other])), (200, page([FEED_OUT])), (200, page([FEED_RET]))])
    [trip] = search_hub_pair(GoogleClient(transport=t, min_interval=0), CFG, "IST", date(2027, 3, 5), date(2027, 3, 20), "economy", 4, {})
    assert trip.tickets[1].seller == "multi"
