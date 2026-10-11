# Sofia ↔ Tokyo flight watch — design

Date: 2026-10-11 · Status: approved by Kamen 2026-10-11

## Goal

Every day, find every Sofia ↔ Tokyo return trip that fits the family's rules and
budget, and email a report that shows everything needed to choose and book it on
the airline's own site. It must never miss a qualifying combination because of
how it searched.

## Requirements (as stated)

**Travellers**
- Party A: 4 people, 3 adults + 1 child aged 14.
- Party B: 3 people, 2 adults + 1 child aged 14.
- Airlines charge a 14-year-old the adult fare (12 and over), so the price per
  person is the same for both parties. The parties differ only in whether enough
  seats exist and whether the group can sit together.

**Cabins and budget** (per person, whole return trip, including one 23 kg checked
bag and meals):
- Economy: €1,200 or less.
- Premium economy ("economy plus"): €1,300 or less.

**Trip**
- From SOF to any Tokyo airport (NRT or HND), and back to SOF.
- Stay of 10 to 21 days, measured from landing in Tokyo to taking off from Tokyo.
  A stay of 14 days or more is tagged "recommended".
- Outbound departure dates run from today + 14 days to today + 9 months. The
  window moves forward with each run.
- Each direction has at most 2 flights (one connection) and takes at most 20 h
  from first departure to last arrival, waiting included.

**Booking**
- Every result must be bookable on the airline's own website:
  - a single ticket: on the website of the airline that sells it (e.g. LOT for a
    LOT itinerary);
  - separate tickets: each ticket on its own airline's website.
- Separate tickets (self-transfer) are allowed when the connection leaves enough
  time to:
  - collect checked bags,
  - check in again before the second airline's bag-drop closes,
  - clear security (and passport control where needed),
  - reach the gate.

**Report contents**
- Dates and length of stay.
- Departure and arrival times in local time, and the arrival time in Tokyo and in
  Sofia.
- Airlines, flight numbers, aircraft, airports and terminals.
- Connection times and total time each way.
- Price per person and in total for Party A and for Party B, with a breakdown of
  fare, bag and seat costs.
- Seats:
  - standard seats compared with extra-legroom seats, with their price;
  - a recommended seating plan (see Seating rules);
  - window seats (view).
- Meals per flight.
- School days missed (see School and holiday calendar).
- Booking link(s) on the airline's site.
- Price trend over the previous days.

**Schedule and delivery**
- The search runs once a day in the cloud and must not depend on the Mac being on.
  The Mac is only a backup runner.
- A daily email goes to kamenlevi@gmail.com. It lists the top deals inline, or says
  that nothing is under budget, and attaches the full HTML report. The report can
  be sorted and filtered.

**Cost: a hard rule**
- Running the tool must never cost money or Claude usage. Only building it may use
  Claude.
- The daily run is plain Python. It makes no LLM or Claude calls and uses no paid
  APIs.
- **GitHub Actions:**
  - public repo, so standard runners are free and unlimited;
  - each job has `timeout-minutes: 60` and the whole run makes at most 15,000
    requests;
  - the account has no payment method, so GitHub cannot bill it;
  - at the end of each run, the report states the minutes used this month.
- Email goes through Gmail SMTP, which is free.

## Assumptions (not stated, chosen by Claude; correct if wrong)

- "Economy plus" means the premium economy cabin. Extra-legroom seats inside economy
  are covered by the seat comparison.
- Self-transfer minimum connection:
  - same airport: 3 h;
  - two airports in the same city (e.g. IST↔SAW, NRT↔HND): 5 h;
  - where a hub needs entry formalities to collect bags, the minimum also needs 2 h
    or more left after landing before the second flight's check-in closes.
- No overnight self-transfers. Every connection must still fit inside the 20 h
  limit.
- Party B's seating may split 2 + 1 only on narrow-body aircraft (A320/737 family).
  On wide-bodies the plan should keep all 3 together.
- If a leg's meals cost extra (e.g. a low-cost feeder flight), the price of one meal
  per person per leg over 2 h is added and shown as "meal bought on board".
- Prices are in EUR. Where a source quotes another currency, it is converted at the
  ECB daily reference rate and the converted price is marked.

## Search strategy (revised after the 2026-10-11 spike)

**What the spike showed** (throwaway code, live Google Flights, 2026-10-11):
- **Plain search-page requests work** (`/travel/flights?tfs=…`).
  - From an EU address they need the "reject all" consent cookie `SOCS=CAI`.
  - About 0.4–1 s per request. 40 back-to-back requests: no throttling.
- **Each result lists every itinerary** across both result sections, with:
  - flight numbers and aircraft;
  - legroom per segment ("31 in");
  - layover minutes and total duration;
  - the total price for all passengers. `checked_bags=1` adds Google's estimated
    bag fee.
- **A round-trip search** returns the outbound options, each with the cheapest
  round-trip total. Encoding the chosen outbound as selected segments (FlightData
  field 4) returns its matching returns with exact totals.
- **Not usable:** Google's price calendar (GetCalendarGraph) and booking-options
  data now require a BotGuard token. They are not used, and nothing tries to get
  around them.
- **Google offers no self-transfer itineraries on SOF↔TYO.** Separate tickets must
  be built by the app.
- **One-way fares from Tokyo are high** (about €1,100–1,750 per person), so
  through-fares on one return ticket are the main source of deals.

**Every-combination search, every day.** Date pairs (d, r): d from today + 14 to
today + 9 months (Europe/Sofia dates), and r − d from 10 to 22. That is about 3,300
pairs × 2 cabins.

1. **Stage 1, every pair, every day:**
   - one round-trip search for 4 adults, at most 1 stop, at most 1,200 min per
     direction, 1 checked bag;
   - result: every outbound itinerary with its cheapest round-trip total.
   - Google's prices here are live, so they bound every pairing of that outbound.
2. **Stage 2:** for each outbound whose cheapest total per person is at most
   budget × 1.10, a selected-outbound search lists every return with its exact
   total. Every outbound × return pairing is then checked by the rules engine.
   - The 10% margin covers estimated bag fees.
3. **Party B (3 people):** a fare per person for 3 is never above the fare for 4
   (fewer seats needed). So for pairs whose Party A cheapest per person is at most
   budget × 1.5, stages 1 and 2 are repeated with 3 adults.
4. **Separate tickets through hubs:**
   - With at most 2 flights per direction, a self-transfer is:
     - a nonstop feeder SOF ↔ hub on one ticket, plus
     - a nonstop hub ↔ Tokyo return on its own ticket.
   - Hubs: those with nonstop service to both SOF and Tokyo. They are listed in
     `config.toml`.
     - Enabled by default: IST, DOH, DXB, FRA, MUC, WAW, HEL.
     - Listed but disabled to cap daily load: AUH, VIE, ZRH, CDG, AMS, LHR, FCO.
   - The hub ↔ Tokyo return searches rotate through the date pairs, so every hub
     covers the full matrix every 7 days. This caps daily load.
   - Feeder one-ways are fetched only for dates where a hub return is already
     under budget, which gives up nothing.
   - This is the one part not covered daily. The report says so.
5. **Load:**
   - about 9,000–15,000 requests a day;
   - spread over 16 parallel GitHub Actions jobs (public repo: unlimited free
     minutes), each throttled to at least 1 s between requests;
   - about 20–30 min wall time.

**Bookability without booking data:**
- A through-fare whose segments are all sold by one airline group is marked
  bookable on that airline's site.
- Each result gets a pre-filled search link for that airline's own site.
- The report notes that Google's price is the cheapest seller's. The airline's own
  price can be slightly higher.

## Rules engine

All rules are pure functions over a normalised `Itinerary` model, so they can be
tested in isolation.

- **Segments:** 1 or 2 per direction. Any third segment rejects the itinerary.
- **Duration:** first departure to last arrival, computed in UTC. 20 h or less each
  way.
- **Stay:** Tokyo landing (local) to Tokyo departure (local), counted in days. Must be
  10 to 21. Tagged "recommended" at 14 or more.
- **Connection:**
  - on one ticket, the airline's own minimum connection time is accepted;
  - on separate tickets, the self-transfer minimum from Assumptions applies, plus a
    check against the second flight's check-in close time.
- **Price:**
  - fare,
  - + a 23 kg bag per person where the fare does not include one (fee from the airline
    table),
  - + paid meals,
  - all per person, then multiplied by the party size.
  - Compared with the budget for the cabin. For mixed-cabin trips, the premium
    economy budget applies only if every long-haul leg is premium economy.
- **Bookability:**
  - single tickets need an airline-direct booking option or a known airline selling
    the fare;
  - each separate ticket must be a single-airline itinerary sold on that airline's
    site.
- **Seats:** enough seats for the party in the chosen cabin. Seat counts come from
  searching with 4 adults (Party A) and with 3 adults (Party B).

## Seating rules

- **Party A (4 people):** prefer 4 together. Otherwise 2 + 2 (pairs in the same row
  or rows next to each other). 3 + 1 is acceptable.
- **Party B (3 people):** prefer 3 together. 2 + 1 only on narrow-bodies.
- From the cabin layout, find the best layout under 2 cost options:
  - standard seats only;
  - the maximum legroom available: exit rows, bulkheads, extra-legroom products.
    Note restrictions, e.g. a 14-year-old is allowed in an exit row on most airlines
    only from 15 or 16, which the report flags.
- Show pitch and width for each option, the price difference, and the window seats.
- If no seat map is available, show the static legroom figures and mark the seating
  plan as "not verified".

## School and holiday calendar

- **Days off:**
  - Saturdays and Sundays;
  - Bulgarian public holidays;
  - school holidays from the 2026/27 Ministry of Education order;
  - every day from 1 to 31 December 2026.
- Score: the school days that fall between the departure day and the arrival-home
  day.
- Results are ranked first by whether they are under budget, then by school days
  missed, then by price.
- The report has a filter for "leaves on Fri/Sat, returns Sat/Sun".

## Architecture

The code is a Python 3.12 package, `flightwatch`, in its own repo at
`~/sofia-tokyo-flights` (a public GitHub repo, chosen by Kamen 2026-10-11 for unlimited free
Actions minutes; results and history are stored encrypted, and passwords are kept
in secrets).

```
flightwatch/
  config.toml          # parties, budgets, hubs, MCT rules, window
  calendar_bg.py       # school/holiday days-off set
  model.py             # Segment, Itinerary, Trip, Offer dataclasses
  sources/
    google.py          # calendars, date grid, full search (fast-flights)
    lowcost.py         # Ryanair/Wizz feeder fare calendars
    airlines.py        # static airline tables: pitch, layout, meals, bags
  data/airlines.toml
  prune.py             # lower-bound pruning
  combine.py           # outbound×return and self-transfer combination
  rules.py             # duration, stay, connection, price, bookability
  seating.py           # seat-map layout search
  history.py           # SQLite price history (committed to repo)
  report.py            # HTML report + email body
  notify.py            # Gmail SMTP send
  run.py               # orchestrates one daily run
.github/workflows/daily.yml   # cron 04:00 UTC, ~30–40 min
launchd/                       # optional Mac backup runner
tests/                         # rules, combine, seating, calendar (recorded fixtures)
```

**Data flow:** config → calendars (prune) → full searches → combine → rules →
airline-table enrichment (bags, meals, legroom) → seating → history → report →
email.

## Error handling

- Each source failure is caught and named in the email, e.g. "Google search failed
  for 37 dates: listed in the report".
- A run never reports "no deals" when a source has failed.
- Rate limiting: back off and retry. Whatever cannot finish in today's run is
  searched first tomorrow, and the report shows coverage, e.g. "100% of dates
  checked today".
- Missing seat maps, meal data or legroom data degrade to "not verified". They never
  drop a result.

## Testing

- Unit tests for the rules, the combination step, seating and the calendar, using
  small recorded source responses as fixtures. No live calls in the tests.
- One live smoke run on a 2-week window before the daily schedule is turned on.

## Setup Kamen does (credentials can't be entered by Claude)

- Create a Gmail app password and add it as a GitHub Actions secret.
- Approve the creation of the private GitHub repo.

## Out of scope

- Booking or holding flights.
- Hotels.
- Price prediction.
- Searching airports other than SOF.
