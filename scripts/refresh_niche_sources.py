#!/usr/bin/env python3
"""Dated cultural programmes from FUGA, BME, Liberta Praxis and ELTE Füvészkert.\n\nAll imports require an explicitly published programme date and known Budapest venue.

Never infer dates from article publication timestamps, evergreen descriptions,
or external news. Only venue-specific official calendar/event pages qualify.
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
TODAY=dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
UA={"User-Agent":"Mozilla/5.0 (compatible; BudapestRadar/1.0; public event calendars)"}
MONTHS={"január":1,"február":2,"március":3,"április":4,"május":5,"június":6,
        "július":7,"augusztus":8,"szeptember":9,"október":10,"november":11,"december":12}
MONTH_PATTERN="|".join(MONTHS)
HU_DATE=re.compile(r"(20\d{2})\.\s*("+MONTH_PATTERN+r")\s*(\d{1,2})(?:\.|(?=\s*[–-]))",re.I)
NUM_DATE=re.compile(r"(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.",re.I)
ISO_DATE=re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
TIME=re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)")
FUGA="https://fuga.org.hu/esemenyek/"
BME="https://www.bme.hu/esemenyek"
LIBERTA="https://libertapraxis.com/aktualitasok/"
GARDEN="https://www.fuveszkert.org/hirek/"
FUGA_WHERE="FUGA Budapesti Építészeti Központ · Petőfi Sándor utca 5., Budapest"
BME_WHERE="Budapesti Műszaki és Gazdaságtudományi Egyetem · Műegyetem rakpart 3., Budapest"
GARDEN_WHERE="ELTE Füvészkert · Illés utca 25., Budapest"

def fetch(url):
 req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=18) as rsp:return rsp.read(1800000).decode("utf-8","replace")
def clean(t):return re.sub(r"\s+"," ",str(t or "")).strip()
def date_of(text):
 m=HU_DATE.search(text) or NUM_DATE.search(text) or ISO_DATE.search(text)
 if not m:return None
 try:
  return dt.date(int(m.group(1)),MONTHS[m.group(2).casefold()] if m.re==HU_DATE else int(m.group(2)),int(m.group(3)))
 except (ValueError,KeyError):return None
def upcoming(d):return d is not None and TODAY<=d<=TODAY+dt.timedelta(days=200)
def row(source,title,date,where,url,kind,topics,time="",desc="",end=False):
 if not upcoming(date) or not (8<=len(title)<=170):return None
 if not url.startswith("https://") or "budapest" not in where.casefold():return None
 day=f"{date:%Y.%m.%d.}"
 label=(day+"-ig" if end else day+(" · "+time if time else " · kezdés a forrásoldalon"))
 key="source-calendar|"+source+"|"+url+"|"+str(date)+"|"+title.casefold()
 return dict(id="source-"+hashlib.sha256(key.encode()).hexdigest()[:22],
  title=title,kind=kind,interestTopics=topics,where=where,date=date.isoformat(),
  dateLabel=label,desc=desc[:420] or "A szervező hivatalos programoldalán közzétett esemény.",
  url=url,source=source,score=84,dataQuality="scheduled",eventVerified=False,discovered=TODAY.isoformat())

def links(html,base,part):
 soup=BeautifulSoup(html,"html.parser"); found=[]
 host=urllib.parse.urlsplit(base).hostname
 for a in soup.select("a[href]"):
  url=urllib.parse.urljoin(base,a["href"]).split("#")[0]
  path=urllib.parse.urlsplit(url).path
  if urllib.parse.urlsplit(url).hostname!=host or part not in path:continue
  if url.rstrip("/")!=base.rstrip("/") and url not in found:found.append(url)
 return found

def head_and_lines(html):
 soup=BeautifulSoup(html,"html.parser")
 h=soup.find("h1")
 if not h:return "",[]
 title=clean(h.get_text(" ",strip=True))
 for tag in soup(["script","style","nav","footer"]):tag.decompose()
 # h1 is the entry point; avoid publication dates from sidebars/site footers.
 lines=[clean(x) for x in soup.get_text("\n").splitlines() if clean(x)]
 try:at=lines.index(title)
 except ValueError:return title,[]
 return title,lines[at+1:at+24]

def fuga_detail(html,url):
 title,lines=head_and_lines(html)
 if not title or not lines:return []
 date_line=next((x for x in lines[:9] if HU_DATE.search(x)),None)
 if date_line is None:return []
 date=date_of(date_line)
 # Exhibition duration: "2026. november 6–29." is an end date, not 29 new dates.
 end=False
 if date and date<TODAY:
  rm=re.search(r"\d{1,2}\s*[–-]\s*(\d{1,2})\.",date_line)
  if rm:
   try:date=dt.date(date.year,date.month,int(rm.group(1)));end=True
   except ValueError:pass
 if not upcoming(date):return []
 category=clean(lines[0]).casefold()
 t=title.casefold()
 if "koncert" in category or "komolyzene" in category or any(k in t for k in ("zongoraest","szerzői est","prämodern","asztromuzsika")):
  kind="koncert";topics=[]
 elif any(k in t+" "+category for k in ("design","médiaművészet","formatervez","grafikai")):
  kind="design";topics=[]
 elif any(k in t+" "+category for k in ("épít","műemlék","építészet","műterem","urbaniszt","város")):
  kind="építészet";topics=["tortenelem"] if "műemlék" in t+" "+category else []
 elif "kiállítás" in category or "kiállítás" in t:
  kind="művészet";topics=[]
 else:
  # Do not label an unrelated book launch as architecture merely because it is at FUGA.
  kind="élmény";topics=[]
 time_match=TIME.search(date_line)
 time=f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else ""
 if not end and not time_match and "–" not in date_line and "-" not in date_line:return []
 info=next((x for x in lines[1:12] if len(x)>35 and not HU_DATE.search(x)), "")
 e=row("FUGA – hivatalos programnaptár",title,date,FUGA_WHERE,url,kind,topics,time,info,end)
 return [e] if e else []

def bme_detail(html,url):
 title,lines=head_and_lines(html)
 if not title or not lines:return []
 # BME detail: # title, room, "2026. 11. 20.", time, description
 where_part=lines[0]
 if not where_part or len(where_part)>100:return []
 date_line=next((x for x in lines[1:6] if NUM_DATE.search(x)),None)
 if not date_line:return []
 date=date_of(date_line)
 if not upcoming(date):return []
 lower=title.casefold()
 if any(k in lower for k in ("diplomaátadó","zártkörű","bizottság","nyilvános doktori védése")):return []
 if not any(k in lower+" "+" ".join(lines[1:11]).casefold() for k in
  ("előadás","workshop","fizika","tech","kutatás","innováció","nyílt nap","tudomány","mérnök","mikroelektron","kvantum","meetup","szeminárium","szellemi tulajdon","mesterséges intelligencia","informatika","klíma","etika","bemutató","konferencia")):return []
 if any(k in lower for k in ("művész","design","építész")):kind,topics="design",[]
 else:kind,topics="tudomány",["technika"] if any(x in lower for x in ("mérnök","tech","innováció","elektron","műszaki")) else ["termeszettudomany"]
 time_match=TIME.search(date_line)
 if not time_match:time_match=next((m for x in lines[2:6] if (m:=TIME.search(x))),None)
 time=f"{int(time_match.group(1)):02d}:{time_match.group(2)}" if time_match else ""
 where=(where_part+" · "+BME_WHERE) if "budapest" not in where_part.casefold() else where_part
 desc=next((x for x in lines[2:12] if len(x)>35 and not NUM_DATE.search(x)), "")
 result=row("BME – hivatalos eseménynaptár",title,date,where,url,kind,topics,time,desc)
 return [result] if result else []

def liberta_listing(html):
 soup=BeautifulSoup(html,"html.parser")
 rows=[]
 for head in soup.select("h3"):
  title=clean(head.get_text(" ",strip=True))
  if len(title)<9:continue
  # Heading + optional subtitle, followed by a published start date/location.
  section=[]
  for node in head.next_elements:
   if getattr(node,"name",None)=="h3":break
   if getattr(node,"name",None)=="footer":break
   if isinstance(node,str) and clean(node):section.append(clean(node))
   if len(section)>32:break
  text="\n".join(section)
  m=re.search(r"Kezdés:\s*(20\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})",text)
  where_match=re.search(r"Helyszín:\s*([^\n]+)",text)
  if not (m and where_match):continue
  date=date_of(m.group(1));where=clean(where_match.group(1))
  if "budapest" not in where.casefold():continue
  anchor=next((a for a in head.find_all_next("a",limit=8) if "Bővebben" in a.get_text(" ",strip=True)),None)
  url=urllib.parse.urljoin(LIBERTA,anchor["href"]) if anchor and anchor.get("href") else LIBERTA
  subtitle=next((x for x in section if len(x)>5 and not x.startswith(("Kezdés:","Befejezés:","Helyszín:","Bővebben"))), "")
  item=row("Liberta Praxis – filozófiai eseménynaptár",title+" – "+subtitle if subtitle and subtitle!=title else title,
           date,where,url,"élmény",["filozofia"],m.group(2),"Filozófiai beszélgetés vagy nyilvános esemény.")
  if item:rows.append(item)
 return rows

def garden_detail(html,url):
 title,lines=head_and_lines(html)
 t=title.casefold()
 if not any(k in t for k in ("szakvezetés","workshop","tematikus nap","kert","növény","orchidea","szamóca")):return []
 # Exclude the publication timestamp in article archives: require dated content after the h1.
 match=next((x for x in lines[:16] if HU_DATE.search(x) or NUM_DATE.search(x)),None)
 if not match:return []
 date=date_of(match)
 if not upcoming(date):return []
 tt=TIME.search(match)
 time=f"{int(tt.group(1)):02d}:{tt.group(2)}" if tt else ""
 if not time:return []
 obj=row("ELTE Füvészkert – hivatalos programoldal",title,date,GARDEN_WHERE,url,
  "élmény",["kertek","termeszettudomany"],time,"Tematikus növénytani program a Füvészkertben.")
 return [obj] if obj else []

def details_from_listing(url,part,parser,limit=35):
 listing=fetch(url)
 target=links(listing,url,part)[:limit]
 if not target:
  print("No detail URLs:",url)
  return []
 def inspect(link):
  try:return parser(fetch(link),link)
  except Exception as exc:print("Detail unavailable:",link,type(exc).__name__);return []
 rows=[]
 with cf.ThreadPoolExecutor(max_workers=6) as pool:
  for found in pool.map(inspect,target):rows.extend(found)
 print(url,"detail links:",len(target),"dated records:",len(rows))
 return rows

def merge(filename,new):
 path=ROOT/filename
 existing=json.loads(path.read_text("utf-8"))
 # Keep incoming-source records if a feed goes temporarily offline, but remove expired records.
 current=[x for x in existing if not (str(x.get("id","")).startswith("source-")
                                     and x.get("date","")<TODAY.isoformat())]
 ids={x["id"] for x in current}
 for x in new:
  if x["id"] not in ids:current.append(x);ids.add(x["id"])
 payload=json.dumps(current,ensure_ascii=False,indent=2)+"\n"
 if path.read_text("utf-8")!=payload:path.write_text(payload,"utf-8")
 print(filename,"new imported:",len([x for x in new if x["id"] not in {i["id"] for i in existing}]),"total:",len(current))

def main():
 found=[];successful=0
 tasks=[
  ("FUGA",lambda:details_from_listing(FUGA,"/fevent/",fuga_detail,32)),
  ("BME",lambda:details_from_listing(BME,"/esemenyek/",bme_detail,42)),
  ("Liberta",lambda:liberta_listing(fetch(LIBERTA))),
  ("Füvészkert",lambda:details_from_listing(GARDEN,"/hirek/",garden_detail,26)),
 ]
 for name,fn in tasks:
  try:
   events=fn();found.extend(events);successful+=1
   print(name,"dated programmes:",len(events))
  except Exception as exc:print(name,"unavailable:",type(exc).__name__,str(exc)[:180])
 if not successful:raise RuntimeError("All additional organizer calendars unavailable")
 indexed={e["id"]:e for e in found}
 merged=list(indexed.values())
 merge("events.json",[e for e in merged if e["kind"]!="koncert"])
 merge("concerts.json",[e for e in merged if e["kind"]=="koncert"])
if __name__=="__main__":main()
