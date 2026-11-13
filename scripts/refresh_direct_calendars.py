#!/usr/bin/env python3
"""Verified dated discoveries outside theatres and cinemas.

Sources are dated event calendars and curated event listings, not RSS news.\nNews results are never converted into
scheduled events. Reject unknown dates, unknown Budapest venues and old dates.
"""
import concurrent.futures as cf
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
FILE=ROOT/"events.json"
TODAY=dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; BudapestRadar/1.0; event listings)"}
MONTHS={"január":1,"február":2,"március":3,"április":4,"május":5,"június":6,
        "július":7,"augusztus":8,"szeptember":9,"október":10,"november":11,"december":12}
DATE_MTA=re.compile(r"^(20\d\d)\.\s*(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+(\d{1,2})\.,?\s*(\d{1,2})(?::(\d{2}))?\s*óra",re.I)
DATE_PSY=re.compile(r"^(20\d\d)\.(\d\d)\.(\d\d)\.?$")
PSY_SOURCE="https://www.programturizmus.hu/ajanlat-pszihologiai-program-eloadas-budapest.html"
MTA_SOURCES=("https://mta.hu/esemenynaptar/","https://mta.hu/mtu_esemenynaptar")
PSY_TERMS=("pszichológ","lélek","önismer","kötődés","párkapcsol","almási","szily","pszicho","trauma","függőség","mentál","stressz","érzelem","önbizalom","kommunikáció","motiváció","szorongás")
HISTORY_TERMS=("történ","régész","emlékezet","örökség","múzeum","hajógyár","építészet","várostörtén","helytörtén")
SPECIAL_TERMS=("séta","bejárás","kulissza","pince","kert","workshop","foglalkozás","tárlatvezetés","kiállítás","kézműves")
SCIENCE_TERMS=("kutat","tudomány","csillag","fizika","matematik","orvos","biológ","kémia","meteorológ","drón","energi","geológ","szimpózium","akadém","természet")
def fetch(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=25) as resp:
  return resp.read(2_500_000).decode("utf-8","replace")
def clean(value):
 return re.sub(r"\s+"," ",value).strip()
def classify(title,description="",default="tudomány"):
 text=(title+" "+description).casefold()
 if any(term in text for term in PSY_TERMS):return "pszichológia",[]
 if any(term in text for term in HISTORY_TERMS):return "élmény",["tortenelem"]
 if any(term in text for term in SPECIAL_TERMS):return "élmény",["titkok"]
 if any(term in text for term in SCIENCE_TERMS):return "tudomány",["termeszettudomany"]
 return default,["termeszettudomany"] if default=="tudomány" else ["titkok"]
def record(source,title,date,where,url,description="",kind=None,topics=None,time=""):
 if not isinstance(date,dt.date) or not TODAY<=date<=TODAY+dt.timedelta(days=180):return None
 if len(title)<8 or len(title)>190 or "budapest" not in where.casefold():return None
 if not url.startswith("https://"):return None
 if kind is None:kind,topics=classify(title,description)
 if topics is None:_,topics=classify(title,description)
 uid="radar-dated-"+hashlib.sha256((source+"|"+title.casefold()+"|"+str(date)+"|"+where.casefold()).encode()).hexdigest()[:20]
 return dict(id=uid,title=title,kind=kind,interestTopics=topics,where=where,
             date=date.isoformat(),dateLabel=f"{date:%Y.%m.%d.}"+(" · "+time if time else " · időpont a forrásban"),
             desc=description[:450] or "Nyilvános programnaptárban közölt időpont. A részvétel feltételeit a forrásoldalon ellenőrizd.",
             url=url,source=source,score=83,dataQuality="scheduled",eventVerified=False,
             discovered=TODAY.isoformat())

def parse_mta(page,source_url):
 soup=BeautifulSoup(page,"html.parser")
 for tag in soup(["script","style","nav","footer"]):tag.decompose()
 lines=[clean(x) for x in soup.get_text("\n").splitlines() if clean(x)]
 links={}
 for a in soup.select("a[href]"):
  text=clean(a.get_text(" ",strip=True))
  href=urllib.parse.urljoin(source_url,a.get("href",""))
  if text and re.search(r"/esemenynaptar/\d+|/mtu_esemenynaptar/\d+",href):
   links.setdefault(text,href)
 result=[]
 for i,line in enumerate(lines):
  match=DATE_MTA.match(line)
  if not match or i<3:continue
  year,month,day,hour,minute=match.groups()
  try:date=dt.date(int(year),MONTHS[month.casefold()],int(day))
  except ValueError:continue
  where=lines[i-1]
  typ=lines[i-2]
  title=lines[i-3]
  if "budapest" not in where.casefold():continue
  if len(title)<8 or not any(x in typ.casefold() for x in ("előadás","konferencia","szimpózium","vita","könyv","beszélgetés","tudományos","kerekasztal","ülés","műhely","hangverseny","bemutató")):continue
  url=links.get(title)
  if not url:continue
  row=record("Magyar Tudományos Akadémia – hivatalos eseménynaptár",title,date,where,url,
             typ, time=f"{int(hour):02d}:{int(minute or 0):02d}")
  if row:result.append(row)
 return result

def parse_psychology(page):
 soup=BeautifulSoup(page,"html.parser")
 for tag in soup(["script","style","nav","footer"]):tag.decompose()
 lines=[clean(x) for x in soup.get_text("\n").splitlines() if clean(x)]
 found=[]
 for i,line in enumerate(lines):
  m=DATE_PSY.fullmatch(line)
  if not m:continue
  try:date=dt.date(*map(int,m.groups()))
  except ValueError:continue
  if not TODAY<=date<=TODAY+dt.timedelta(days=180):continue
  title=lines[i+1] if i+1<len(lines) else ""
  if not (9<len(title)<150) or not any(t in title.casefold() for t in PSY_TERMS):continue
  nearby=lines[i+2:i+8]
  where=next((x for x in nearby if "Budapest" in x and ("kerület" in x or re.search(r"\b1\d{3}\b",x))),None)
  if not where:continue
  row=record("Programturizmus – dátumos pszichológiai programajánló",title,date,where,PSY_SOURCE,
             "A pontos helyszín és jegyvásárlás az ajánlóban ellenőrizhető.",
             kind="pszichológia",topics=[])
  if row:found.append(row)
 return found

def traverse_json(value):
 if isinstance(value,list):
  for v in value:yield from traverse_json(v)
 elif isinstance(value,dict):
  types=value.get("@type",[])
  if isinstance(types,str):types=[types]
  if any(str(t).split("/")[-1].endswith("Event") for t in types):yield value
  for sub in value.values():
   if isinstance(sub,(list,dict)):yield from traverse_json(sub)

def parse_obuda_detail(page,url):
 soup=BeautifulSoup(page,"html.parser")
 rows=[]
 for script in soup.select('script[type="application/ld+json"]'):
  try:data=json.loads(script.string or script.get_text())
  except (ValueError,TypeError):continue
  for event in traverse_json(data):
   title=clean(str(event.get("name","")))
   start=str(event.get("startDate",""))
   try:date=dt.date.fromisoformat(start[:10])
   except ValueError:continue
   location=event.get("location",{})
   if isinstance(location,list):location=next((x for x in location if isinstance(x,dict)),{})
   if not isinstance(location,dict):continue
   address=location.get("address",{})
   place=clean(str(location.get("name","")))
   if isinstance(address,dict):
    place=clean(place+" · "+", ".join(str(address.get(k,"")) for k in ("streetAddress","addressLocality") if address.get(k)))
   elif isinstance(address,str):place=clean(place+" · "+address)
   # Only accept an explicit Budapest locality, never infer from web domain.
   if "budapest" not in place.casefold():continue
   kind,topics=classify(title,str(event.get("description","")),default="élmény")
   row=record("Óbuda-Békásmegyer – hivatalos eseménynaptár",title,date,place,url,
              clean(BeautifulSoup(str(event.get("description","")),"html.parser").get_text(" ",strip=True)),kind,topics,
              time=start[11:16] if re.match(r"^\d\d:\d\d$",start[11:16]) else "")
   if row:rows.append(row)
 return rows

def obuda():
 urls=[]
 for offset in (0,1):
  month=TODAY.month+offset
  year=TODAY.year+(month-1)//12
  month=(month-1)%12+1
  listing=f"https://obuda.hu/esemenyek/honap/{year}-{month:02d}/"
  try:
   soup=BeautifulSoup(fetch(listing),"html.parser")
   for a in soup.select('a[href*="/esemeny/"]'):
    url=urllib.parse.urljoin(listing,a["href"]).split("#")[0]
    if url.startswith("https://obuda.hu/esemeny/") and url not in urls:urls.append(url)
  except Exception as exc:print("Óbuda list error:",type(exc).__name__,str(exc)[:100])
 rows=[]
 # Limit traffic and fetch detail pages concurrently to keep scheduled jobs short.
 # Detail pages require structured start date and explicit venue.
 def inspect(url):
  try:return parse_obuda_detail(fetch(url),url)
  except Exception as exc:
   print("Óbuda detail error:",url,type(exc).__name__)
   return []
 with cf.ThreadPoolExecutor(max_workers=6) as pool:
  for result in pool.map(inspect,urls[:45]):rows.extend(result)
 print("Óbuda detail pages checked:",min(len(urls),45))
 return rows

def main():
 sources=[("MTA naptár",lambda:sum((parse_mta(fetch(url),url) for url in MTA_SOURCES),[])),
          ("Pszichológia",lambda:parse_psychology(fetch(PSY_SOURCE))),
          ("Óbuda",obuda)]
 collected=[];success=0
 for name,fn in sources:
  try:
   rows=fn()
   collected.extend(rows)
   success+=1
   print(name,"dated Budapest events:",len(rows))
  except Exception as exc:print(name,"unavailable:",type(exc).__name__,str(exc)[:170])
 if not success:raise RuntimeError("No direct calendar available; existing events retained")
 old=json.loads(FILE.read_text("utf-8"))
 merged={e["id"]:e for e in old if not str(e.get("id","")).startswith("radar-dated-")
         or (e.get("date") or "")>=TODAY.isoformat()}
 for item in collected:
  previous=merged.get(item["id"],{})
  for field in ("summary","fullDescription","image","imageSourceUrl","imageCredit","imageAlt"):
   if previous.get(field) and not item.get(field):item[field]=previous[field]
  merged[item["id"]]=item
 # Prevent same source/date/title duplicated from pages with different listings.
 items=list(merged.values())
 text=json.dumps(items,ensure_ascii=False,indent=2)+"\n"
 if text!=FILE.read_text("utf-8"):FILE.write_text(text,"utf-8")
 print("New dated candidate sources:",len(collected),"total:",len(items))

if __name__=="__main__":main()
