#!/bin/zsh
# Runs at noon (or on wake). If today's GitHub run did not succeed, search from this Mac instead.
set -u
REPO_DIR="/Users/kamen/sofia-tokyo-flights"
cd "$REPO_DIR" || exit 1
export PATH="$REPO_DIR/.venv/bin:/usr/bin:/bin"
# The cloud run starts 05:00-06:00 Sofia time and takes about an hour; before 10:00 it may still be running
if [ "$(date +%H)" -lt 10 ]; then echo "$(date) too early to judge today's cloud run"; exit 0; fi
flightwatch fallback-check --repo kamenlevi/sofia-tokyo-flights
case $? in
  0) echo "$(date) GitHub run OK, nothing to do"; exit 0 ;;
  2) echo "$(date) could not reach GitHub; not starting a run"; exit 0 ;;
esac
export FLIGHTWATCH_KEY="$(security find-generic-password -s flightwatch-key -w)"
export PATH="$PATH:/opt/homebrew/bin"   # gh
git pull --ff-only
ISSUE="$(mktemp -d)/issue"
caffeinate -i flightwatch local --history history/history.bin --out report.html --no-email --issue "$ISSUE"
for n in $(gh issue list --repo kamenlevi/sofia-tokyo-flights --label daily --state open --json number -q '.[].number'); do
  gh issue close "$n" --repo kamenlevi/sofia-tokyo-flights; done
gh issue create --repo kamenlevi/sofia-tokyo-flights --label daily \
  --title "$(cat "$ISSUE.title") (from the Mac)" --body-file "$ISSUE.md"
git add history/history.bin && git commit -m "History $(date +%F) (Mac fallback)" && git push
