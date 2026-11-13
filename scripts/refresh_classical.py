#!/usr/bin/env python3
"""Import dated classical concerts from official Budapest organiser calendars.\n\nUse the organiser programme link, not guessed ticket or event URLs.

Never infer a performance date from a news headline. A failed source retains
previously collected, still-upcoming classical concerts from that source.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"concerts.json"
TODAY=dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; BudapestRadar/1.1; public concert calendar)"}
MONTHS={"január":1,"február":2,"március":3,"április":4,"május":5,"június":6,"július":7,
        "augusztus":8,"szeptember":9,"október":10,"november":11,"december":12}
NF="https://www.filharmonikusok.hu/koncertek/?helyszin=budapest"
MUPA="https://mupa.hu/en"
ZENE="https://koncert.zeneakademia.hu/programok"
DATE_RE=re.compile(r"^20\d\d\.\s*(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+\d{1,2}\.",re.I)
IGNORE=("épületlátogatás","vezetett séta","workshop","nyitott nap","building tour","guided tour",
        "filmklub","film screening","talk","podcast","literárium","táncház")
GENRE_HINTS=("classical","chamber","quartet","quartett","orchestra","symphon","philharm",
             "zenekar","filharmon","kamarakoncert","kamarazene","orgona","opera","zongora",
             "kórus","beethoven","mozart","bach","haydn","bartók","liszt","brahms","dohnányi",
             "schubert","mahler","vivaldi","concertgebouw","cello","violin","vonós")
def clean(text):return re.sub(r"\s+"," ",str(text)).strip()
def fetch(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=23) as resp:return resp.read(2_500_000).decode("utf-8","replace")
def asdate(text):
 m=re.search(r"(20\d\d)\.\s*("+ "|".join(MONTHS)+r")\s*(\d{1,2})\.",text,re.I)
 if m:
  try:return dt.date(int(m.group(1)),MONTHS[m.group(2).casefold()],int(m.group(3)))
  except ValueError:return None
 m=re.search(r"(20\d\d)-(\d\d)-(\d\d)(?!\d)",text)
 if m:
  try:return dt.date(*map(int,m.groups()))
  except ValueError:return None
 return None
def make(source,title,date,time,venue,url,description=""):
 title=clean(title);venue=clean(venue);description=clean(description)
 if not isinstance(date,dt.date) or not TODAY<=date<=TODAY+dt.timedelta(days=270):return None
 if not (5<=len(title)<=170) or not venue or "budapest" not in venue.casefold():return None
 if not url.startswith("https://"):return None
 if any(x in title.casefold() for x in IGNORE):return None
 stamp=f"{date:%Y.%m.%d.}"+(" · "+time if time else " · kezdés a forrásban")
 identifier="classical-"+hashlib.sha256((source+"|"+title.casefold()+"|"+date.isoformat()+"|"+time+"|"+venue.casefold()).encode()).hexdigest()[:21]
 return {"id":identifier,"title":title,"kind":"koncert","genre":"klasszikus","where":venue,
         "date":date.isoformat(),"dateLabel":stamp,"desc":description[:350] or "Hivatalos koncertnaptárban meghirdetett klasszikus zenei program. A jegyeket és kezdési időt indulás előtt ellenőrizd.",
         "url":url,"source":source,"score":87,"dataQuality":"scheduled","eventVerified":False,
         "discovered":TODAY.isoformat(),"ticketStatus":"unknown"}

def national_philharmonic(html):
 """The National Philharmonic page lists date / venue / time / concert title in order."""
 soup=BeautifulSoup(html,"html.parser")
 for tag in soup(["script","style","nav","footer"]):tag.decompose()
 lines=[clean(x) for x in soup.get_text("\n").splitlines() if clean(x)]
 links={}
 for a in soup.select("a[href]"):
  title=clean(a.get_text(" ",strip=True))
  if len(title)>=7:
   link=urllib.parse.urljoin(NF,a.get("href",""))
   if link.startswith("https://www.filharmonikusok.hu/") and link!=NF:links.setdefault(title,link)
 rows=[]
 for i,line in enumerate(lines):
  if not DATE_RE.match(line):continue
  date=asdate(line)
  if date is None:continue
  window=lines[i+1:i+17]
  city_idx=next((j for j,x in enumerate(window[:7]) if x.strip().casefold()=="budapest"),None)
  if city_idx is None or city_idx==0:continue
  venue=window[city_idx-1].rstrip(",")+" · Budapest"
  if venue.casefold().startswith(("évad","jegy")):continue
  # Use the full HH:MM, never only the hour.
  time=next((m.group(0).split("-")[0] for x in window[:11] if (m:=re.search(r"\b(?:[01]?\d|2[0-3]):[0-5]\d-tól",x))),"")
  title=next((x for x in window[city_idx+1:] if x in links),None)
  if not title:continue
  item=make("Nemzeti Filharmonikusok – hivatalos koncertnaptár",title,date,time,venue,links[title])
  if item:rows.append(item)
 return list({x["id"]:x for x in rows}.values())

def walk(value):
 if isinstance(value,list):
  for x in value:yield from walk(x)
 elif isinstance(value,dict):
  kind=value.get("@type",[])
  if isinstance(kind,str):kind=[kind]
  if any(str(x).split("/")[-1].endswith("Event") for x in kind):yield value
  for sub in value.values():
   if isinstance(sub,(dict,list)):yield from walk(sub)

def parse_schema(html,page_url,source):
 """Only published schema.org events with an explicit Budapest venue qualify."""
 soup=BeautifulSoup(html,"html.parser");rows=[]
 for node in soup.select('script[type="application/ld+json"]'):
  try:parsed=json.loads(node.string or node.get_text())
  except (ValueError,TypeError):continue
  for event in walk(parsed):
   title=clean(event.get("name",""))
   if not any(x in title.casefold() for x in GENRE_HINTS):continue
   start=str(event.get("startDate",""))
   date=asdate(start)
   if not date:continue
   location=event.get("location") or {}
   if isinstance(location,list):location=next((x for x in location if isinstance(x,dict)),{})
   if not isinstance(location,dict):continue
   place=clean(location.get("name",""))
   addr=location.get("address") or {}
   if isinstance(addr,dict):
    place=clean(place+" · "+", ".join(str(addr.get(k,"")) for k in ("streetAddress","addressLocality") if addr.get(k)))
   elif isinstance(addr,str):place=clean(place+" · "+addr)
   if "budapest" not in place.casefold():continue
   event_url=urllib.parse.urljoin(page_url,str(event.get("url") or page_url))
   parsed_url=urllib.parse.urlsplit(event_url)
   page_host=urllib.parse.urlsplit(page_url).hostname
   if parsed_url.scheme!="https" or parsed_url.hostname!=page_host:continue
   desc=clean(BeautifulSoup(str(event.get("description","")),"html.parser").get_text(" ",strip=True))
   time=start[11:16] if re.match(r"^\d\d:\d\d$",start[11:16]) else ""
   item=make(source,title,date,time,place,event_url,desc)
   if item:rows.append(item)
 return rows

def detail_links(html,base,pattern):
 soup=BeautifulSoup(html,"html.parser")
 urls=[]
 for a in soup.select("a[href]"):
  url=urllib.parse.urljoin(base,a["href"]).split("#")[0]
  if urllib.parse.urlsplit(url).hostname!=urllib.parse.urlsplit(base).hostname:continue
  if not re.search(pattern,urllib.parse.urlsplit(url).path,re.I):continue
  if url not in urls:urls.append(url)
 return urls

def zeneakademia():
 results=[]
 for offset in range(2):
  month=TODAY.month+offset;year=TODAY.year+(month-1)//12;month=(month-1)%12+1
  end=(dt.date(year+1,1,1)-dt.timedelta(days=1)).day if month==12 else (dt.date(year,month+1,1)-dt.timedelta(days=1)).day
  calendar=ZENE+"?idopont="+f"{year}-{month:02d}-01+to+{year}-{month:02d}-{end:02d}"
  html=fetch(calendar)
  links=detail_links(html,ZENE,r"/(?:programok|esemenyek)/[^/?#]+")
  for link in links[:55]:
   try:results.extend(parse_schema(fetch(link),link,"Zeneakadémia – hivatalos koncertnaptár"))
   except Exception:continue
 print("Zeneakadémia schema concerts:",len(results))
 return results

def mupa():
 # The home page has classical and popular sections; only event-specific
 # detail pages with Event JSON-LD and classical title signals are accepted.
 html=fetch(MUPA)
 links=detail_links(html,MUPA,r"/(?:program|event|events|programok)/[^/?#]+")
 results=[]
 for link in links[:45]:
  try:results.extend(parse_schema(fetch(link),link,"Müpa – hivatalos koncertnaptár"))
  except Exception:continue
 print("Müpa classical schema concerts:",len(results))
 return results

def main():
 previous=json.loads(OUT.read_text("utf-8"))
 by_id={x["id"]:x for x in previous if not str(x.get("id","")).startswith("classical-")
        or (x.get("date") or "")>=TODAY.isoformat()}
 results=[];success=0
 for name,fn in (("Nemzeti Filharmonikusok",lambda:national_philharmonic(fetch(NF))),
                 ("Zeneakadémia",zeneakademia),("Müpa",mupa)):
  try:
   entries=fn();results.extend(entries);success+=1
   print(name,"dated classical events:",len(entries))
  except Exception as exc:print(name,"unavailable:",type(exc).__name__,str(exc)[:170])
 if not success:raise RuntimeError("All classical concert source calendars unavailable; old entries retained")
 # Prefer current official calendar records when a previously verified seed
 # represents the same concert. Keep shared links stable unless a replacement
 # record is genuinely equivalent (same title, date and venue).
 def signature(e):
  return (e.get("date",""),clean(e.get("title","")).casefold(),clean(e.get("where","")).casefold())
 sigs={signature(e):key for key,e in by_id.items() if str(key).startswith("classical-")}
 for e in results:
  previous_id=sigs.get(signature(e))
  if previous_id and previous_id!=e["id"] and previous_id.startswith("classical-verified-"):
   by_id.pop(previous_id,None)
  by_id[e["id"]]=e
 rows=sorted(by_id.values(),key=lambda x:(0 if x.get("date") else 1,x.get("date") or x.get("discovered","")))
 serialized=json.dumps(rows,ensure_ascii=False,indent=2)+"\n"
 if OUT.read_text("utf-8")!=serialized:OUT.write_text(serialized,"utf-8")
 print("Classical new imported:",len(results),"Total concert entries:",len(rows))
if __name__=="__main__":main()
