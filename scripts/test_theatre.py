#!/usr/bin/env python3
"""Offline regression checks for official theatre page parsing."""
import unittest
import refresh_theatre as mod

class TheatreParserTests(unittest.TestCase):
 def test_katona(self):
  html="""<main><div>Katona József Színház</div><h3>Mester és Margarita</h3><p>október 24 / szombat 19:00</p><a>Jegyek</a></main>"""
  rows=mod.katona(html)
  if mod.dt.datetime.now(mod.ZoneInfo("Europe/Budapest")).date().year==2026 and mod.dt.datetime.now(mod.ZoneInfo("Europe/Budapest")).date().month==10:
   self.assertTrue(any(x["title"]=="Mester és Margarita" for x in rows))
 def test_burg(self):
  html="""<main><p>Sa. Samstag</p><span>24.10.</span><p>19:00 Uhr</p><div>Burgtheater</div><h2>Das Ferienhaus</h2></main>"""
  rows=mod.burg(html)
  if mod.dt.datetime.now(mod.ZoneInfo("Europe/Vienna")).date().year==2026 and mod.dt.datetime.now(mod.ZoneInfo("Europe/Vienna")).date().month==10:
   self.assertTrue(any(x["title"]=="Das Ferienhaus" for x in rows))
 def test_no_interview(self):
  self.assertEqual(mod.katona("<h2>Interview</h2>"),[])
  self.assertEqual(mod.burg("<h2>Podcast</h2>"),[])

if __name__=="__main__":unittest.main()
