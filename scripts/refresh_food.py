#!/usr/bin/env python3
"""Conservative gastronomy discovery: find candidate openings in recent public RSS.
A news article is never proof a venue is open or located in the target city.
Candidates are kept separately for editorial review, never published as places.
"""
import datetime as dt
import email.utils
import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUTPUT=ROOT/"food_candidates.json"
SOURCES={
 "budapest":[
  'Budapest új étterem nyitott meg 2026',
  'Budapest új koktélbár söröző megnyitó 2026',
  'Budapest különleges étterem tetőterasz üvegház rejtett kert'],
 "vienna":[
  'Wien neues Restaurant eröffnet 2026',
  'Wien neue Cocktailbar Craft Beer Eröffnung 2026',
  'Wien Restaurant Glashaus versteckter Garten Rooftop']
}
SIGNALS=("étterem","restaurant","bár","bar","söröző","bier","gasztr","gastronom","rooftop","kert","garten","eröffn","nyit","lokál","lokal","brasserie")
REJECT=("interjú","interview","podcast","recept","recipe","lakás","ingatlan","politika")
def discover(city,query):
 language,country=("hu","HU") if city=="budapest" else ("de","AT")
 u="https://news.google.com/rss/search?q="+urllib.parse.quote(query+" when:14d")+f"&hl={language}&gl={country}&ceid={country}:{language}"
 request=urllib.request.Request(u,headers={"User-Agent":"BudapestRadar/1.0"})
 with urllib.request.urlopen(request,timeout=18) as response:
  xml=ET.fromstring(response.read(1200000))
 now=dt.datetime.now(dt.timezone.utc)
 results=[]
 for item in xml.findall("./channel/item"):
  title=item.findtext("title","").strip()
  link=item.findtext("link","").strip()
  low=title.casefold()
  if len(title)<14 or not link.startswith("https://"):continue
  if not any(x in low for x in SIGNALS) or any(x in low for x in REJECT):continue
  try:
   published=email.utils.parsedate_to_datetime(item.findtext("pubDate",""))
   if published.tzinfo is None:published=published.replace(tzinfo=dt.timezone.utc)
   if not 0<=(now-published).days<=14:continue
  except (TypeError,ValueError,OverflowError):continue
  results.append({"id":"food-lead-"+hashlib.sha256((city+title.casefold()).encode()).hexdigest()[:18],
   "city":city,"headline":title[:180],"articleUrl":link,"published":published.date().isoformat(),
   "status":"candidate","note":"Nem ellenőrzött hírtalálat. A hely neve, pontos címe és működése még igazolandó."})
 return results
def main():
 existing=json.loads(OUTPUT.read_text("utf-8")) if OUTPUT.exists() else []
 cutoff=(dt.date.today()-dt.timedelta(days=21)).isoformat()
 rows={x["id"]:x for x in existing if x.get("published","")>=cutoff}
 failures=0
 for city,queries in SOURCES.items():
  for query in queries:
   try:
    leads=discover(city,query)
    for lead in leads:rows[lead["id"]]=lead
    print(city,len(leads),"candidates")
   except Exception as exc:
    failures+=1;print("Source failed",city,type(exc).__name__,str(exc)[:100])
 output=sorted(rows.values(),key=lambda x:x["published"],reverse=True)[:150]
 data=json.dumps(output,ensure_ascii=False,indent=2)+"\n"
 if not OUTPUT.exists() or OUTPUT.read_text("utf-8")!=data:OUTPUT.write_text(data,"utf-8")
 print("Food discovery candidates",len(output),"source failures",failures)
if __name__=="__main__":main()
