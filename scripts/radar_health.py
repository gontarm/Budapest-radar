#!/usr/bin/env python3
"""Auditable event freshness report for Budapest Radar.

Prune only expired automatically scraped, date-specific events. Never remove
hand-curated entries, unverified news leads or any upcoming event.
"""
import argparse
import collections
import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
FILES=(("Budapest","events.json","Europe/Budapest"),("Bécs","vienna-events.json","Europe/Vienna"))
AUTO_PREFIXES=("cinema-","theatre-","theatre-schema-","official-")
CATEGORIES=("mozi","színház","tudomány","egyéb")
def category(e):
 if e.get("kind")=="mozi":return "mozi"
 if "szinhaz" in e.get("interestTopics",[]) or str(e.get("id","")).startswith("theatre-"):return "színház"
 if e.get("kind")=="tudomány":return "tudomány"
 return "egyéb"

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--prune",action="store_true")
 ap.add_argument("--summary",action="store_true")
 args=ap.parse_args()
 report=[]
 for city,filename,timezone in FILES:
  path=ROOT/filename
  rows=json.loads(path.read_text("utf-8"))
  today=dt.datetime.now(ZoneInfo(timezone)).date().isoformat()
  retained=[e for e in rows if not (str(e.get("id","")).startswith(AUTO_PREFIXES)
                              and e.get("date") and e["date"]<today)]
  removed=len(rows)-len(retained)
  if args.prune and removed:path.write_text(json.dumps(retained,ensure_ascii=False,indent=2)+"\n","utf-8")
  present=retained if args.prune else rows
  upcoming=[e for e in present if isinstance(e.get("date"),str) and e["date"]>=today]
  counts=collections.Counter(category(e) for e in upcoming)
  distinct=collections.defaultdict(set)
  for e in upcoming:distinct[category(e)].add(str(e.get("title","")).casefold().strip())
  count_new=sum(e.get("discovered")==today for e in upcoming)
  line=f"{city}: {len(present)} összes; {len(upcoming)} jövőbeli; {count_new} ma felfedezett jövőbeli; lejárt automatikus: {removed} eltávolítva"
  report.append(line)
  report.append(" | ".join(f"{k}: {counts[k]} időpont / {len(distinct[k])} különböző cím" for k in CATEGORIES))
  if not counts["mozi"] and city=="Budapest":
   report.append("FIGYELMEZTETÉS: egyetlen aktuális budapesti mozivetítés sincs az adatbázisban.")
  if not counts["színház"]:
   report.append("FIGYELMEZTETÉS: nincs aktuális színházi műsor a városban.")
 output="\n".join(report)
 print(output)
 if args.summary and os.environ.get("GITHUB_STEP_SUMMARY"):
  with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
   f.write("\n### Radar – programadatok frissessége\n\n")
   f.write("\n".join("- "+line for line in report)+"\n")
if __name__=="__main__":main()
