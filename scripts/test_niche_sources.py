#!/usr/bin/env python3
"""Offline regression tests for four new niche organizer sources."""
import datetime as dt
import unittest
import refresh_niche_sources as mod
class Sources(unittest.TestCase):
 def setUp(self):self.orig=mod.TODAY;mod.TODAY=dt.date(2026,11,13)
 def tearDown(self):mod.TODAY=self.orig
 def test_fuga_architecture(self):
  html='''<html><main><h1>RÉKE-est: Gönyü, egykori postakocsi állomás</h1>
  <p>műemlékvédelem</p><p>2026. november 19. csütörtök 18.00</p>
  <p>Breuer Marcell terem</p><p>László Csaba régész, műemléki szakértő előadása, amely bemutatja a műemléki értékeket.</p></main></html>'''
  rows=mod.fuga_detail(html,"https://fuga.org.hu/fevent/reke-est-gonyu-egykori-postakocsi-allomas/")
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["kind"],"építészet")
  self.assertEqual(rows[0]["date"],"2026-11-19")
  self.assertEqual(rows[0]["dateLabel"],"2026.11.19. · 18:00")
 def test_fuga_exhibition_end(self):
  html='''<main><h1>Harminc és Milučký – két nagyhatású szlovákiai építész</h1>
  <p>szlovákiai építészet</p><p>2026. november 6–29.</p><p>Janáky István terem</p></main>'''
  r=mod.fuga_detail(html,"https://fuga.org.hu/fevent/harminc")
  self.assertEqual(len(r),1)
  self.assertEqual(r[0]["date"],"2026-11-29")
  self.assertTrue(r[0]["dateLabel"].endswith("-ig"))
 def test_bme(self):
  html='''<main><h1>Ha Einstein tudta volna...</h1><p>BME F épület, F29-es terem</p><p>2026. 11. 20.</p><p>16:00 - 18:00</p>
  <p>Asbóth János (BME TTK Elméleti Fizika Tanszék) előadása kvantumfizikáról.</p></main>'''
  r=mod.bme_detail(html,"https://www.bme.hu/esemenyek/22466")
  self.assertEqual(len(r),1);self.assertIn("termeszettudomany",r[0]["interestTopics"])
 def test_liberta(self):
  html='''<main><h3>Philocafé in English with Liberta</h3><h4>LIFE</h4>
  <p>Kezdés: 2026-11-21 14:00</p><p>Befejezés: 2026-11-21 16:00</p>
  <p>Helyszín: Tűzoltó utca 2, Budapest, 1094</p>
  <a href="/philocafe-life">Bővebben</a></main>'''
  r=mod.liberta_listing(html)
  self.assertEqual(len(r),1);self.assertEqual(r[0]["interestTopics"],["filozofia"])
 def test_garden_date(self):
  html='''<main><h1>Luca napi varázsnövénytan – tematikus szakvezetés</h1>
  <p>2026. december 13. vasárnap 13:00 A növényvilág titokzatos oldala.</p></main>'''
  r=mod.garden_detail(html,"https://www.fuveszkert.org/hirek/luca-napi/")
  self.assertEqual(len(r),1);self.assertEqual(r[0]["date"],"2026-12-13")
 def test_no_guessed_garden_date(self):
  html='''<main><h1>Új növények a kertben</h1>
  <p>2026. november 18. óta nyitva, de nincs meghirdetett szakvezetés.</p></main>'''
  self.assertEqual(mod.garden_detail(html,"https://www.fuveszkert.org/hirek/uj/"),[])
if __name__=="__main__":unittest.main()
