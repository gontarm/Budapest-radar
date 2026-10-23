#!/usr/bin/env python3
"""Official-source event ingestion. Strictly requires dated, linked event entries.

Source-specific parsing is intentionally conservative. Failure must never produce
fabricated dates, fake venues, or articles presented as events.
"""
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; RadarEvents/1.0)"}
SOURCES=[
 dict(city="budapest",name="Svábhegyi Csillagvizsgáló",url="https://svabhegyicsillagvizsgalo.hu/programok-a-csillagvizsgaloban",
      base="https://svabhegyicsillagvizsgalo.hu",where="Svábhegyi Csillagvizsgáló · Budapest, Konkoly-Thege Miklós út 15–17.",
      topic="vilagegyetem",kind="tudomány"),
 dict(city="vienna",name="Wien Museum",url="https://www.wienmuseum.at/veranstaltungen",
      base="https://www.wienmuseum.at",where="Wien Museum · Karlsplatz 8, 1040 Wien",
      topic="tortenelem",kind="élmény"),
 dict(city="vienna",name="Technisches Museum Wien",url="https://www.technischesmuseum.at/veranstaltungen",
      base="https://www.technischesmuseum.at",where="Technisches Museum Wien · Mariahilfer Straße 212, 1140 Wien",
      topic="technika",kind="élmény")
]
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.current=None;self.structured=[];self.ld=False
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if tag=="a":self.current={"href":d.get("href",""),"text":""}
  if tag=="script" and d.get("type")=="application/ld+json":self.ld=True;self.structured.append("")
 def handle_data(self,data):
  if self.current is not None:self.current["text"]+=data
  if self.ld:self.structured[-1]+=data
 def handle_endtag(self,tag):
  if tag=="a" and self.current is not None:self.links.append(self.current);self.current=None
  if tag=="script":self.ld=False
def request(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=20) as r:return r.read(1_700_000).decode("utf-8","replace")
def walk(node):
 if isinstance(node,list):
  for x in node:yield from walk(x)
 if isinstance(node,dict):
  if "Event" in str(node.get("@type","")):yield node
  for v in node.values():
   if isinstance(v,(dict,list)):yield from walk(v)
def record(src,title,date,url,description=""):
 try:date=dt.date.fromisoformat(date[:10]).isoformat()
 except (TypeError,ValueError):return None
 tz=ZoneInfo("Europe/Budapest" if src["city"]=="budapest" else "Europe/Vienna")
 if date<dt.datetime.now(tz).date().isoformat():return None
 if not title or len(title)<7 or not url.startswith(src["base"]+"/"):return None
 eid="official-"+hashlib.sha256((src["city"]+url+date).encode()).hexdigest()[:18]
 return {"id":eid,"title":title.strip()[:160],"kind":src["kind"],"interestTopics":[src["topic"]],
  "where":src["where"],"date":date,"dateLabel":date+" · kezdés a szervező oldalán",
  "desc":description.strip()[:430] or "Hivatalos szervezői programadat. A részleteket és jegyeket a forrásoldalon ellenőrizd.",
  "url":url,"source":src["name"]+" – hivatalos program","score":85,
  "dataQuality":"scheduled","eventVerified":False,"discovered":dt.datetime.now(tz).date().isoformat()}
def jsonld(src,page,page_url):
 parser=Links();parser.feed(page)
 result=[]
 for text in parser.structured:
  try:obj=json.loads(text)
  except (ValueError,TypeError):continue
  for e in walk(obj):
   title=e.get("name") or ""
   start=e.get("startDate") or ""
   location=e.get("location")
   # Do not assign a venue unless its structured location references the source venue.
   venue=json.dumps(location,ensure_ascii=False).casefold() if location else ""
   if location and src["name"].casefold().split()[0] not in venue and src["city"] not in venue:continue
   url=urllib.parse.urljoin(page_url,str(e.get("url") or page_url))
   desc=re.sub(r"<[^>]+>"," ",str(e.get("description") or ""))
   item=record(src,str(title),str(start),url,html.unescape(desc))
   if item:result.append(item)
 return result,parser.links

# Svábhegyi's public calendar provides per-event detail pages containing an
# explicit 'October 25. 2026' style full date. Read that page before admitting it.
MONTHS={"január":1,"február":2,"március":3,"április":4,"május":5,"június":6,
 "július":7,"augusztus":8,"szeptember":9,"október":10,"november":11,"december":12}
def observatory(src,links):
 results=[]
 seen=set()
 for a in links:
  url=urllib.parse.urljoin(src["url"],a["href"]).split("#")[0]
  if not url.startswith(src["base"]+"/programok-a-csillagvizsgaloban/") or url in seen:continue
  seen.add(url)
  if len(seen)>55:break
  try:page=request(url)
  except Exception:continue
  plain=html.unescape(re.sub(r"<[^>]+>"," ",page))
  plain=" ".join(plain.split())
  m=re.search(r"(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+(\d{1,2})\.\s+(20\d{2})",plain,re.I)
  title=re.search(r"<h1[^>]*>(.*?)</h1>",page,re.I|re.S)
  if not m or not title:continue
  day=f"{int(m.group(3)):04d}-{MONTHS[m.group(1).casefold()]:02d}-{int(m.group(2)):02d}"
  name=html.unescape(re.sub(r"<[^>]+>"," ",title.group(1))).strip()
  item=record(src,name,day,url)
  if item:results.append(item)
 return results
def main():
 all_rows={"budapest":[],"vienna":[]}
 for src in SOURCES:
  try:
   page=request(src["url"])
   rows,links=jsonld(src,page,src["url"])
   # For official sites without structured Event data, inspect linked detail
   # pages, but accept them only if they publish schema.org Event JSON-LD.
   if src["name"]=="Svábhegyi Csillagvizsgáló":rows.extend(observatory(src,links))
   else:
    visited=set()
    for link in links:
     href=urllib.parse.urljoin(src["url"],link["href"]).split("#")[0]
     if href in visited or not href.startswith(src["base"]+"/"):continue
     if not re.search(r"veranstaltung|event|fuehrung|fuehrungen|programm",href,re.I):continue
     visited.add(href)
     if len(visited)>15:break
     try:r,_=jsonld(src,request(href),href);rows.extend(r)
     except Exception:continue
   all_rows[src["city"]].extend(rows)
   print(src["name"],"dated official events:",len(rows))
  except Exception as exc:print(src["name"],"unavailable:",type(exc).__name__,str(exc)[:130])
 for city,rows in all_rows.items():
  path=ROOT/("events.json" if city=="budapest" else "vienna-events.json")
  old=json.loads(path.read_text("utf-8"))
  # Retain curated events and historical IDs, but prune expired official-source entries.
  today=dt.datetime.now(ZoneInfo("Europe/Vienna" if city=="vienna" else "Europe/Budapest")).date().isoformat()
  unique={x["id"]:x for x in old if not x.get("id","").startswith("official-") or x.get("date","")>=today}
  for r in rows:unique[r["id"]]=r
  text=json.dumps(list(unique.values()),ensure_ascii=False,indent=2)+"\n"
  if text!=path.read_text("utf-8"):path.write_text(text,"utf-8")
  print(city,"official imported",len(rows))
if __name__=="__main__":main()
