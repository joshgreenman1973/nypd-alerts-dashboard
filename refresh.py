#!/usr/bin/env python3
"""Rebuild dashboard_data.json from data.csv and re-inject it into index.html.

Usage: python3 refresh.py
Reads:  data.csv (one row per NYPD press message)
Writes: dashboard_data.json, and updates the embedded DATA blob in index.html.
"""
import csv, re, json, sys, os
from collections import Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "data.csv")
HTML = os.path.join(HERE, "index.html")
JSON = os.path.join(HERE, "dashboard_data.json")

def norm_offense(o):
    o = (o or "").strip().lower()
    if not o: return None
    o = o.replace("attempted ", "")
    m = {"forcible touching":"Forcible touching","robbery":"Robbery","gang assault":"Assault",
         "assault":"Assault","missing":"Missing person","found person":"Missing person","found":"Missing person",
         "sexual abuse":"Sexual abuse","sex abuse":"Sexual abuse","rape":"Rape","homicide":"Homicide","murder":"Homicide",
         "grand larceny auto":"Grand larceny","grand larceny":"Grand larceny","burglary":"Burglary",
         "reckless endangerment":"Reckless endangerment","shooting":"Shooting","arson":"Arson",
         "unlawful surveillance":"Unlawful surveillance","collision":"Collision / traffic","doa":"DOA / death investigation",
         "kidnapping":"Kidnapping","menacing":"Menacing","public lewdness":"Public lewdness","criminal mischief":"Criminal mischief",
         "hate crime":"Hate crime","endangering the welfare":"Child endangerment","robbery pattern":"Robbery"}
    for k, v in m.items():
        if k in o: return v
    return o.title()

def borough(unit):
    u = (unit or "").strip()
    if not u: return None
    mm = re.match(r"(\d+)", u)
    num = int(mm.group(1)) if (mm and "Pct" in u) else None
    if num is not None:
        if 1 <= num <= 34: return "Manhattan"
        if 40 <= num <= 52: return "Bronx"
        if 60 <= num <= 94: return "Brooklyn"
        if 100 <= num <= 115: return "Queens"
        if 120 <= num <= 123: return "Staten Island"
    uu = u.lower()
    if any(x in uu for x in ("mts","mtn","midtown","central park")): return "Manhattan"
    if uu.startswith("td") or "transit" in uu: return "Transit"
    if uu.startswith("psa") or "psa" in uu: return "Housing (PSA)"
    return "Other / citywide"

def build(rows):
    crime = [r for r in rows if r["category"] == "crime_advisory"]
    orig = [r for r in crime if r["is_update"] == "0"]
    months = sorted(set(r["date"][:7] for r in rows))
    mlab = {f"2026-{i:02d}": n for i, n in enumerate(
        ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
    ba, bc, bo = Counter(r["date"][:7] for r in rows), Counter(r["date"][:7] for r in crime), Counter(r["date"][:7] for r in orig)
    today_month = datetime.now().strftime("%Y-%m")
    monthly = [{"month": mlab.get(m, m), "all": ba[m], "crime": bc[m], "original": bo[m],
                "partial": m == today_month} for m in months]
    off = Counter()
    for r in crime:
        o = norm_offense(r["offense"]); off[o if o else "Pattern / unspecified"] += 1
    offense = [{"name": k, "count": v} for k, v in off.most_common()]
    bor = Counter(borough(r["unit"]) or "Other / citywide" for r in crime)
    boroughs = [{"name": k, "count": v} for k, v in bor.most_common()]
    un = Counter(r["unit"].strip() for r in crime if r["unit"].strip())
    precincts = [{"unit": k, "count": v, "borough": borough(k)} for k, v in un.most_common(20)]
    byh = Counter(int(r["time"][:2]) for r in rows if r["time"][:2].isdigit())
    hour = [{"hour": h, "count": byh.get(h, 0)} for h in range(24)]
    orig_by_rma = {}
    for r in orig:
        if r["rma"]: orig_by_rma.setdefault(r["rma"], r)
    arr = [r for r in crime if r["is_arrest"] == "1"]
    lags = []
    for a in arr:
        if a["rma"] and a["rma"] in orig_by_rma:
            try:
                t0 = datetime.strptime(orig_by_rma[a["rma"]]["datetime"], "%Y-%m-%d %H:%M:%S")
                t1 = datetime.strptime(a["datetime"], "%Y-%m-%d %H:%M:%S")
                d = (t1 - t0).total_seconds() / 3600
                if d >= 0: lags.append(d)
            except Exception: pass
    lags.sort()
    ever = len(set(a["rma"] for a in arr if a["rma"]) & set(orig_by_rma.keys()))
    arrest = {"orig_rma": len(orig_by_rma), "ever_arrest": ever,
              "rate": round(ever / len(orig_by_rma) * 100, 1) if orig_by_rma else 0,
              "median_days": round(lags[len(lags)//2] / 24, 1) if lags else None,
              "within72": round(sum(1 for x in lags if x <= 72) / len(lags) * 100) if lags else None,
              "matched": len(lags)}
    by_day = Counter(r["date"] for r in rows)
    days = sorted(by_day)
    hom = [r for r in rows if 'homicide' in (r['offense'] or '').lower() or 'homicide' in r['subject'].lower()]
    valid_rma = [int(r["rma"]) for r in crime if r["rma"] and r["rma"].isdigit() and int(r["rma"]) < 1700]
    return {
        "meta": {"total": len(rows), "crime": len(crime), "original": len(orig),
                 "start": days[0], "end": days[-1], "days": len(days),
                 "avgday": round(len(rows) / len(days), 1) if days else 0,
                 "rma_max": max(valid_rma) if valid_rma else 0},
        "monthly": monthly, "offense": offense, "boroughs": boroughs, "precincts": precincts,
        "hour": hour, "arrest": arrest,
        "daily": [{"date": d, "count": by_day[d]} for d in days],
        "homicide": {"advisories": len(hom), "with_rma": len(set(r["rma"] for r in hom if r["rma"])),
                     "updates": sum(1 for r in hom if r["is_update"] == "1")},
        "pattern": {"messages": sum(1 for r in crime if r["is_pattern"] == "1"),
                    "unique": len(set(r["rma"] for r in crime if r["is_pattern"] == "1" and r["rma"]))},
        "found": sum(1 for r in rows if r["is_found"] == "1"),
    }

def main():
    with open(CSV) as f:
        rows = list(csv.DictReader(f))
    data = build(rows)
    with open(JSON, "w") as f:
        json.dump(data, f, indent=1)
    blob = json.dumps(data, separators=(",", ":"))
    html = open(HTML).read()
    new = re.sub(r"const DATA = .*?;\n", f"const DATA = {blob};\n", html, count=1, flags=re.S)
    if new == html:
        print("WARNING: DATA blob not replaced — check the marker in index.html", file=sys.stderr)
        sys.exit(1)
    open(HTML, "w").write(new)
    print(f"Rebuilt: {data['meta']['total']} rows, {data['meta']['start']} to {data['meta']['end']}, RMA max {data['meta']['rma_max']}")

if __name__ == "__main__":
    main()
