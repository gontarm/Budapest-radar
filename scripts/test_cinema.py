#!/usr/bin/env python3
"""Regression tests for split cinema date headers and multiple venues."""
import datetime as dt
import unittest
from refresh_cinema import extract

class CinemaParserTests(unittest.TestCase):
 def setUp(self):
  self.today=dt.date(2026,11,13)
  self.url="https://mozibp.hu/film/digger"
 def test_split_headers_and_time_formats(self):
  html="""<html><body><h1>Digger</h1>
   <div><span>Péntek</span><span>11.13.</span><span>3 vetítés</span></div>
   <section><h3>Allee</h3><a>19:30</a><h3>Aréna</h3><a>20:00 ENG·F</a><h3>Mammut</h3><a>19:45 F</a></section>
   <div><span>Szombat 11.14. 1 vetítés</span><h3>Kino</h3><a>18:15</a></div>
  </body></html>"""
  records=extract(self.url,"Digger",html,self.today)
  self.assertEqual(len(records),4)
  self.assertEqual(sorted(set(e["date"] for e in records)),["2026-11-13","2026-11-14"])
  self.assertTrue(any("Cinema City Allee" in e["where"] for e in records))
  self.assertTrue(any("Kino Cafe" in e["where"] for e in records))
 def test_duplicate_blocks_and_expired_days(self):
  html="""<html><body><h1>Film</h1>
   <p>Csütörtök 11.12. 1 vetítés</p><h3>Allee</h3><a>19:30</a>
   <p>Péntek 11.13. 1 vetítés</p><h3>Allee</h3><a>19:30</a>
   <p>Péntek 11.13. 1 vetítés</p><h3>Allee</h3><a>19:30</a>
   </body></html>"""
  records=extract(self.url,"Film",html,self.today)
  self.assertEqual(len(records),1)
  self.assertEqual(records[0]["date"],"2026-11-13")

if __name__=="__main__":unittest.main()
