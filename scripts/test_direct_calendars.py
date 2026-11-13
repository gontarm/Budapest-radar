#!/usr/bin/env python3
"""Offline fixture checks for direct-source event extraction."""
import datetime as dt
import unittest
import refresh_direct_calendars as sources

class DirectCalendarTests(unittest.TestCase):
 def setUp(self):
  self.old=sources.TODAY
  sources.TODAY=dt.date(2026,11,13)
 def tearDown(self):sources.TODAY=self.old
 def test_mta_calendar(self):
  html='''<main><h2><a href="/esemenynaptar/1234">A drónrajok fizikája</a></h2>
  <div>Előadóülés</div><div>Budapest, Széchenyi István tér 9.</div>
  <div>2026. november 27., 11 óra</div></main>'''
  rows=sources.parse_mta(html,"https://mta.hu/esemenynaptar/")
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["date"],"2026-11-27")
  self.assertEqual(rows[0]["url"],"https://mta.hu/esemenynaptar/1234")
 def test_psychology_requires_budapest(self):
  html='''<main>
  <p>2026.11.17.</p><p>Dr. Almási Kitti - A Te döntésed</p>
  <p>1124 Budapest, 12. kerület - Hegyvidék</p>
  <p>2026.11.18.</p><p>Dr. Almási Kitti - A Te döntésed</p>
  <p>1111 Bécs</p></main>'''
  rows=sources.parse_psychology(html)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["kind"],"pszichológia")
 def test_obuda_event_requires_explicit_location(self):
  event='''<script type="application/ld+json">{"@type":"Event","name":"Óbudai történelmi séta","startDate":"2026-11-19T18:00:00+01:00","location":{"@type":"Place","name":"Óbudai Múzeum","address":{"streetAddress":"Fő tér 1.","addressLocality":"Budapest"}}}</script>'''
  rows=sources.parse_obuda_detail(event,"https://obuda.hu/esemeny/teszt/")
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["interestTopics"],["tortenelem"])
if __name__=="__main__":unittest.main()
