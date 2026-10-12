from datetime import date
from html import escape

from flightwatch.enrich import Result, SegmentView
from flightwatch.history import trend


def rank(results: list[Result]) -> list[Result]:
    return sorted(results, key=lambda r: (bool(r.problems), r.school_days, r.price_pp))


def _eur(x: float) -> str:
    return f"€{x:,.0f}"


def _hm(m: int) -> str:
    return f"{m // 60}h{m % 60:02d}"


def _pct(cov) -> int:
    planned = cov.pairs_planned + cov.hub_pairs_planned
    return 100 if planned == 0 else round(100 * (cov.pairs_done + cov.hub_pairs_done) / planned)


def _coverage_line(cov) -> str:
    line = (f"Checked {cov.pairs_done:,} of {cov.pairs_planned:,} date pairs and "
            f"{cov.hub_pairs_done:,} of {cov.hub_pairs_planned:,} hub pairs ({_pct(cov)}%) with {cov.requests:,} requests.")
    if not cov.complete:
        line = "INCOMPLETE: some dates were not checked, so missing results do not mean no deals. " + line
    return line


def _seg_html(v: SegmentView) -> str:
    s = v.segment
    leg = f"{s.dep:%a %d %b %H:%M} {s.origin} → {s.arr:%a %d %b %H:%M} {s.destination}"
    legroom = escape(s.legroom or "legroom n/a")
    table = (f", {v.pitch_in:g}\" pitch" if v.pitch_in else "") + (f", {v.width_in:g}\" wide" if v.width_in else "")
    seats = ""
    if v.seat_plan:
        seats = f"<br><small>Seats ({v.layout}): {' '.join(v.seat_plan.seats)}, {v.seat_plan.note}, {v.seat_plan.windows} window</small>"
    elif v.segment.minutes >= 360:
        seats = "<br><small>Seat plan: layout not verified</small>"
    cabin = {1: "economy", 2: "premium economy", 3: "business", 4: "first"}.get(s.cabin, "")
    return (f"<div><b>{escape(s.code)}</b> {escape(s.airline)}, {escape(s.aircraft)}{', ' + cabin if cabin else ''}<br>{escape(leg)} ({_hm(s.minutes)})"
            f"<br><small>Legroom {legroom}{table}. Meals: {escape(v.meals)}</small>{seats}</div>")


def _leg_html(views, leg) -> str:
    parts = []
    for i, v in enumerate(views):
        parts.append(_seg_html(v))
        if i < len(leg.layovers):
            parts.append(f"<div class=lay>Connection at {escape(v.segment.destination)}: {_hm(leg.layovers[i])}</div>")
    parts.append(f"<div class=tot>Door to door {_hm(leg.minutes)}</div>")
    return "".join(parts)


def _row(r: Result, hist: dict) -> str:
    t = r.trip
    ok = not r.problems
    off = t.outbound.dep.weekday() in (4, 5)
    links = " ".join(f"<a href=\"{escape(u)}\">{escape(label)}</a>" for label, u in r.booking)
    warn = "".join(f"<li>{escape(p)}</li>" for p in r.problems)
    if t.self_transfer:
        warn += "<li>Separate tickets: if the first flight is late, the next airline will not rebook you.</li>"
    extra = "".join(f"<li>{escape(e)}</li>" for e in r.extra_legroom) or "<li>not verified</li>"
    return f"""<tr class="{'ok' if ok else 'near'}" data-cabin="{t.cabin}" data-party="{t.party}" data-school="{r.school_days}"
 data-rec="{int(r.recommended)}" data-st="{int(t.self_transfer)}" data-off="{int(off)}" data-price="{r.price_pp:.0f}">
<td data-v="{r.price_pp:.0f}"><b>{_eur(r.price_pp)}</b> pp<br>{_eur(r.price_pp * t.party)} total for {t.party}<br>
<small>23 kg bag included{', meals add ' + _eur(r.meal_addon_pp) + ' pp' if r.meal_addon_pp else ''}</small><br><small>{escape(trend(hist, t.key))}</small></td>
<td data-v="{t.outbound.dep:%Y%m%d}">{t.cabin.replace('-', ' ')}<br>{t.outbound.dep:%a %d %b} → {t.inbound.arr:%a %d %b %Y}<br>
<b>{t.stay_days} days</b> in Japan{' (recommended)' if r.recommended else ''}</td>
<td data-v="{r.school_days}">{r.school_days}</td>
<td>{_leg_html(r.outbound, t.outbound)}<div class=arr>Arrive Tokyo {t.outbound.arr:%a %d %b %H:%M}</div></td>
<td>{_leg_html(r.inbound, t.inbound)}<div class=arr>Arrive Sofia {t.inbound.arr:%a %d %b %H:%M}</div></td>
<td><ul>{extra}</ul></td>
<td>{links}<ul class=warn>{warn}</ul></td></tr>"""


STYLE = """
:root{--bg:#fff;--fg:#111;--mut:#666;--ok:#e8f6ec;--near:#fff6e0;--line:#ddd;--acc:#0b57d0}
@media (prefers-color-scheme: dark){:root{--bg:#111;--fg:#eee;--mut:#aaa;--ok:#12301c;--near:#33280c;--line:#333;--acc:#8ab4f8}}
body{background:var(--bg);color:var(--fg);font:14px/1.4 -apple-system,system-ui,sans-serif;margin:16px}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left}
th{cursor:pointer;position:sticky;top:0;background:var(--bg)}tr.ok{background:var(--ok)}tr.near{background:var(--near)}
small,.lay,.tot{color:var(--mut)}.arr{font-weight:600;margin-top:4px}a{color:var(--acc)}.warn{color:#b3261e}
.banner{padding:10px;border:1px solid var(--line);margin-bottom:12px}.filters label{margin-right:12px}
"""

SCRIPT = """
const rows=[...document.querySelectorAll('tbody tr')];
function apply(){const f=id=>document.getElementById(id);
 rows.forEach(r=>{let show=true;
  if(f('cabin').value&&r.dataset.cabin!==f('cabin').value)show=false;
  if(f('party').value&&r.dataset.party!==f('party').value)show=false;
  if(f('rec').checked&&r.dataset.rec!=='1')show=false;
  if(f('through').checked&&r.dataset.st==='1')show=false;
  if(f('off').checked&&r.dataset.off!=='1')show=false;
  if(f('ok').checked&&!r.classList.contains('ok'))show=false;
  if(f('school').value!==''&&+r.dataset.school>+f('school').value)show=false;
  r.style.display=show?'':'none';});}
document.querySelectorAll('.filters input,.filters select').forEach(e=>e.addEventListener('input',apply));
document.querySelectorAll('th[data-sort]').forEach((th,i)=>th.addEventListener('click',()=>{
 const tb=document.querySelector('tbody'),col=[...th.parentNode.children].indexOf(th),dir=th.dataset.dir=th.dataset.dir==='1'?'-1':'1';
 rows.sort((a,b)=>(+a.children[col].dataset.v-+b.children[col].dataset.v)*dir).forEach(r=>tb.appendChild(r));}));
apply();
"""


MAX_ROWS = 500   # ~2.5 MB; keeps the attachment far below Gmail's 25 MB limit


def render_html(results: list[Result], cov, today: date, hist: dict, calendar_source: str) -> str:
    everything = rank(results)
    ranked = everything[:MAX_ROWS]
    capped = (f"<p><b>Showing the best {MAX_ROWS} of {len(everything):,} trips</b> (fewest school days, then cheapest).</p>"
              if len(everything) > MAX_ROWS else "")
    failures = "".join(f"<li>{escape(f)}</li>" for f in cov.failures[:50])
    body = "".join(_row(r, hist) for r in ranked) or "<tr><td colspan=7>No trips within 10% of budget.</td></tr>"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Sofia–Tokyo flights</title><style>{STYLE}</style></head><body>
<h1>Sofia ↔ Tokyo, {today:%d %b %Y}</h1>
<div class=banner>{escape(_coverage_line(cov))}<ul>{failures}</ul>
<small>Prices from Google Flights (cheapest seller). The airline's own price can be a little higher; open the link to check.
Green rows are under budget (economy €1,200 / premium economy €1,300 per person, 23 kg bag included); yellow rows are within 10%.
School days use the official calendar: {escape(calendar_source)}. All of December counts as off.</small></div>
{capped}<div class=filters><label>Cabin <select id=cabin><option value="">all</option><option value=economy>economy</option>
<option value=premium-economy>premium economy</option></select></label>
<label>People <select id=party><option value="">all</option><option>4</option><option>3</option></select></label>
<label><input type=checkbox id=ok checked> under budget only</label>
<label><input type=checkbox id=rec> 14+ days only</label>
<label><input type=checkbox id=through> one ticket only</label>
<label><input type=checkbox id=off> leaves Fri/Sat</label>
<label>Max school days <input id=school type=number min=0 style="width:4em"></label></div>
<table><thead><tr><th data-sort>Price</th><th data-sort>Dates</th><th data-sort>School days</th><th>Outbound</th>
<th>Return</th><th>Extra legroom</th><th>Book</th></tr></thead><tbody>{body}</tbody></table>
<script>{SCRIPT}</script></body></html>"""


def _line(r: Result) -> str:
    t = r.trip
    codes = "+".join(s.code for s in t.outbound.segments) + " / " + "+".join(s.code for s in t.inbound.segments)
    return (f"{_eur(r.price_pp)} pp ({_eur(r.price_pp * t.party)} for {t.party}), {t.cabin.replace('-', ' ')}, "
            f"{t.outbound.dep:%a %d %b} → {t.inbound.arr:%a %d %b}, {t.stay_days} days, {r.school_days} school days, {codes}")


def render_email(results: list[Result], cov, today: date, hist: dict) -> tuple[str, str, str]:
    ranked = rank(results)
    deals = [r for r in ranked if not r.problems]
    if not cov.complete:
        subject = f"SOF–TYO: INCOMPLETE search ({_pct(cov)}% checked), {len(deals)} deal(s) found so far"
    elif deals:
        best = deals[0]
        subject = (f"SOF–TYO: {len(deals)} deal{'s' if len(deals) != 1 else ''} under budget, "
                   f"best {_eur(best.price_pp)} pp, {best.school_days} school days")
    else:
        cheapest = min((r.price_pp for r in ranked), default=None)
        subject = "SOF–TYO: no deals under budget today" + (f" (closest {_eur(cheapest)} pp)" if cheapest else "")
    top = deals[:10] or ranked[:5]
    text = "\n".join([_coverage_line(cov), *cov.failures[:10], "", *(_line(r) for r in top), "",
                      "Full report attached (open report.html)."])
    html = (f"<p>{escape(_coverage_line(cov))}</p><ol>"
            + "".join(f"<li>{escape(_line(r))} <a href=\"{escape(r.booking[0][1])}\">book</a></li>" for r in top)
            + "</ol><p>Full report attached.</p>")
    return subject, text, html


ISSUE_ROWS = 30


def _md(s: str) -> str:
    return s.replace("|", "\\|")


def render_issue(results: list[Result], cov, today: date, hist: dict, mention: str) -> tuple[str, str]:
    """A GitHub issue: GitHub emails it to the repo owner, so no mail password is needed."""
    subject, _, _ = render_email(results, cov, today, hist)
    title = subject.replace("SOF–TYO:", f"SOF–TYO {today.isoformat()}:", 1)
    ranked = rank(results)
    deals = [r for r in ranked if not r.problems]
    top = (deals or ranked)[:ISSUE_ROWS]
    lines = [f"@{mention} daily Sofia ↔ Tokyo results.", "", _coverage_line(cov)]
    lines += [f"- {_md(f)}" for f in cov.failures[:10]]
    lines += ["", f"{'Best' if deals else 'Closest'} {len(top)} of {len(deals) if deals else len(ranked):,} "
                  f"{'trips under budget' if deals else 'trips (none under budget)'}, fewest school days first:", "",
              "| € pp | total | cabin | people | dates | days | school days | flights | trend | book |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in top:
        t = r.trip
        flights = (" + ".join(f"{s.code} {s.origin}→{s.destination} {s.dep:%d %b %H:%M}" for s in t.outbound.segments)
                   + " / " + " + ".join(f"{s.code} {s.origin}→{s.destination} {s.dep:%d %b %H:%M}" for s in t.inbound.segments))
        books = " ".join(f"[{i + 1}]({u})" for i, (_, u) in enumerate(r.booking))
        lines.append(f"| {_eur(r.price_pp)} | {_eur(r.price_pp * t.party)} | {t.cabin.replace('-', ' ')} | {t.party} | "
                     f"{t.outbound.dep:%a %d %b} → {t.inbound.arr:%a %d %b %Y} | {t.stay_days} | {r.school_days} | "
                     f"{_md(flights)}{' (separate tickets)' if t.self_transfer else ''} | {_md(trend(hist, t.key))} | {books} |")
    lines += ["", "Prices are Google Flights' cheapest seller with a 23 kg bag; the airline's own price can be a little higher. "
              "The full report with legroom, seat plans and meals is attached to each run's summary in the Actions tab "
              "(open the run, then *report*)."]
    return title, "\n".join(lines)
