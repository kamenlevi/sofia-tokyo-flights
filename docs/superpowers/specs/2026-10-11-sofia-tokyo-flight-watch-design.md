# Sofia ↔ Tokyo flight watch — design

Date: 2026-10-11 · Status: draft for review

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

**Cost**
- Use free sources and check as many combinations as possible.
- Any paid service needs Kamen's explicit OK before it is switched on.

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

## Search strategy: lossless pruning

The full set of combinations is about:
- 255 outbound dates × 12 stay lengths × 2 cabins, multiplied by every itinerary on
  each date,
- plus every self-transfer pairing through each hub.

Searching each combination as its own request every day is not possible from free
sources. Instead, the search uses a **lower-bound** step that gives exactly the same
answer:

1. **Price calendars (cheap, a few hundred requests a day).** For each route and
   cabin, fetch the cheapest unfiltered price for every date, and for every
   (outbound, return) pair on the round-trip grid.
   - An unfiltered cheapest price is a lower bound on any itinerary that meets the
     rules: adding the 1-stop limit, the 20 h limit or the 23 kg bag can only make
     the price go up.
   - If the lower bound for a date or a date pair is above budget × 1.15, no
     qualifying itinerary can exist there, so it is skipped.
   - The 15% margin covers stale calendar prices.
2. **Full searches for every date and pair that survives.** Fetch every itinerary,
   then evaluate every outbound × return combination for every stay length from 10
   to 21 days, for both cabins and both parties.
3. **Self-transfer combinations.** Combine one-way legs SOF → hub → Tokyo and back
   through the hubs that serve both cities:
   - IST, SAW, DOH, DXB, AUH, FRA, MUC, VIE, ZRH, WAW, HEL, CDG, AMS, LHR, FCO, MXP,
     BCN, ATH, BUD, OTP;
   - the list is a config file, extended by any hub seen in the results.

   Feeder legs (SOF ↔ hub) come from monthly fare calendars. The long-haul legs
   (hub ↔ Tokyo) are pruned in the same way as step 1, before any full search.
4. **Every date stays covered.** A date whose lower bound drops back under the
   threshold is fully searched on the same day. The calendars themselves are
   refreshed every day for the whole window.

This keeps the guarantee: a qualifying combination is missed only if a source does
not list that flight at all, or if its calendar shows a price more than 15% above
the real one.

## Data sources

| Source | Used for | Cost | Risk |
|---|---|---|---|
| Google Flights, through the `fast-flights` library plus Google's calendar/date-grid endpoints | Price calendars, full itinerary lists, self-transfer legs, "book with airline" options | Free | Unofficial and against Google's terms of service, so it can break when Google changes the site. Volume is kept polite and spread over the run. No CAPTCHA or bot-check evasion. If the library breaks, the run says so in the email and does not report "no deals". |
| Ryanair / Wizz Air public fare calendars | Feeder legs SOF ↔ European hubs | Free | Unofficial endpoints |
| Duffel (live mode) | Detail check on the top candidates: seat maps, extra-legroom seat prices, bags, meals, bookable fare confirmation | Free up to 1,500 searches per booking made, then $0.005 per search. With no bookings, expect a few dollars a month | Enabled only after Kamen OKs the cost |
| Static legroom table (seat pitch and width per airline, aircraft type and cabin, from public airline specs) | Legroom when no seat map is available | Free | Can drift; dated in the report |
| Bulgarian Ministry of Education 2026/27 school-year order, and the Bulgarian public holidays | School-day scoring | Free | Dates must come from the official order (mon.bg), not guesses |

Skyscanner, Kiwi and Amadeus are left out. Skyscanner's API is for partners only and
its site blocks bots. Kiwi's API takes new users by invitation only. Amadeus's free
self-service API reportedly closed on 2026-07-17.

**First implementation step (spike):** confirm that the Google Flights price calendar
and date grid can be read for SOF → TYO in both cabins, and how many requests a run
can make before it is throttled. The strategy above depends on that. If it turns out
not to be possible, stop and come back with alternatives before building further.

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
  - + a 23 kg bag per person where the fare does not include one (fee from Duffel,
    or the airline fee table),
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
  Duffel, or a search made with 4 adults.

## Seating rules

- **Party A (4 people):** prefer 4 together. Otherwise 2 + 2 (pairs in the same row
  or rows next to each other). 3 + 1 is acceptable.
- **Party B (3 people):** prefer 3 together. 2 + 1 only on narrow-bodies.
- From the seat map, find the best layout under 2 cost options:
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
`~/sofia-tokyo-flights` (a private GitHub repo once Kamen agrees to it).

```
flightwatch/
  config.toml          # parties, budgets, hubs, MCT rules, window
  calendar_bg.py       # school/holiday days-off set
  model.py             # Segment, Itinerary, Trip, Offer dataclasses
  sources/
    google.py          # calendars, date grid, full search (fast-flights)
    lowcost.py         # Ryanair/Wizz feeder fare calendars
    duffel.py          # detail check: seat maps, bags, meals
    legroom.py         # static seat-pitch table lookup
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

**Data flow:** config → calendars (prune) → full searches → combine → rules → Duffel
detail on the top N → seating → history → report → email.

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
- Create a Duffel account and add its key as a secret, only if the Duffel cost is
  approved.
- Approve the creation of the private GitHub repo.

## Out of scope

- Booking or holding flights.
- Hotels.
- Price prediction.
- Searching airports other than SOF.
