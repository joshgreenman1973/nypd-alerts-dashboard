# The NYPD press feed, 2026

A dashboard of every alert the New York City Police Department's Deputy Commissioner of Public Information (DCPI) emailed out in the first half of 2026, parsed into a structured, searchable record.

**Live:** https://joshgreenman1973.github.io/nypd-alerts-dashboard/

## What it is

The NYPD press office pipes every media advisory — per-incident crime alerts, missing-persons notices, arrest updates, pattern bulletins, public schedules — into a Slack channel as email. This project pulls that feed, parses each email's subject line into structured fields (precinct, offense, case number, update/arrest/pattern flags), and charts what the department chose to tell the public.

## Files

- `index.html` — the self-contained dashboard (data embedded inline)
- `data.csv` — the parsed dataset, one row per press message
- `refresh.py` — rebuilds `dashboard_data.json` from the CSV and re-injects it into `index.html`
- `pull_and_deploy.sh` — the daily automation: pull new alerts, rebuild, redeploy, notify

## Method & limitations

Offense and borough groupings are editorial, derived by transparent rule from the department's own subject lines. Labels are the NYPD's initial framing, not independently verified crime classifications — in particular, "Homicide" advisories are **not** a murder count (many are follow-up updates and some are deaths later ruled non-criminal). Arrest follow-through reflects press behavior, not case clearances. No arrestee or victim names are carried into the dataset.

Not an official NYPD product.
