import json


def seg(o, d, dep_date, dep_t, arr_date, arr_t, mins, carrier, num, aircraft="Boeing 787", legroom="31 in"):
    x = [None] * 23
    x[3], x[6], x[8], x[10], x[11] = o, d, dep_t, arr_t, mins
    x[14], x[17], x[20], x[21] = legroom, aircraft, dep_date, arr_date
    x[22] = [carrier, num, None, f"Airline {carrier}"]
    return x


def itin(seller, segs, leg_minutes, layovers, price):
    f = [None] * 23
    f[0], f[1], f[2], f[9] = seller, [f"Airline {seller}"], segs, leg_minutes
    f[13] = [[m, "X", "X"] for m in layovers] or None
    return [f, None if price is None else [[None, price], "token"]]


def page(best, other=()):
    p = [None] * 32
    p[3] = [list(best) or None]
    p[2] = [list(other)] if other else None
    data = json.dumps(p)
    return ("<html><head><title>Google Flights</title></head><body>"
            f"<script class=\"ds:1\" nonce=\"x\">AF_initDataCallback({{key: 'ds:1', hash: '1', data:{data}, sideChannel: {{}}}});</script>"
            "</body></html>")


CONSENT = "<html><head><title>Before you continue</title></head><body>consent</body></html>"


class FakeTransport:
    """Returns queued (status, html) responses and records the params of every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, params):
        self.calls.append(params)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
