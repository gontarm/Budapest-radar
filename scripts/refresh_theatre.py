#!/usr/bin/env python3
"""Import dated theatre performances from two official theatre programme pages.

The collectors read published programme entries, not articles. Date, title and
venue must appear together. No date or theatre performance is guessed.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent.parent
UA={"User-Agent":"Mozilla/5.0 (compatible; BudapestRadar/1.0; event discovery)"}
HU_MONTHS={"január":1,"február":2,"március":3,"április":4,"május":5,"június":6,
"július":7,"augusztus":8,"szeptember":9,"október":10,"november":11,"december":12}
THEATRES={
 "katona":{"city":"budapest","url":"https://katonajozsefszinhaz.hu/musor/",
           "name":"Katona József Színház"},
 "burg":{"city":"vienna","url":"https://www.burgtheater.at/spielplan",
         "name":"Burgtheater Wien"},
}
def read(url):
 req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=28) as r:
  return r.read(3_000_000).decode("utf-8","replace")

def lines(html):
 soup=BeautifulSoup(html,"html.parser")
 for tag in soup(["script","style","nav","footer"]):tag.decompose()
 return [re.sub(r"\s+"," ",x).strip() for x in soup.get_text("\n").splitlines() if x.strip()]

def date_for(month,day,now):
 for year in (now.year,now.year+1):
  try:date=dt.date(year,month,day)
  except ValueError:continue
  if (date-now).days>=-1 and (date-now).days<=440:return date
 return None

def create(city,source,title,venue,date,time,url):
 if not title or len(title)<3 or not venue or not re.fullmatch(r"\d\d:\d\d",time):return None
 today=dt.datetime.now(ZoneInfo("Europe/Budapest" if city=="budapest" else "Europe/Vienna")).date()
 if date<today or date>today+dt.timedelta(days=400):return None
 key="theatre|"+city+"|"+source+"|"+title.casefold()+"|"+str(date)+"|"+time
 eid="theatre-"+hashlib.sha256(key.encode()).hexdigest()[:20]
 return dict(id=eid,title=title,kind="élmény",interestTopics=["szinhaz"],where=venue,
     date=date.isoformat(),dateLabel=f"{date:%Y.%m.%d.} · {time}",
     desc="A színház hivatalos műsorában szereplő előadás. A jegyek elérhetőségét és az esetleges műsorváltozást a színháznál ellenőrizd.",
     url=url,source=source+" – hivatalos műsor",score=86,
     dataQuality="scheduled",eventVerified=False,
     discovered=today.isoformat())

def katona(html):
 rows=[]
 now=dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
 data=lines(html)
 pattern=re.compile(r"^(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+(\d{1,2})\s*/\s*[^\d\n]*?(\d\d:\d\d)",re.I)
 venues={
  "Katona József Színház - Kamra":"Katona József Színház – Kamra · Ferenciek tere 4., Budapest",
  "Katona József Színház - Cafe Katona":"Cafe Katona · Petőfi Sándor utca 6., Budapest",
  "Katona József Színház":"Katona József Színház · Petőfi Sándor utca 6., Budapest",
  "Sufni":"Katona József Színház – Sufni · Petőfi Sándor utca 6., Budapest"}
 for i,text in enumerate(data):
  m=pattern.search(text.casefold())
  if not m or i<2:continue
  date=date_for(HU_MONTHS[m.group(1)],int(m.group(2)),now)
  if not date:continue
  title=data[i-1]
  venue=venues.get(data[i-2])
  if not venue or title in venues or len(title)>155:continue
  row=create("budapest","Katona József Színház",title,venue,date,m.group(3),THEATRES["katona"]["url"])
  if row:rows.append(row)
 return rows

def burg(html):
 rows=[]
 now=dt.datetime.now(ZoneInfo("Europe/Vienna")).date()
 data=lines(html)
 venues={
  "Burgtheater":"Burgtheater · Universitätsring 2, 1010 Wien",
  "Akademietheater":"Akademietheater · Lisztstraße 1, 1030 Wien",
  "Kasino":"Kasino am Schwarzenbergplatz · Schwarzenbergplatz 1, 1010 Wien",
  "Vestibül":"Vestibül · Universitätsring 2, 1010 Wien"}
 # Printed calendar order: weekday, dd.mm., HH:MM Uhr, venue, title.
 datepat=re.compile(r"^(\d{1,2})\.(\d{1,2})\.$")
 timepat=re.compile(r"^(\d{1,2}:\d{2})\s*Uhr")
 for i,item in enumerate(data):
  m=datepat.fullmatch(item)
  if not m:continue
  date=date_for(int(m.group(2)),int(m.group(1)),now)
  if not date:continue
  time=None;venue=None;title=None
  for j in range(i+1,min(i+14,len(data))):
   if datepat.fullmatch(data[j]):break
   if not time:
    a=timepat.match(data[j])
    if a:time=a.group(1)
   if not venue and data[j] in venues:
    venue=venues[data[j]]
    if j+1<len(data):title=data[j+1]
    break
  if not (time and venue and title) or len(title)>160:continue
  if title.lower() in ("tickets","premiere","einführung","ausverkauft"):continue
  row=create("vienna","Burgtheater",title,venue,date,time,THEATRES["burg"]["url"])
  if row:rows.append(row)
 return rows

def integrate(city,new):
 path=ROOT/("events.json" if city=="budapest" else "vienna-events.json")
 old=json.loads(path.read_text(encoding="utf-8"))
 today=dt.datetime.now(ZoneInfo("Europe/Budapest" if city=="budapest" else "Europe/Vienna")).date().isoformat()
 # Keep old saved-event IDs available; skip equivalent manually curated performances.
 seen={(x.get("date"),re.sub(r"[^\w]+","",x.get("title","").casefold()))
       for x in old if x.get("date") and not x.get("id","").startswith("theatre-")}
 merged=[x for x in old if not x.get("id","").startswith("theatre-") or x.get("date","")>=today]
 ids={x["id"] for x in merged}
 count=0
 for x in new:
  dedup=(x["date"],re.sub(r"[^\w]+","",x["title"].casefold()))
  if x["id"] in ids or dedup in seen:continue
  merged.append(x);ids.add(x["id"]);seen.add(dedup);count+=1
 content=json.dumps(merged,ensure_ascii=False,indent=2)+"\n"
 if path.read_text(encoding="utf-8")!=content:path.write_text(content,encoding="utf-8")
 print(city,"new theatre entries",count,"total",sum("szinhaz" in x.get("interestTopics",[]) and bool(x.get("date")) for x in merged))

def main():
 success=0
 for name,settings in THEATRES.items():
  try:
   html=read(settings["url"])
   entries=(katona if name=="katona" else burg)(html)
   if not entries:raise RuntimeError("No dated performances found – parsing may need updating")
   integrate(settings["city"],entries)
   success+=1
  except Exception as exc:
   print("Source failed",settings["name"],type(exc).__name__,str(exc)[:160])
 if not success:raise RuntimeError("No official theatre programme was parsed; existing data retained")
if __name__=="__main__":main()
