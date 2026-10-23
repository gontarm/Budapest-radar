#!/usr/bin/env python3
"""Conservative structured-data importer for theatre_sources.json.

Watches all registered theatre sites. Imports ONLY dated schema.org Event
entries whose published location explicitly indicates Budapest or Vienna.
A watched source is not claimed to have a working full-schedule parser.
"""
import concurrent.futures as cf
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
UA={"User-Agent":"Mozilla/5.0 (compatible; RadarTheatre/1.0)"}
class Scripts(HTMLParser):
 def __init__(self):super().__init__();self.active=False;self.stack=[];self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag=="script" and dict(attrs).get("type","").lower()=="application/ld+json":
   self.active=True;self.parts=[]
 def handle_data(self,data):
  if self.active:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag=="script" and self.active:
   self.stack.append("".join(self.parts));self.active=False
def walk(data):
 if isinstance(data,list):
  for v in data:yield from walk(v)
 elif isinstance(data,dict):
  types=data.get("@type",[])
  if isinstance(types,str):types=[types]
  if any(str(t).split("/")[-1]=="Event" or str(t).endswith("Event") for t in types):yield data
  for v in data.values():
   if isinstance(v,(dict,list)):yield from walk(v)
def parse(source,city):
 url=source["url"]
 request=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(request,timeout=9) as response:
  page=response.read(1_400_000).decode("utf-8","replace")
 parser=Scripts();parser.feed(page)
 rows=[]
 zone=ZoneInfo("Europe/Budapest" if city=="budapest" else "Europe/Vienna")
 today=dt.datetime.now(zone).date()
 for raw in parser.stack:
  try:structured=json.loads(raw)
  except ValueError:continue
  for event in walk(structured):
   title=event.get("name","")
   start=str(event.get("startDate") or "")
   try:date=dt.date.fromisoformat(start[:10])
   except ValueError:continue
   if not today<=date<=today+dt.timedelta(days=365):continue
   loc=event.get("location")
   if not loc:continue
   place=json.dumps(loc,ensure_ascii=False).casefold()
   city_name="budapest" if city=="budapest" else "wien"
   if city_name not in place and (city!="vienna" or "vienna" not in place):continue
   event_url=urllib.parse.urljoin(url,str(event.get("url") or url))
   p=urllib.parse.urlparse(event_url)
   base=urllib.parse.urlparse(url)
   if p.scheme!="https" or p.netloc!=base.netloc or p.path.rstrip("/")==base.path.rstrip("/"):continue
   if not isinstance(title,str) or len(title.strip())<4:continue
   venue=(loc.get("name") if isinstance(loc,dict) else None) or source["name"]
   if isinstance(loc,dict):
    address=loc.get("address")
    if isinstance(address,dict):venue+=" · "+", ".join(str(address.get(k,"")) for k in ("streetAddress","addressLocality") if address.get(k))
   uid="theatre-schema-"+hashlib.sha256((city+event_url+str(date)).encode()).hexdigest()[:20]
   rows.append(dict(id=uid,title=title.strip()[:160],kind="élmény",interestTopics=["szinhaz"],
       where=str(venue)[:180],date=date.isoformat(),dateLabel=date.isoformat()+" · időpont a színháznál",
       desc="Színházi esemény a szervező oldalán közölt strukturált adatok alapján. Indulás előtt ellenőrizd a kezdést és a jegyeket.",
       url=event_url,source=source["name"]+" – hivatalos eseményadat",score=84,
       dataQuality="scheduled",eventVerified=False))
 return rows

def main():
 watch=json.loads((ROOT/"theatre_sources.json").read_text("utf-8"))["cities"]
 tasks=[(city,item) for city,items in watch.items() for item in items]
 found={"budapest":[],"vienna":[]};success=0
 with cf.ThreadPoolExecutor(max_workers=10) as executor:
  futures={executor.submit(parse,item,city):(city,item["name"]) for city,item in tasks}
  for future in cf.as_completed(futures):
   city,name=futures[future]
   try:
    result=future.result();found[city].extend(result);success+=1
    print(city,name,"dated events",len(result))
   except Exception as ex:print(city,name,"unavailable:",str(ex)[:90])
 for city,entries in found.items():
  path=ROOT/("events.json" if city=="budapest" else "vienna-events.json")
  existing=json.loads(path.read_text("utf-8"))
  zone=ZoneInfo("Europe/Budapest" if city=="budapest" else "Europe/Vienna")
  today=dt.datetime.now(zone).date().isoformat()
  by_id={e["id"]:e for e in existing if not e.get("id","").startswith("theatre-schema-") or e.get("date","")>=today}
  for e in entries:by_id[e["id"]]=e
  content=json.dumps(list(by_id.values()),ensure_ascii=False,indent=2)+"\n"
  if content!=path.read_text("utf-8"):path.write_text(content,"utf-8")
  print(city,"official structured performances",len(entries))
 print("Reachable theatre source pages:",success,"of",len(tasks))
 if not success:raise RuntimeError("All theatre pages unavailable; previous data preserved")
if __name__=="__main__":main()
