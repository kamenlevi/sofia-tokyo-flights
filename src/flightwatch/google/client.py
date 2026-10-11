URL = "https://www.google.com/travel/flights"


def primp_transport():
    from primp import Client
    c = Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)
    c.set_cookies("https://www.google.com", {"SOCS": "CAI"})   # consent: reject all

    def get(params: dict[str, str]) -> tuple[int, str]:
        r = c.get(URL, params=params)
        return r.status_code, r.text
    return get
