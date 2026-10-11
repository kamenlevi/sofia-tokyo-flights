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
export GMAIL_USER="$(security find-generic-password -s flightwatch-gmail-user -w)"
export GMAIL_APP_PASSWORD="$(security find-generic-password -s flightwatch-gmail-app-password -w 2>/dev/null)"
export MAIL_TO="$GMAIL_USER"
if [ -z "$GMAIL_APP_PASSWORD" ]; then echo "$(date) no Gmail app password in Keychain; not running"; exit 0; fi
git pull --ff-only
caffeinate -i flightwatch local --history history/history.bin --out report.html
git add history/history.bin && git commit -m "History $(date +%F) (Mac fallback)" && git push
