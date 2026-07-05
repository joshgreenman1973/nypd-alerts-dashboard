#!/usr/bin/env python3
"""Parse an NYPD DCPI email subject line into the dashboard's structured fields.

The channel delivers one email per message; the email's file name IS the subject.
This reproduces the field schema used to build data.csv so incrementally pulled
rows are consistent with the original backfill.
"""
import re

RMA_RE = re.compile(r"RMA\s*#?\s*(\d+)\s*-\s*(?:26|2026)\b", re.I)

def parse_rma(subject):
    m = RMA_RE.search(subject)
    return int(m.group(1)) if m else None

def parse_unit_offense(subject):
    """Split the leading '<unit> - <offense>' portion (before any RMA/asterisks)."""
    s = subject
    s = re.split(r"\(RMA", s, 1, flags=re.I)[0]      # drop RMA paren onward
    s = re.split(r"\*", s, 1)[0]                       # drop ***Update*** onward
    s = s.strip().rstrip("-").strip()
    # unit is the chunk before the first ' - ' / '- ' / '-' that precedes the offense
    m = re.match(r"\s*(.+?)\s*[-–]\s*(.+)$", s)
    if not m:
        return "", ""
    unit, offense = m.group(1).strip(), m.group(2).strip()
    # guard: if "unit" doesn't look like a command, treat whole thing as no-unit
    if not re.search(r"pct|td|mts|mtn|psa|precinct|park|midtown|transit|\d", unit, re.I):
        return "", offense
    return unit, offense

def classify(subject, unit, offense, rma):
    up = subject.upper()
    # "City Employee Arrested" is administrative even with a precinct prefix
    if "CITY EMPLOYEE ARRESTED" in up:
        return "other"
    if "PUBLIC SCHEDULE FOR THE NEW YORK CITY POLICE" in up:
        return "public_schedule"
    if "PRESS CLIPPINGS" in up:
        return "press_clippings"
    if any(k in up for k in ("MSG LOGISTICS", "LOGISTICS FOR", "THE OUTLOOK",
                             "FINEST MESSAGE", "TRAFFIC ADVISORY", "GAME LOGISTICS",
                             "MEDIA CLIPS", "KNICKS")):
        return "logistics"
    # press releases: subject-line prefixes and department-wide announcements
    if (up.startswith(("FOR IMMEDIATE RELEASE", "ADVISORY:", "MEDIA ADVISORY")) or
            "NYPD ANNOUNCES" in up or up.startswith("COMMISSIONER") or
            ("COMMISSIONER" in up and any(k in up for k in ("ANNOUNCE", "SWEAR IN",
             "DELIVER", "ADDRESS", "LAUNCH", "TO HOLD", "STATEMENT")))):
        return "announcement"
    if rma is not None or (unit and offense):
        return "crime_advisory"
    return "other"

def parse_subject(subject, datetime_str):
    """Return a dict row matching data.csv's columns (minus message_ts/file_id)."""
    subject = subject.strip()
    rma = parse_rma(subject)
    unit, offense = parse_unit_offense(subject)
    low = subject.lower()
    cat = classify(subject, unit, offense, rma)
    if cat != "crime_advisory":
        # administrative items carry no unit/offense
        if cat in ("public_schedule", "press_clippings", "announcement", "logistics"):
            unit, offense = "", ""
    return {
        "datetime": datetime_str,
        "date": datetime_str[:10],
        "time": datetime_str[11:19],
        "subject": subject,
        "rma": str(rma) if rma is not None else "",
        "unit": unit,
        "offense": offense,
        "is_update": "1" if "update" in low else "0",
        "is_arrest": "1" if "arrest" in low else "0",
        "is_pattern": "1" if "pattern" in low else "0",
        "is_found": "1" if "found" in low else "0",
        "category": cat,
    }

if __name__ == "__main__":
    # self-check: re-parse existing data.csv and report agreement on key fields
    import csv, os
    HERE = os.path.dirname(os.path.abspath(__file__))
    rows = list(csv.DictReader(open(os.path.join(HERE, "data.csv"))))
    fields = ["rma", "category", "is_update", "is_arrest", "is_pattern", "is_found"]
    disagree = {f: 0 for f in fields}
    for r in rows:
        p = parse_subject(r["subject"], r["datetime"])
        for f in fields:
            if (p[f] or "") != (r[f] or ""):
                disagree[f] += 1
    print(f"Checked {len(rows)} rows. Field disagreements vs backfill:")
    for f in fields:
        print(f"  {f}: {disagree[f]} ({disagree[f]/len(rows)*100:.1f}%)")
