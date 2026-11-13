#!/usr/bin/env python3
"""Offline regression tests for classical-concert official source parsing."""
import datetime as dt
import unittest
import refresh_classical as mod

class TestClassical(unittest.TestCase):
 def setUp(self):
  self.prev=mod.TODAY
  mod.TODAY=dt.date(2026,11,13)
 def tearDown(self):mod.TODAY=self.prev
 def test_philharmonic_real_calendar_shape(self):
  html='''<html><body>
  <p>2026. november 16., hétfő</p>
  <p>Saját</p><p>Zeneakadémia,</p><p>Budapest</p>
  <p>19:30-tól várhatóan 21:40-ig</p><p>Évad: 2026 | 2027</p>
  <a href="https://www.filharmonikusok.hu/koncert/mozart-haydn/">MOZART, HAYDN, CARTELLIERI – VASHEGYI GYÖRGY</a>
  <p>Jegyvásárlás</p></body></html>'''
  rows=mod.national_philharmonic(html)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["genre"],"klasszikus")
  self.assertEqual(rows[0]["date"],"2026-11-16")
  self.assertIn("19:30",rows[0]["dateLabel"])
  self.assertTrue(rows[0]["url"].startswith("https://www.filharmonikusok.hu/koncert/"))
 def test_expired_is_ignored(self):
  html='''<p>2026. november 11., szerda</p><p>Zeneakadémia,</p><p>Budapest</p>
  <p>19:30-tól</p><a href="/koncert/mozart/">Mozart a Zeneakadémián</a>'''
  self.assertEqual(mod.national_philharmonic(html),[])
 def test_schema_rejects_unknown_city(self):
  html='''<script type="application/ld+json">
  {"@type":"MusicEvent","name":"Mozart kamarazene","startDate":"2026-11-21T19:00:00+01:00",
  "location":{"@type":"Place","name":"Kunsthalle",
  "address":{"streetAddress":"Ring 1","addressLocality":"Wien"}}}
  </script>'''
  self.assertEqual(mod.parse_schema(html,"https://mupa.hu/en/program/mozart","Müpa"),[])
 def test_schema_budapest(self):
  html='''<script type="application/ld+json">
  {"@type":"MusicEvent","name":"Mozart kamarazene","startDate":"2026-11-21T19:00:00+01:00",
  "location":{"@type":"Place","name":"Bartók Béla Nemzeti Hangversenyterem",
  "address":{"streetAddress":"Komor Marcell u. 1.","addressLocality":"Budapest"}}}
  </script>'''
  self.assertEqual(len(mod.parse_schema(html,"https://mupa.hu/en/program/mozart","Müpa")),1)
if __name__=="__main__":unittest.main()
