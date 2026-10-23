#!/usr/bin/env python3
"""Collect real Budapest cinema showtimes from public MoziBP film pages.

Only dated showtimes explicitly printed alongside one of the 23 supported cinema
names are imported. If the source changes/fails, existing entries are kept.
"""
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://mozibp.hu"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BudapestRadar/1.0; public cinema programme)"}
CINEMAS = {
 "Allee":"Cinema City Allee", "Aréna":"Cinema City Aréna", "Art+ Cinema":"Art+ Cinema",
 "Bem":"Bem Mozi", "Campona":"Cinema City Campona", "Cinema MOM":"Cinema MOM",
 "Cirko-Gejzír":"Cirko-Gejzír", "Corvin":"Corvin mozi",
 "Duna Pláza":"Cinema City Duna Plaza", "Etele Cinema":"Etele Cinema",
 "GoBuda":"GoBuda Mozi", "Kino Cafe":"Kino Cafe",
 "Kultik Csepel":"Kultik Csepel", "Lurdy":"Lurdy Mozi",
 "Mammut":"Cinema City Mammut", "Művész":"Művész mozi",
 "Pólus":"Pólus Mozi", "Puskin":"Puskin mozi", "Sugár":"Sugár Mozi",
 "Tabán":"Tabán mozi", "Toldi":"Toldi mozi",
 "Uránia":"Uránia Nemzeti Filmszínház", "Westend":"Cinema City Westend",
}
DATE = re.compile(r"^(?:Hétfő|Kedd|Szerda|Csütörtök|Péntek|Szombat|Vasárnap)\s+(\d{1,2})\.(\d{1,2})\.\s+\d+\s+vetítés", re.I)
TIME = re.compile(r"^(\d{1,2}):(\d{2})(?:\s*(?:VIP|IMAX|4DX|3D|ScreenX|2D|HU|EN|F|OV|SUB|\(.*\)))*$",re.I)

def fetch(url):
 req=urllib.request.Request(url,headers=HEADERS)
 with urllib.request.urlopen(req,timeout=25) as r:
  return r.read(2_500_000).decode("utf-8","replace")

def film_links(html):
 soup=BeautifulSoup(html,"html.parser")
 links={}
 for a in soup.select('a[href*="/film/"]'):
  href=urllib.parse.urljoin(BASE,a.get("href",""))
  title=a.get_text(" ",strip=True)
  title=re.sub(r"\s+\(\d{4}\)$","",title).strip()
  if href.startswith(BASE+"/film/") and title and len(title)<160:
   links[href]=title
 return links

def date_from(month,day,today):
 for year in (today.year,today.year+1):
  try: date=dt.date(year,month,day)
  except ValueError: continue
  if today<=date<=today+dt.timedelta(days=14):return date
 return None


def film_metadata(soup):
 h=soup.find("h1")
 title=h.get_text(" ",strip=True) if h else ""
 candidates=[]
 if h:
  for element in h.find_all_next(["p","div"],limit=30):
   value=element.get_text(" ",strip=True)
   if 75<=len(value)<=1400 and not re.search(r"(?:vetítés|moziműsor|Sütik:)",value,re.I):
    candidates.append(value)
 description=min(candidates,key=len) if candidates else ""
 meta=soup.find("meta",attrs={"name":"description"})
 if not description and meta:description=meta.get("content","")
 duration=""
 for item in soup.stripped_strings:
  match=re.search(r"\b(\d{2,3})\s*perc\b",item)
  if match:duration=match.group(1)+" perc";break
 genre=""
 if h:
  for element in h.find_all_next(["p","span","div"],limit=20):
   value=element.get_text(" ",strip=True)
   if 2<len(value)<60 and any(x in value.lower() for x in ("dráma","vígjáték","horror","thriller","animáció","dokumentumfilm","romantikus","akció","kalandfilm","sci-fi")):
    genre=value;break
 image=""
 meta_img=soup.find("meta",attrs={"property":"og:image"})
 if meta_img:image=urllib.parse.urljoin(BASE,meta_img.get("content",""))
 return {"description":description[:1100],"duration":duration,"genre":genre[:80],"image":image}

def cinema_official_links():
 """Discover verified links from cinema directory pages instead of guessing URLs."""
 try:soup=BeautifulSoup(fetch(BASE+"/musoron"),"html.parser")
 except Exception:return {}
 directory={}
 for a in soup.select('a[href]'):
  label=a.get_text(" ",strip=True)
  if label in CINEMAS:
   href=urllib.parse.urljoin(BASE,a.get("href",""))
   if href.startswith(BASE+"/"):directory[label]=href
 def inspect(entry):
  label,url=entry
  try:
   page=BeautifulSoup(fetch(url),"html.parser")
   for a in page.select('a[href]'):
    caption=a.get_text(" ",strip=True).lower()
    href=urllib.parse.urljoin(BASE,a.get("href",""))
    if ("hivatalos" in caption or "mozi oldala" in caption or "weboldal" in caption) and href.startswith("https://") and urllib.parse.urlsplit(href).hostname not in ("mozibp.hu","www.mozibp.hu"):
     return label,href
  except Exception:pass
  return label,None
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  return {CINEMAS[label]:link for label,link in pool.map(inspect,directory.items()) if link}

def extract(url,title,html,today,official=None):
 soup=BeautifulSoup(html,"html.parser")
 metadata=film_metadata(soup)
 # Links and labels also occur in menus; only parse after the first real day header.
 for tag in soup(["script","style","nav","footer"]):tag.decompose()
 lines=[re.sub(r"\s+"," ",part).strip() for part in soup.get_text("\n").splitlines()]
 lines=[x for x in lines if x]
 date=None;cinema=None;found=[]
 for line in lines:
  m=DATE.match(line)
  if m:
   date=date_from(int(m.group(2)),int(m.group(1)),today)
   cinema=None
   continue
  if not date:continue
  if line in CINEMAS:
   cinema=CINEMAS[line]
   continue
  if line.startswith(("Műsor","Kapcsolódó vetítések","Filmek","Info","Budapesti mozik")):
   cinema=None
  if not cinema:continue
  m=TIME.fullmatch(line)
  if not m:continue
  hh,mm=map(int,m.groups())
  if hh>23 or mm>59:continue
  showtime=f"{hh:02d}:{mm:02d}"
  key=f"cinema|{url}|{date}|{showtime}|{cinema}"
  found.append({
   "id":"cinema-"+hashlib.sha256(key.encode()).hexdigest()[:22],
   "title":title,"filmId":urllib.parse.urlsplit(url).path,
   "kind":"mozi","where":cinema+" · Budapest",
   "date":date.isoformat(),"dateLabel":f"{date:%Y.%m.%d.} · {showtime}",
   "desc":metadata["description"] or "A film ismertetője a forrásoldalon olvasható.",
   "genre":metadata["genre"],"duration":metadata["duration"],"image":metadata["image"],
   "cinemaOfficialUrl":(official or {}).get(cinema,""),
   "url":url,"source":"MoziBP – nyilvános budapesti moziműsor",
   "score":85,"dataQuality":"scheduled","eventVerified":False,
   "discovered":today.isoformat()})
 return found

def collect():
 today=dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
 urls=film_links(fetch(BASE+"/musoron"))
 if not urls:raise RuntimeError("No films found on weekly programme")
 entries=[]
 official=cinema_official_links()
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  futures={pool.submit(fetch,url):(url,title) for url,title in urls.items()}
  for future in concurrent.futures.as_completed(futures):
   url,title=futures[future]
   try:entries.extend(extract(url,title,future.result(),today,official))
   except Exception as exc:print("Film failed:",title,str(exc)[:90])
 if not entries:raise RuntimeError("No dated showtimes extracted; refusing to overwrite")
 path=ROOT/"events.json"
 old=json.loads(path.read_text(encoding="utf-8"))
 # Replace only entries owned by this importer when new collection succeeded.
 keep=[x for x in old if not str(x.get("id","")).startswith("cinema-")]
 seen={x["id"] for x in keep}
 for x in entries:
  if x["id"] not in seen:keep.append(x);seen.add(x["id"])
 path.write_text(json.dumps(keep,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"Films: {len(urls)}; extracted shows: {len(entries)}; unique new records: {len(keep)-len(old)}")
if __name__=="__main__":collect()
