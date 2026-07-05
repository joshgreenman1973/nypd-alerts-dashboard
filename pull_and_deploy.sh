#!/bin/bash
# Daily NYPD alerts dashboard refresh:
#   pull new alerts (Slack API) -> rebuild dashboard -> commit & push -> iMessage.
# Requires a Slack token in $SLACK_TOKEN or Keychain item 'nypd-slack-token'.
set -e
cd "$(dirname "$0")"
export PATH="/usr/bin:/bin:/usr/local/bin:/Users/joshgreenman/.local/bin:$PATH"

STAMP=$(date +%Y%m%d_%H%M)
mkdir -p logs
LOG="logs/run_$STAMP.log"
SITE_URL="https://joshgreenman1973.github.io/nypd-alerts-dashboard/"
IMESSAGE_TO="9175823254"

send_imessage () {
  local body="$1"
  osascript -e "tell application \"Messages\"
    set targetService to 1st account whose service type = iMessage
    set targetBuddy to participant \"$IMESSAGE_TO\" of targetService
    send \"$body\" to targetBuddy
  end tell" 2>/dev/null || echo "iMessage send failed"
}

{
  echo "=== NYPD alerts refresh $STAMP ==="
  git pull --quiet --no-edit || true

  echo "-- pull --"
  PULL_OUT=$(python3 pull_via_api.py)
  echo "$PULL_OUT"

  echo "-- rebuild --"
  REFRESH_OUT=$(python3 refresh.py)
  echo "$REFRESH_OUT"

  if [ -n "$(git status --porcelain data.csv index.html dashboard_data.json)" ]; then
    git add data.csv index.html dashboard_data.json
    git commit -q -m "Daily refresh $STAMP [skip ci]" || true
    git push -q && echo "pushed" || echo "push failed"
    ADDED=$(echo "$PULL_OUT" | grep -oE 'Added [0-9]+' | grep -oE '[0-9]+' || echo "0")
    TOTAL=$(echo "$REFRESH_OUT" | grep -oE '[0-9]+ rows' | grep -oE '[0-9]+' || echo "?")
    send_imessage "NYPD alerts dashboard refreshed: +${ADDED} new alerts (${TOTAL} total). ${SITE_URL}"
  else
    echo "No changes; nothing to deploy."
  fi
  echo "=== done ==="
} >> "$LOG" 2>&1

echo "Run complete. Log: $LOG"
