#!/usr/bin/env python3
"""Budapest Radar: ingyenes, kulcsszavas programhír-figyelő (RSS).
A hírek NEM ellenőrzött eseményidőpontok: a részletek a forráslinken olvashatók.
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
FILE = ROOT / "events.json"
QUERIES = [
    ("építészet", 'Budapest (építészeti kiállítás OR épületbejárás OR városi séta OR Bauhaus)'),
    ("tudomány", 'Budapest (idegtudomány OR neurobiológia OR csillagászat OR tudományos előadás)'),
    ("design", 'Budapest (design kiállítás OR kortárs múzeum OR fotókiállítás)'),
    ("élmény", '(Budapest OR Gödöllő OR Szentendre) (fénypark OR fényshow OR fényinstalláció OR fénykiállítás OR immerzív kiállítás OR interaktív élmény OR különleges esti séta)'),
]
POSITIVE = {
    "építészet": 9, "építészeti": 9, "épületbejár": 10, "városi séta": 9,
    "bauhaus": 10, "moderniz": 8, "várostörtén": 8, "múzeum": 3,
    "kiállítás": 6, "tárlatvezet": 8, "előadás": 6, "ingyenes": 3,
    "idegtud": 11, "neuro": 10, "agy": 3, "biológ": 8,
    "csillagász": 9, "űrkutat": 10, "tudomány": 5,
    "design": 7, "fotó": 4, "geometri": 6, "kutató": 4,
    "fénypark": 12, "fényshow": 12, "fényinstalláció": 12, "fénykiállítás": 12,
    "immerzív": 10, "interaktív": 7, "esti séta": 9, "látvány": 5
}
NEGATIVE = ("ingatlan", "lakáshirdetés", "eladó", "politikai", "választás", "baleset",
            "hotel", "szálloda", "beruházás", "felújítás", "újulhat", "ingatlanfejlesztés")
# A friss cikk csak akkor kerülhet a listába, ha valódi, látogatható
# programra utal. A program időpontját az RSS-cím alapján nem találjuk ki.
EVENT_TERMS = ("kiállítás", "tárlat", "tárlatvezet", "épületbejár", "városi séta",
               "tematikus séta", "előadás", "workshop", "műhely", "nyílt nap",
               "fesztivál", "koncert", "közönségtalálkozó", "programok",
               "rendezvény", "bemutató", "látogatható", "fénypark", "fényshow",
               "fényinstalláció", "fénykiállítás", "immerzív", "esti séta")
def relevant(title):
    lower = title.casefold()
    if any(x in lower for x in NEGATIVE):
        return False
    if not any(x in lower for x in EVENT_TERMS):
        return False
    return sum(v for k, v in POSITIVE.items() if k in lower) >= 6

TZ = ZoneInfo("Europe/Budapest")
now = dt.datetime.now(dt.timezone.utc)
today = now.astimezone(TZ).date()
headers = {"User-Agent": "BudapestRadar/1.0 (personal RSS reader)"}

def news(kind, query):
    search = urllib.parse.quote(query + " when:7d")
    url = f"https://news.google.com/rss/search?q={search}&hl=hu&gl=HU&ceid=HU:hu"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        root = ET.fromstring(response.read(1_500_000))
    items = []
    for item in root.findall("./channel/item"):
        title = re.sub(r"\s+-\s+[^-]{2,75}$", "", item.findtext("title", "").strip())
        link = item.findtext("link", "").strip()
        try:
            published = email.utils.parsedate_to_datetime(item.findtext("pubDate", ""))
            if published.tzinfo is None: published = published.replace(tzinfo=dt.timezone.utc)
        except (TypeError, ValueError):
            continue
        age = (now - published.astimezone(dt.timezone.utc)).total_seconds()
        if age < -3600 or age > 7 * 86400 or not link.startswith("https://"):
            continue
        lower = title.casefold()
        if not relevant(title): continue
        matches = sum(v for k, v in POSITIVE.items() if k in lower)
        # A dátum a HÍR közzététele, nem a program időpontja.
        pid = "rss-" + hashlib.sha256(title.casefold().encode()).hexdigest()[:15]
        items.append({
            "id": pid, "title": title[:150], "kind": kind,
            "where": "Budapest / környéke · helyszín ellenőrzendő",
            "date": "", "dateLabel": f"Friss hír: {published.astimezone(TZ):%Y.%m.%d.} · időpont a forrásban",
            "desc": "Új, témába vágó hírtalálat. A program helyét, pontos dátumát, jegyárát és elérhetőségét a forrásoldalon ellenőrizd.",
            "url": link, "score": min(94, 65 + matches),
            "discovered": today.isoformat(), "source": "Google News RSS · nem ellenőrzött programjelölt"
        })
    return items

def main():
    entries = json.loads(FILE.read_text(encoding="utf-8"))
    manual = [x for x in entries if not str(x.get("id", "")).startswith("rss-")]
    new = []
    failures = []
    for kind, query in QUERIES:
        try:
            new.extend(news(kind, query))
        except Exception as exc:
            failures.append(f"{kind}: {type(exc).__name__}: {exc}")
    if len(failures) == len(QUERIES):
        raise RuntimeError("Egyetlen feed sem elérhető; a régi adatlista megmarad. " + "; ".join(failures))
    # Részleges kiesésnél a meglévő friss hírek megmaradnak még max. 7 napig.
    cached = [x for x in entries if str(x.get("id", "")).startswith("rss-")
              and x.get("discovered", "") >= (today - dt.timedelta(days=7)).isoformat()
              and relevant(x.get("title", ""))]
    unique = {}
    for x in cached + new:
        unique[x["id"]] = x
    latest = sorted(unique.values(), key=lambda x: (x.get("discovered", ""), x["score"]), reverse=True)[:18]
    result = manual + latest
    if result != entries:
        FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Alap programok: {len(manual)}; friss RSS-találatok: {len(latest)}; feed hibák: {len(failures)}")
    for err in failures: print("FIGYELMEZTETÉS:", err)

if __name__ == "__main__":
    main()
