#!/bin/zsh
# Runs at noon. If today's GitHub run did not succeed, search from this Mac instead.
set -u
REPO_DIR="$HOME/sofia-tokyo-flights"
cd "$REPO_DIR" || exit 1
export PATH="$REPO_DIR/.venv/bin:/usr/bin:/bin"
if flightwatch fallback-check --repo kamenlevi/sofia-tokyo-flights; then
  echo "$(date) GitHub run OK, nothing to do"; exit 0
fi
export FLIGHTWATCH_KEY="$(security find-generic-password -s flightwatch-key -w)"
export GMAIL_USER="$(security find-generic-password -s flightwatch-gmail-user -w)"
export GMAIL_APP_PASSWORD="$(security find-generic-password -s flightwatch-gmail-app-password -w)"
export MAIL_TO="$GMAIL_USER"
git pull --ff-only
caffeinate -i flightwatch local --history history/history.bin --out report.html
git add history/history.bin && git commit -m "History $(date +%F) (Mac fallback)" && git push
