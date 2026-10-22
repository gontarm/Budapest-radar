#!/usr/bin/env python3
"""Ingyenes koncertHÍR-figyelő: a hír nem igazolt jegykészlet."""
import datetime as dt, email.utils, hashlib, json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent.parent/"concerts.json"
today=dt.datetime.now(ZoneInfo("Europe/Budapest")).date()
queries=[
'Budapest koncert jegyek új bejelentés when:7d',
'Budapest 2026 koncert jegyértékesítés indul when:7d',
'Budapest klubkoncert jazz alternatív elektronikus koncert when:7d',
'Szentendre Gödöllő koncert fesztivál jegyek when:7d']
terms=("koncert","fellép","fesztivál","turné","turne","jegyértékesítés","jegyek")
ignore=("elmarad","lemond","politika","botrány","sport","meccs")
def fetch(q):
 url="https://news.google.com/rss/search?q="+urllib.parse.quote(q)+"&hl=hu&gl=HU&ceid=HU:hu"
 req=urllib.request.Request(url,headers={"User-Agent":"BudapestRadar/1.0"})
 with urllib.request.urlopen(req,timeout=25) as response: root=ET.fromstring(response.read(1200000))
 for item in root.findall("./channel/item"):
  title=re.sub(r"\s+-\s+[^-]{2,75}$","",item.findtext("title","").strip())
  lower=title.casefold()
  if not any(t in lower for t in terms) or any(t in lower for t in ignore):continue
  try:
   d=email.utils.parsedate_to_datetime(item.findtext("pubDate",""))
   if abs((dt.datetime.now(dt.timezone.utc)-d.astimezone(dt.timezone.utc)).total_seconds())>8*86400:continue
  except (TypeError,ValueError):continue
  link=item.findtext("link","")
  if not link.startswith("https://"):continue
  yield {"id":"concert-"+hashlib.sha256(title.casefold().encode()).hexdigest()[:16],"title":title[:160],"kind":"koncert","where":"Budapest és környéke · ellenőrizendő","date":"","dateLabel":"Koncerthír · időpont a forrásban","desc":"Új koncert- vagy jegyhír. A pontos dátumot, helyszínt és jegyértékesítést a szervezőnél ellenőrizd. Ez nem igazolt jegykészlet.","url":link,"score":75,"discovered":today.isoformat(),"ticketStatus":"unknown","source":"Google News RSS · ellenőrizetlen hírtalálat"}
def main():
 previous=json.loads(OUT.read_text("utf-8")) if OUT.exists() else []
 results={x["id"]:x for x in previous if x.get("discovered","")>=(today-dt.timedelta(days=7)).isoformat()}
 successes=0
 for q in queries:
  try:
   for item in fetch(q): results[item["id"]]=item
   successes+=1
  except Exception as e:print("Forrás nem elérhető:",str(e)[:120])
 if not successes:raise RuntimeError("Nincs elérhető hírcsatorna; a korábbi lista változatlan")
 rows=sorted(results.values(),key=lambda x:x["discovered"],reverse=True)[:50]
 text=json.dumps(rows,ensure_ascii=False,indent=2)+"\n"
 if not OUT.exists() or OUT.read_text("utf-8")!=text:OUT.write_text(text,encoding="utf-8")
 print("Koncert-hírtalálatok:",len(rows))
if __name__=="__main__":main()
