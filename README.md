# Sofia ↔ Tokyo flight watch

Every day this checks Google Flights for every Sofia ↔ Tokyo (Narita or Haneda) return trip that fits our rules, then emails a report.

The rules:
- **Travellers:** 4 people (3 adults and a 14-year-old) or 3 people (2 adults and the 14-year-old).
- **Cabin and budget per person:** economy up to €1,200, premium economy up to €1,300. That covers the whole return trip, with a 23 kg bag and meals.
- **Stay:** 10–21 days in Japan, where 14 days or more is tagged "recommended".
- **Flights:** at most one stop and at most 20 hours each way.
- **Dates:** departures from 2 weeks to 9 months ahead.

Each result says how many school days it misses. The count uses the official Bulgarian 2026/27 school calendar.

Trips leaving in December 2026 are marked **December pick** and listed first, because Mum is between jobs then. Their weekdays still count as missed school days. To change the month, edit `recommended_months` in `src/flightwatch/data/config.toml`.

## Costs nothing to run

- The daily run is plain Python. It makes no AI or Claude calls and uses no paid APIs.
- It runs on GitHub Actions in this public repo, where standard runners are free.
- The daily summary arrives as a GitHub issue, which GitHub emails to you. No mail password is needed.
- Search results and price history are stored **encrypted**, so this public repo shows only the code and settings.

## Reading the daily email (a GitHub issue)

- **Where:** GitHub emails each new issue to you (the repo owner, mentioned in it). The previous day's issue is closed automatically.
- **Subject line:** tells you how many deals are under budget, the best price per person, and its school days.
- **INCOMPLETE:** if the subject says this, some searches failed. Missing results then do **not** mean there are no deals.
- **Full report:** the issue lists the best 30 trips. For legroom, seat plans and meals, open that day's run in the Actions tab, download the *report* artifact and open `report.html` in a browser.
  - Green rows are under budget. Yellow rows are within 10% of budget.
  - Click a column header to sort.
  - Use the filters for cabin, number of people, 14+ day stays, one-ticket trips, Friday/Saturday departures, and a maximum number of school days.
- **Each row shows:**
  - days in Japan: nights, full days (not counting the landing and leaving days), and the landing and leaving times;
  - the whole trip from leaving Sofia to getting home: total days, weekdays, weekend days, school days, and the official holidays inside it (holiday list from [почивнидни.com](https://xn--b1aekbb1acci5f.com/));
  - every flight: number, airline, aircraft, local times, and arrival times in Tokyo and in Sofia;
  - connection times and total time each way;
  - legroom: Google's figure, plus seat pitch and width from the airline's published specs;
  - a suggested seating plan so the family sits together, with window seats;
  - meals, and extra-legroom seat options with prices;
  - the price trend;
  - a **Book** link for each ticket.
- **Book link:** opens Google's booking page for exactly that itinerary, where you choose the airline's own site.
- **Prices:** these are Google's cheapest seller. The airline's own price can be a little higher.
- **Separate tickets** (connecting at a hub on two bookings): these are marked. They always leave at least 3 hours to collect bags, check in again, clear security and reach the gate. If the first flight is late, the second airline will **not** rebook you.

## One-time setup

1. Create the encryption key, then keep it safe (Keychain and a password manager):
   ```bash
   .venv/bin/python -c "from flightwatch.crypto import new_key; print(new_key())"
   ```
2. Add the key as a GitHub secret and to the Keychain:
   ```bash
   gh secret set FLIGHTWATCH_KEY --repo kamenlevi/sofia-tokyo-flights
   security add-generic-password -s flightwatch-key -a "$USER" -w
   ```

## Mac backup

`mac/com.kamen.flightwatch.plist` runs `mac/fallback.sh` every day at 12:00:
- If today's GitHub run succeeded, it does nothing.
- If the run failed, the Mac runs the whole search itself (several hours, kept awake with `caffeinate`) and posts the issue.
- If the Mac was asleep at noon, the job runs when it next wakes.

Install the job:
```bash
cp mac/com.kamen.flightwatch.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kamen.flightwatch.plist
```

## Running a small test by hand

This searches the first 2 departure dates and sends no email:
```bash
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
FLIGHTWATCH_KEY=<key> .venv/bin/flightwatch local --limit-days 2 --no-email --no-hubs --history /tmp/fw.bin
open report.html
```

To start a full cloud run now: `gh workflow run daily --repo kamenlevi/sofia-tokyo-flights`.

## Settings

`src/flightwatch/data/config.toml` holds the budgets, stay lengths, hub airports, request limits and number of parallel jobs. If you change `shards`, change the matrix list in `.github/workflows/daily.yml` to match.

Airline facts (meals, layouts, legroom, extra-legroom prices) live in `src/flightwatch/data/airlines.toml`. Each entry records its source and the date it was checked.
