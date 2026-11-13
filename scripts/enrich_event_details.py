#!/usr/bin/env python3
"""Enrich Radar event records from the event's own organiser page.

No invented prose, time, image or venue. Prefer event-specific image metadata.
Avoid treating venue homepages and generic listings as an individual event.
Original image URLs remain at their publishers; no third-party photos are
downloaded or republished as files. Provenance is saved with each image.
"""
import concurrent.futures
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent.parent
TODAY=dt.datetime.now(ZoneInfo("Europe/Budapest")).date().isoformat()
UA={"User-Agent":"Mozilla/5.0 (compatible; BudapestRadar/1.0; public programme metadata)"}
LIMIT=110
BLOCKED_URL_PARTS=("/musor/","/events/all-events","/esemenyek/","/programok/","/koncertek/")
DROP_TEXT=("cookie","sütik","adatvéd","feliratkoz","hírlevél","adatkezel","weboldalunk","jegyvásárlás","megosztás","share this","további információk","kapcsolat","kövess minket")
GENERIC=("a rendezvény","a program pontos","a részleteket","a hivatalos","nyilvános programnaptár","pontos helyszín","jegyárat és","további információ","hivatalos eseménynaptár","forrásoldalon","közzétett esemény","további részleteket")
def tidy(s):return re.sub(r"\s+"," ",str(s or "")).strip()
def meaningful(s):
 x=tidy(s)
 if len(x)<55 or len(x)>3600:return False
 t=x.casefold()
 if any(k in t[:90] for k in DROP_TEXT):return False
 if sum(c.isalpha() for c in x)<len(x)*.48:return False
 if x.count("https://") or x.count("http://"):return False
 return True
def fetch(url):
 req=urllib.request.Request(url,headers=UA)
 with urllib.request.urlopen(req,timeout=16) as rsp:
  if "html" not in rsp.headers.get("Content-Type","").lower():return None
  return rsp.read(1200000).decode("utf-8","replace")
def meta(soup,name):
 node=(soup.find("meta",attrs={"property":name}) or soup.find("meta",attrs={"name":name}))
 return tidy(node.get("content","")) if node else ""
def same_page(page_title,record_title):
 # A broad calendar must never provide the same unrelated description/image to all
 # events. For narrow event URLs, metadata is event-specific even if the heading
 # title has a date or artist suffix.
 path=urllib.parse.urlsplit(page_title).path.lower()
 return not any(path.rstrip("/").endswith(x.rstrip("/")) for x in BLOCKED_URL_PARTS)
def usable_image(soup,base,title):
 # Do not present social sharing icons, site logos, 1px trackers as an event photo.
 candidates=[meta(soup,"og:image"),meta(soup,"twitter:image")]
 scope=soup.find("article") or soup.find("main")
 if scope:
  for node in scope.select("img[src],img[data-src]")[:6]:
   candidates.append(node.get("data-src") or node.get("src"))
 for c in candidates:
  if not c:continue
  u=urllib.parse.urljoin(base,c)
  parsed=urllib.parse.urlsplit(u)
  if parsed.scheme!="https" or not parsed.hostname:continue
  low=(parsed.path+" "+parsed.query).lower()
  if any(x in low for x in ("logo","favicon","icon","avatar","placeholder","pixel","sprite","default-image","no-image")):continue
  if re.search(r"\.(?:svg|gif)(?:$|\?)",low):continue
  if u.rstrip("/")==base.rstrip("/"):continue
  return u
 return ""
def get_description(soup,title):
 # Distinct opening summary plus the substantial body paragraphs, attributed to
 # the organiser. No complete republishing of the original programme article.
 main=soup.find("article") or soup.find("main") or soup
 for x in main(["script","style","nav","footer","aside","form","button","header"]):x.decompose()
 lines=[]
 for p in main.select("p, .entry-content > div, .field--name-body > div, .wp-block-paragraph"):
  txt=tidy(p.get_text(" ",strip=True))
  if meaningful(txt) and txt not in lines:lines.append(txt)
 # Avoid empty source preview and social meta used as full event details.
 og=meta(soup,"og:description") or meta(soup,"description")
 if meaningful(og) and not lines:lines=[og]
 summary=next((x[:260].rsplit(" ",1)[0]+"…" if len(x)>260 else x for x in lines if meaningful(x)),"")
 substantial=[x for x in lines if len(x)>=170 and x!=summary]
 # Source pages often put short opening and administrative notices before
 # their actual programme description. Prefer substantial editorial paragraphs.
 content=" ".join((substantial[:3] if substantial else lines[:4]))
 if len(content)>690:content=content[:687].rsplit(" ",1)[0]+"…"
 if content==summary:content=""
 return summary,content
def details(record):
 url=record.get("url","")
 if not url.startswith("https://") or not same_page(url,record.get("title","")):return None
 try:html=fetch(url)
 except Exception:return None
 if not html:return None
 soup=BeautifulSoup(html,"html.parser")
 title=meta(soup,"og:title") or (soup.title.get_text(" ",strip=True) if soup.title else "")
 # An official page with a totally unrelated title is likely a stale URL.
 if title:
  a=set(re.findall(r"\w{4,}",record.get("title","").lower()))
  b=set(re.findall(r"\w{4,}",title.lower()))
  if len(a)>=2 and not a.intersection(b):return None
 summary,content=get_description(soup,record.get("title",""))
 picture=usable_image(soup,url,record.get("title",""))
 if not (summary or content or picture):return None
 return summary,content,picture
def candidates(rows,kind):
 valid=[e for e in rows if isinstance(e,dict) and e.get("date","")>=TODAY
  and e.get("kind")!="mozi" and e.get("url","").startswith("https://")
  and same_page(e.get("url",""),e.get("title",""))
  and (e.get("detailVersion",0)<2 or not e.get("image") or not e.get("fullDescription") or
       any(k in e.get("desc","").casefold() for k in GENERIC))]
 # Prioritise FUGA/BME/Liberta, then short and imageless details.
 return sorted(valid,key=lambda e:(
  e.get("detailCheckedOn",""),  # process unchecked pages first, then oldest checked
  not any(e.get("id","").startswith(p) for p in ("source-","radar-dated-","official-","classical-")),
  bool(e.get("image") and e.get("fullDescription")),
  len(e.get("fullDescription",""))),reverse=False)[:LIMIT]
def apply(e,summary,content,image):
 changed=False
 if summary and (not e.get("summary") or len(e.get("summary",""))<70):
  e["summary"]=summary;changed=True
 if content and (not e.get("fullDescription") or len(e.get("fullDescription",""))<100 or
                 (len(e.get("fullDescription",""))<540 and len(content)>len(e.get("fullDescription",""))+130)):
  e["fullDescription"]=content;changed=True
 if image and not e.get("image"):
  e["image"]=image;e["imageSourceUrl"]=e["url"]
  e["imageCredit"]=e.get("source","Eseményszervező")+" · eredeti eseményfotó"
  e["imageAlt"]="A program szervezőjének eseményképe: "+e.get("title","")
  changed=True
 if summary and (not e.get("desc") or any(x in e["desc"].casefold() for x in GENERIC)):
  e["desc"]=summary;changed=True
 return changed
def main():
 total=Counter()
 for path in (ROOT/"events.json",ROOT/"concerts.json"):
  rows=json.loads(path.read_text("utf-8"))
  subset=candidates(rows,path.name)
  seen={}
  for e in subset:seen.setdefault(e["url"],[]).append(e)
  print(path.name,"records:",len(rows),"event pages to enrich:",len(seen),flush=True)
  def job(item):url,items=item;return url,details(items[0])
  with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
   for url,result in pool.map(job,seen.items()):
    for e in seen[url]:
     e["detailCheckedOn"]=TODAY
     e["detailVersion"]=2
     if not result:continue
     summary,content,image=result
     if apply(e,summary,content,image):total["updated"]+=1
     if image:total["image_found"]+=1
     if content:total["description_found"]+=1
  out=json.dumps(rows,ensure_ascii=False,indent=2)+"\n"
  if out!=path.read_text("utf-8"):path.write_text(out,"utf-8")
 print("Enrichment results:",dict(total),flush=True)
if __name__=="__main__":main()
