#!/usr/bin/env python3
"""Vienna Radar: official Stadthalle listings + separately marked news leads.

Only Stadthalle's published date and location are represented as scheduled.
News headlines never acquire guessed dates or ticket links.
"""
import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
TODAY=dt.datetime.now(ZoneInfo("Europe/Vienna")).date()
UA={"User-Agent":"BudapestRadar/1.0 (personal public events calendar)"}

class Table(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth=0;self.row=None;self.cell=None;self.rows=[];self.link=""
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="tr":self.row=[]
        if tag in ("td","th") and self.row is not None:self.cell=[]
        if tag=="a" and self.cell is not None and a.get("href"):
            self.link=urllib.parse.urljoin("https://www.stadthalle.com",a["href"])
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None:
            if self.row:self.rows.append((self.row,self.link))
            self.row=None;self.link=""

NON_MUSIC=("ballet","musical","kabarett","comedy","tennis","holiday on ice","red bull bassline","erste bank open","riverdance","spiritualität","wrestling","junglebook","oktagon","swan lake","nutcracker","phantom of the opera","shen yun","lets dance","romeo & julia","mamma mia","dr. michael tsokos","chris tall","gernot & stipsits","torsten sträter","ralf schmitz","paul panzer","kaya yanar","herzog & polster","irish celtic","sukhishvili")
MUSIC_ARTISTS=("peter cornelius","andré rieu","nico santos","placebo","bob dylan","jungle","beatrice egli","tokio hotel","the dark tenor","pitbull","korn","gregorian","rin","sergio cortés","santiano","the prodigy","bonez mc","raf camora","blok3","aretha franklin","smokie","konstantinos argiros","rea garvey","jodokcello","bap","parov stelar","seiler","nimo","wanda","falco meets amadeus","die fantastischen vier","bullet for my valentine","five finger death punch","unheilig","nickelback","edmund","max raabe","roy bianco","montez","sido","louis philippson","il volo","nena")
MUSIC_HINTS=("concert","konzert","music of","musik","orchestra","orchester","symphon","tribute","gospel","filmmusik")
def is_music(title):
 t=title.casefold()
 return not any(x in t for x in NON_MUSIC) and (any(x in t for x in MUSIC_ARTISTS) or any(x in t for x in MUSIC_HINTS))
def genre(title):
    t=title.casefold()
    if any(x in t for x in ("orchestra","symphon","filmmusik","classical","sound of","orchester","cello")):return "klasszikus"
    if any(x in t for x in ("korn","koRn".casefold(),"placebo","metal","bullet for","five finger","bap")):return "rock"
    if any(x in t for x in ("prodigy","parov stelar","jungle","electronic")):return "elektronikus"
    if any(x in t for x in ("rin","bonez","raf camora","bl ok3","nimo","hip-hop")):return "hiphop"
    return "pop"

def stadthalle():
    url="https://www.stadthalle.com/en/events/all-events/print"
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:page=r.read(2_000_000).decode("utf-8","replace")
    p=Table();p.feed(page)
    rows=[]
    for cells,link in p.rows:
        if len(cells)<3:continue
        title=cells[0].strip()
        if not title or title.lower() in ("event title","titel","veranstaltung"):continue
        combined=" ".join(cells)
        m=re.search(r"(?<!\d)(\d{2})\.(\d{2})\.(20\d{2})(?!\d)",combined)
        if not m:continue
        iso=f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        if iso<TODAY.isoformat():continue
        hall=next((c for c in cells if re.search(r"Hall [DEF]|Halle [DEF]|Studio F",c,re.I)),"")
        if not is_music(title):continue
        if not hall or not re.search(r"Hall [DEF]|Halle [DEF]|Studio F",hall,re.I):continue
        pid="vienna-stadthalle-"+hashlib.sha256((title.casefold()+iso).encode()).hexdigest()[:15]
        rows.append(dict(id=pid,title=title,kind="koncert",genre=genre(title),
            where="Wiener Stadthalle · "+hall+" · Roland-Rainer-Platz 1, 1150 Wien",
            date=iso,dateLabel=f"{m.group(1)}.{m.group(2)}.{m.group(3)} · pontos kezdés a forrásban",
            desc="A Wiener Stadthalle hivatalos naptárában meghirdetett esemény. A jegyárat és az elérhetőséget a szervezőnél ellenőrizd.",
            url=link if link.startswith("https://www.stadthalle.com/") else url,
            source="Wiener Stadthalle – hivatalos rendezvénynaptár",score=82,discovered=TODAY.isoformat()))
    return rows

QUERIES=[
 ("építészet","Wien Architekturführung Bauhaus Ausstellung Architekturzentrum"),
 ("tudomány","Wien Wissenschaft Vortrag Neurowissenschaft Astronomie Universität"),
 ("pszichológia","Wien Psychologie Vortrag Gespräch Neurowissenschaft"),
 ("design","Wien Design Ausstellung MAK Vienna"),
 ("mozi","Wien Filmfestival Filmgespräch Premiere Filmvorführung"),
 ("élmény","Wien Stadtführung Museumsführung Sonderausstellung"),
 ("koncert","Wien Konzert Stadthalle Arena WUK Gasometer Musikverein"),
]
def news(kind,query):
    q=urllib.parse.quote(query+" when:7d")
    url="https://news.google.com/rss/search?q="+q+"&hl=de&gl=AT&ceid=AT:de"
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=25) as r:root=ET.fromstring(r.read(1_300_000))
    rows=[]
    for item in root.findall("./channel/item"):
        title=re.sub(r"\s+-\s+[^-]{2,70}$","",item.findtext("title","").strip())
        link=item.findtext("link","")
        if not link.startswith("https:") or len(title)<12:continue
        try:
            when=email.utils.parsedate_to_datetime(item.findtext("pubDate",""))
            if abs((dt.datetime.now(dt.timezone.utc)-when.astimezone(dt.timezone.utc)).days)>8:continue
        except (TypeError,ValueError,AttributeError):continue
        if not any(x in title.casefold() for x in ("konzert","tour","ausstellung","führung","vortrag","festival","film","premiere","workshop","museum","architektur","design","wissenschaft","psycholog","musik")):continue
        rid="vienna-news-"+hashlib.sha256((kind+title.casefold()).encode()).hexdigest()[:16]
        rows.append(dict(id=rid,title=title[:160],kind=kind,where="Wien · helyszín ellenőrizendő",
            date="",dateLabel="Friss hírtalálat · időpont a forrásban",
            desc="Bécsi programhír, nem ellenőrzött esemény. A dátum, a helyszín és a jegyadatok a forrásnál ellenőrizendők.",
            url=link,score=60,discovered=TODAY.isoformat(),source="Google News RSS · ellenőrizetlen hírtalálat"))
    return rows

def save(path,rows):
    previous=json.loads(path.read_text("utf-8")) if path.exists() else []
    old={r["id"]:r for r in previous if (r.get("date","") and r.get("date","")>=TODAY.isoformat()) or (not r.get("date") and r.get("discovered","")>=(TODAY-dt.timedelta(days=7)).isoformat())}
    for r in rows:old[r["id"]]=r
    # Prefer manually verified event pages over new calendar imports for
    # the same performer on the same date.
    unique={}
    for r in sorted(old.values(),key=lambda r:(r.get("score",0),bool(r.get("ticketUrl"))),reverse=True):
        name=re.sub(r"[^a-z0-9]+","",r.get("title","").casefold())
        date=r.get("date") or r.get("id")
        duplicate=next((key for key in unique if key[0]==date and (key[1] in name or name in key[1]) and len(name)>5),None)
        if duplicate:continue
        unique[(date,name)]=r
    result=sorted(unique.values(),key=lambda r:(not bool(r.get("date")),r.get("date") or r.get("discovered",""),-r.get("score",0)))[:250]
    data=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if not path.exists() or data!=path.read_text("utf-8"):path.write_text(data,"utf-8")
    print(path.name,len(result))

def main():
    events=[];concerts=[];ok=0
    try:
        concerts=stadthalle();ok+=1
        print("Stadthalle official concert candidates:",len(concerts))
    except Exception as exc:print("Stadthalle fetch error:",repr(exc))
    for kind,query in QUERIES:
        try:
            rows=news(kind,query)
            (concerts if kind=="koncert" else events).extend(rows)
            ok+=1
        except Exception as exc:print("Vienna RSS unavailable:",kind,repr(exc))
    if not ok:raise RuntimeError("No Vienna source available; retained previous dataset")
    save(ROOT/"vienna-events.json",events)
    save(ROOT/"vienna-concerts.json",concerts)

if __name__=="__main__":main()
