#!/usr/bin/env python3
"""Audit Budapest Radar event links without claiming that tickets or dates were verified.

Runs in the scheduled GitHub Action. An HTTP response only checks link reachability;
it does not prove that the event still takes place or that tickets remain.
"""
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.datetime.now(ZoneInfo("Europe/Budapest")).date().isoformat()
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BudapestRadarLinkAudit/1.0)"}
VAGUE = ("ellenőrizendő", "változó helyszín", "több helyszín", "magyarországi mozik")
AGGREGATORS = ("news.google.com",)
EVENT_PATH_WORDS = ("program", "event", "esemeny", "esemény", "ticket", "jegy",
                    "concert", "koncert", "show", "eloadas", "előadás", "exhibition",
                    "kiallitas", "kiállítás", "detail", "events")


def classification(row):
    if not row.get("date") or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(row.get("date"))):
        return "news"
    where = str(row.get("where") or "").casefold()
    if not where or any(bad in where for bad in VAGUE):
        return "incomplete"
    return "scheduled"


def event_specific(url):
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname in AGGREGATORS:
            return False
        path = parsed.path.casefold()
        return any(word in path for word in EVENT_PATH_WORDS) and len(path.strip("/")) > 10
    except (ValueError, TypeError):
        return False


def check_link(url):
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return "invalid"
        if parsed.hostname in AGGREGATORS:
            return "news_link"
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=12) as resp:
            # Limit transferred content: response is closed without downloading the page.
            status = resp.status
            return "reachable" if 200 <= status < 400 else "uncertain"
    except urllib.error.HTTPError as exc:
        # 403/429 often result from bot blocking; do not mistake for a deleted event.
        return "blocked" if exc.code in (401, 403, 429) else "not_found" if exc.code in (404, 410) else "uncertain"
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return "uncertain"


def audit_file(name):
    path = ROOT / name
    rows = json.loads(path.read_text("utf-8"))
    url_results = {}
    totals = {}
    for row in rows:
        kind = classification(row)
        url = str(row.get("ticketUrl") or row.get("url") or "")
        direct = event_specific(url)
        # News links are not event links; keep them explicitly separated.
        if kind == "news":
            status = "news_link" if "news.google.com" in url else "not_checked"
        else:
            if url not in url_results:
                url_results[url] = check_link(url)
            status = url_results[url]
        row["dataQuality"] = kind
        row["linkStatus"] = status
        row["directEventLink"] = direct
        row["linkCheckedOn"] = TODAY if status not in ("news_link", "not_checked") else None
        # HTTP success ≠ confirmed date/availability.
        row["eventVerified"] = False
        totals[(kind, status)] = totals.get((kind, status), 0) + 1
    output = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    if path.read_text("utf-8") != output:
        path.write_text(output, "utf-8")
    print(name + ": " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(totals.items())))


if __name__ == "__main__":
    audit_file("events.json")
    audit_file("concerts.json")
    audit_file("vienna-events.json")
    audit_file("vienna-concerts.json")
