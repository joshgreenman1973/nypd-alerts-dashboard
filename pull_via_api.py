#!/usr/bin/env python3
"""Incrementally pull new #nypd-alerts messages via the Slack Web API and append
them to data.csv. Then run refresh.py to rebuild the dashboard.

Auth: reads a Slack token (needs scope `channels:history`) from, in order:
  1. env var SLACK_TOKEN
  2. macOS Keychain generic password, service name `nypd-slack-token`
     (add once with:  security add-generic-password -s nypd-slack-token -a nypd -w)

Only message subjects (email file names) and timestamps are read — no file bodies,
no personal data. Prints how many new rows were added.
"""
import csv, os, sys, json, subprocess, urllib.request, urllib.parse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "data.csv")
CHANNEL = "C08082VG89J"      # #nypd-alerts in vitalcity.slack.com
NY = ZoneInfo("America/New_York")
COLS = ["datetime","date","time","message_ts","file_id","subject","rma","unit",
        "offense","is_update","is_arrest","is_pattern","is_found","category"]

sys.path.insert(0, HERE)
import parse as P


def get_token():
    tok = os.environ.get("SLACK_TOKEN")
    if tok:
        return tok.strip()
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", "nypd-slack-token", "-w"],
            capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit("ERROR: no Slack token. Set $SLACK_TOKEN or add Keychain item "
                 "'nypd-slack-token' (see file header).")


def slack(method, token, **params):
    url = "https://slack.com/api/" + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if not data.get("ok"):
        sys.exit(f"ERROR: Slack API {method} failed: {data.get('error')}")
    return data


def newest_ts():
    """First data row (file is newest-first) → its message_ts as the pull cursor."""
    with open(CSV) as f:
        rdr = csv.DictReader(f)
        first = next(rdr, None)
    return first["message_ts"] if first else "0"


def main():
    token = get_token()
    cursor_ts = newest_ts()
    new_rows, page_cursor = [], None
    while True:
        kw = dict(channel=CHANNEL, oldest=cursor_ts, limit=200, inclusive="false")
        if page_cursor:
            kw["cursor"] = page_cursor
        data = slack("conversations.history", token, **kw)
        for m in data.get("messages", []):
            files = m.get("files") or []
            if not files:
                continue
            f = files[0]
            subject = (f.get("name") or f.get("title") or "").strip()
            if not subject:
                continue
            dt = datetime.fromtimestamp(float(m["ts"]), tz=timezone.utc).astimezone(NY)
            row = P.parse_subject(subject, dt.strftime("%Y-%m-%d %H:%M:%S"))
            row["message_ts"] = m["ts"]
            row["file_id"] = f.get("id", "")
            new_rows.append(row)
        if data.get("has_more") and data.get("response_metadata", {}).get("next_cursor"):
            page_cursor = data["response_metadata"]["next_cursor"]
        else:
            break

    if not new_rows:
        print("No new messages.")
        return

    # de-dupe against message_ts already present, then write newest-first
    with open(CSV) as f:
        existing = list(csv.DictReader(f))
    seen = {r["message_ts"] for r in existing}
    fresh = [r for r in new_rows if r["message_ts"] not in seen]
    if not fresh:
        print("No new messages (all already present).")
        return
    fresh.sort(key=lambda r: float(r["message_ts"]), reverse=True)
    combined = fresh + existing
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in combined:
            w.writerow({c: r.get(c, "") for c in COLS})
    print(f"Added {len(fresh)} new rows (newest: {fresh[0]['date']} {fresh[0]['time']} — {fresh[0]['subject'][:50]}).")


if __name__ == "__main__":
    main()
