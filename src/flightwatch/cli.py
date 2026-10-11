import argparse
import json
import os
import sys
import urllib.request
from dataclasses import replace
from datetime import date
from pathlib import Path

from flightwatch import history
from flightwatch.airlines import AirlineTable
from flightwatch.calendar_bg import DaysOff
from flightwatch.config import load_config
from flightwatch.dates import today_in
from flightwatch.enrich import enrich
from flightwatch.google.client import GoogleClient, primp_transport
from flightwatch.notify import send_email
from flightwatch.report import render_email, render_html
from flightwatch.shard import ShardResult, merge_shards, run_shard, save_shard


def make_transport():
    return primp_transport()


def today() -> date:
    return today_in(load_config().timezone)


def _key() -> str:
    key = os.environ.get("FLIGHTWATCH_KEY")
    if not key:
        sys.exit("FLIGHTWATCH_KEY is not set")
    return key


def _search(args, day: date, index: int, total: int) -> ShardResult:
    cfg = load_config()
    if args.no_hubs:
        cfg = replace(cfg, hubs=())
    client = GoogleClient(transport=make_transport(), min_interval=args.interval,
                          max_requests=cfg.max_requests_per_run // total)
    return run_shard(client, cfg, day, index, total, args.limit_days)


def _report(res: ShardResult, args, day: date) -> None:
    cfg, key = load_config(), _key()
    airlines, cal = AirlineTable.load(), DaysOff.load()
    results = [enrich(t, cfg, airlines, cal) for t in res.trips]

    def fits_rules(r):
        return not [p for p in r.problems if "budget" not in p]

    shown = [r for r in results if fits_rules(r) and r.price_pp <= cfg.budget_pp_eur[r.trip.cabin] * cfg.stage2_margin]
    hist = history.load(Path(args.history), key)
    history.record(hist, [(r.trip.key, r.price_pp) for r in shown], day)
    for cabin in cfg.budget_pp_eur:
        for party in cfg.parties:
            prices = [r.price_pp for r in results if fits_rules(r) and r.trip.cabin == cabin and r.trip.party == party]
            history.record_best(hist, cabin, party, min(prices, default=None), day)
    html = render_html(shown, res.coverage, day, hist, cal.source)
    Path(args.out).write_text(html)
    history.save(Path(args.history), key, hist)
    subject, text, body = render_email(shown, res.coverage, day, hist)
    if not os.environ.get("CI"):          # CI logs of a public repo are public: keep prices out of them
        print(subject)
    if not args.no_email:
        send_email(subject, text, body, html)
    if not res.coverage.complete:
        print("search incomplete:", "; ".join(res.coverage.failures[:3]), file=sys.stderr)
        sys.exit(1)               # a red run lets the Mac fallback take over


def main(argv=None):
    ap = argparse.ArgumentParser(prog="flightwatch")
    sub = ap.add_subparsers(dest="cmd", required=True)
    shard_p, local_p, report_p = sub.add_parser("shard"), sub.add_parser("local"), sub.add_parser("report")
    for p in (shard_p, local_p):
        p.add_argument("--limit-days", type=int)
        p.add_argument("--no-hubs", action="store_true")
        p.add_argument("--interval", type=float, default=1.0)
    for p in (local_p, report_p):
        p.add_argument("--history", default="history/history.bin")
        p.add_argument("--no-email", action="store_true")
        p.add_argument("--out", default="report.html")
    shard_p.add_argument("--index", type=int, required=True)
    shard_p.add_argument("--total", type=int, required=True)
    shard_p.add_argument("--out", required=True)
    report_p.add_argument("--shards", required=True)
    report_p.add_argument("--expected", type=int, default=30)
    fc = sub.add_parser("fallback-check")
    fc.add_argument("--repo", required=True)
    args = ap.parse_args(argv)
    day = today()

    if args.cmd == "shard":
        save_shard(_search(args, day, args.index, args.total), Path(args.out), _key())
    elif args.cmd == "local":
        _report(_search(args, day, 0, 1), args, day)
    elif args.cmd == "report":
        paths = sorted(Path(args.shards).glob("shard-*.bin"))
        _report(merge_shards(paths, _key(), args.expected), args, day)
    elif args.cmd == "fallback-check":
        url = (f"https://api.github.com/repos/{args.repo}/actions/workflows/daily.yml/runs"
               f"?status=success&created=%3E%3D{day.isoformat()}")
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                ok = json.load(r).get("total_count", 0) > 0
        except Exception as e:      # offline or rate-limited: unknown, so do not start an 8-hour run
            print("fallback-check: could not ask GitHub:", e, file=sys.stderr)
            sys.exit(2)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
