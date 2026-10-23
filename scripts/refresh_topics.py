#!/usr/bin/env python3
"""Targeted discovery for eight Radar interests in Budapest and Vienna.

These are UNVERIFIED leads from Google News RSS, including searches restricted to
relevant institutions. Never invent an event date, time, address or ticket URL.
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
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TOPICS = {
 "titkok": (
  "Budapest (épületbejárás OR pincetúra OR óvóhely OR kulisszajárás) (vezetett OR látogatás)",
  "Wien (Unterwelt Führung OR Bunker Führung OR geheime Orte OR Architekturführung)"),
 "termeszettudomany": (
  "Budapest (Természettudományi Múzeum OR ELTE OR MTA) (előadás OR tárlatvezetés OR nyílt nap) (evolúció OR genetika OR geológia OR biológia)",
  "Wien (Naturhistorisches Museum OR Universität Wien) (Führung OR Vortrag OR Workshop) (Evolution OR Biologie OR Geologie)"),
 "tortenelem": (
  "Budapest (Budapesti Történeti Múzeum OR Aquincumi Múzeum OR Magyar Nemzeti Múzeum) (tárlatvezetés OR előadás OR régészet OR séta)",
  "Wien (Wien Museum OR Römermuseum OR Kunsthistorisches Museum) (Führung OR Vortrag OR Geschichte OR Archäologie)"),
 "filozofia": (
  "Budapest (filozófiai beszélgetés OR filozófiai előadás OR filozófia est) (ELTE OR CEU OR könyvtár OR kávéház)",
  "Wien (Philosophie Vortrag OR Philosophisches Café OR Philosophie Diskussion) (Universität OR Museum OR Wien)"),
 "vilagegyetem": (
  "Budapest (Svábhegyi Csillagvizsgáló OR Planetárium OR Polaris Csillagvizsgáló) (bemutató OR távcsöves OR előadás)",
  "Wien (Planetarium Wien OR Kuffner Sternwarte OR Urania Sternwarte) (Vorführung OR Führung OR Astronomie)"),
 "technika": (
  "Budapest (Közlekedési Múzeum OR Műszaki Múzeum OR erőmű OR gyárlátogatás) (vezetés OR látogatás OR bemutató)",
  "Wien (Technisches Museum Wien OR Kraftwerk Führung OR Industrieführung) (Führung OR Ausstellung OR Vortrag)"),
 "szinhaz": (
  "Budapest (Nemzeti Színház OR Örkény Színház OR Trafó) (bemutató OR előadás OR premier OR tánc)",
  "Wien (Burgtheater OR Volkstheater OR Tanzquartier) (Premiere OR Aufführung OR Tanz OR Theater)"),
 "kertek": (
  "Budapest (Füvészkert OR Soroksári Botanikus Kert OR arborétum) (vezetett séta OR növénybemutató OR botanikai program)",
  "Wien (Botanischer Garten Universität Wien OR Schönbrunn Tiergarten OR Blumengärten Hirschstetten) (Führung OR Workshop OR Pflanzen)")
}
KIND={"titkok":"élmény","termeszettudomany":"tudomány","tortenelem":"élmény",
      "filozofia":"élmény","vilagegyetem":"tudomány","technika":"élmény",
      "szinhaz":"élmény","kertek":"élmény"}
SIGNAL={
 "titkok":("bejár","látogat","túra","führung","besichtig","séta"),
 "termeszettudomany":("kiállítás","előadás","tárlat","führung","vortrag","workshop","ausstellung"),
 "tortenelem":("kiállítás","előadás","tárlat","vezetés","führung","vortrag","ausstellung","séta"),
 "filozofia":("filozóf","beszélget","előadás","philosoph","diskussion","vortrag"),
 "vilagegyetem":("csillag","bemutat","előadás","távcső","planetarium","sternwarte","vorführung"),
 "technika":("látogat","bejár","kiállítás","bemutat","führung","ausstellung","technik"),
 "szinhaz":("színház","előadás","bemutat","tánc","theater","aufführung","premiere","tanz"),
 "kertek":("séta","vezet","bemutat","garten","pflanzen","führung","workshop")}
UA={"User-Agent":"BudapestRadar/1.0 (public programme discovery)"}

# A hírcím nem bizonyítja, hogy a cikk látogatható eseményről szól.
# A hírtalálatokat csak belső jelöltként kezeljük, nem közöljük programként.
REJECT=("interjú","interview","interjú:","podcast","vélemény","kommentár",
        "rückblick","bericht","kritik","rezension","porträt","portrait",
        "könyvajánló","tudósítás","visszatekintés","beszámoló")
def plausible_lead(title):
    t=title.casefold()
    return not any(term in t for term in REJECT)

def fetch(city,topic,query):
    language="hu" if city=="budapest" else "de"
    country="HU" if city=="budapest" else "AT"
    url=("https://news.google.com/rss/search?q="+urllib.parse.quote(query+" when:14d")
         +f"&hl={language}&gl={country}&ceid={country}:{language}")
    request=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(request,timeout=22) as response:
        root=ET.fromstring(response.read(1200000))
    now=dt.datetime.now(dt.timezone.utc)
    rows=[]
    for item in root.findall("./channel/item"):
        title=re.sub(r"\s+-\s+[^-]{2,75}$","",item.findtext("title","").strip())
        link=item.findtext("link","").strip()
        if not link.startswith("https://") or len(title)<13:continue
        if not plausible_lead(title) or not any(word in title.casefold() for word in SIGNAL[topic]):continue
        try:
            published=email.utils.parsedate_to_datetime(item.findtext("pubDate",""))
            if published.tzinfo is None:published=published.replace(tzinfo=dt.timezone.utc)
            age=(now-published.astimezone(dt.timezone.utc)).total_seconds()
            if age< -3600 or age>14*86400:continue
        except (ValueError,TypeError,OverflowError):continue
        discovered=now.astimezone(ZoneInfo("Europe/Budapest" if city=="budapest" else "Europe/Vienna")).date().isoformat()
        rid=("radar-topic-"+city+"-"+hashlib.sha256((topic+title.casefold()).encode()).hexdigest()[:18])
        rows.append(dict(id=rid,title=title[:160],kind=KIND[topic],interestTopics=[topic],
            where=("Budapest · helyszín ellenőrizendő" if city=="budapest" else "Wien · helyszín ellenőrizendő"),
            date="",dateLabel="Témafigyelő hírtalálat · időpont a forrásban",
            desc="Témához kapcsolódó hírtalálat, nem ellenőrzött esemény. Nyisd meg a forrást és ellenőrizd a helyszínt, az időpontot és a részvételt.",
            url=link,score=63,discovered=discovered,
            source="Tematikus Google News RSS · nem ellenőrzött programjelölt",
            dataQuality="news"))
    return rows

def update(city):
    filename="events.json" if city=="budapest" else "vienna-events.json"
    file=ROOT/filename
    existing=json.loads(file.read_text("utf-8"))
    today=dt.datetime.now(ZoneInfo("Europe/Budapest" if city=="budapest" else "Europe/Vienna")).date()
    cutoff=(today-dt.timedelta(days=14)).isoformat()
    previous=[x for x in existing if not (x.get("id","").startswith("radar-topic-") and x.get("interestTopics")==["szinhaz"]) and (not x.get("id","").startswith("radar-topic-") or x.get("discovered","")>=cutoff)]
    collected=[]
    for topic,pair in TOPICS.items():
        if topic=="szinhaz":continue  # Theatre: only official organiser calendars.
        query=pair[0 if city=="budapest" else 1]
        try:
            entries=fetch(city,topic,query)
            collected.extend(entries)
            print(city,topic,len(entries))
        except Exception as exc:
            print("Source unavailable:",city,topic,str(exc)[:120])
    if not collected and not any(x.get("id","").startswith("radar-topic-") for x in previous):
        print("No new thematic leads; existing entries preserved")
        return
    by_id={x["id"]:x for x in previous}
    for x in collected:by_id[x["id"]]=x
    output=list(by_id.values())
    # Only trim our own leads; do not touch curated programmes or older RSS.
    topic_rows=sorted((x for x in output if x.get("id","").startswith("radar-topic-")),
                      key=lambda x:x.get("discovered",""),reverse=True)[:100]
    output=[x for x in output if not x.get("id","").startswith("radar-topic-")]+topic_rows
    new=json.dumps(output,ensure_ascii=False,indent=2)+"\n"
    if file.read_text("utf-8")!=new:file.write_text(new,"utf-8")
    print(filename,"total",len(output),"topic leads",len(topic_rows))

if __name__=="__main__":
    for city in ("budapest","vienna"):update(city)
