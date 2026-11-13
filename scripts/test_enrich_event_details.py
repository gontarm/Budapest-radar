#!/usr/bin/env python3
"""Regression tests: original image provenance, meaningful texts, no fabricated details."""
import unittest
from bs4 import BeautifulSoup
import enrich_event_details as mod

class EnrichmentTests(unittest.TestCase):
 def test_fuga_original_image_and_event_copy(self):
  html='''<html><head><meta property="og:title" content="Élet-művek | 40 év a pályán"/>
  <meta property="og:image" content="https://fuga.org.hu/wp-content/uploads/2026/11/kiallitas.jpg"/></head>
  <body><main><h1>Élet-művek | 40 év a pályán</h1>
  <p>Szigeti Szilvia textiltervező, Radnóti Tamás belsőépítész és Radnóti Róza zongoraművész kiállítása a FUGÁ-ban.</p>
  <p>Az esemény két alkotó négy évtizedes munkásságát, a textil, a téralkotás és a zene közötti kapcsolatokat mutatja be.</p>
  </main></body></html>'''
  soup=BeautifulSoup(html,"html.parser")
  short,long=mod.get_description(soup,"Élet-művek | 40 év a pályán")
  image=mod.usable_image(soup,"https://fuga.org.hu/fevent/elet-muvek/","Élet-művek")
  self.assertIn("Szigeti Szilvia",short)
  self.assertIn("Radnóti Tamás",long)
  self.assertEqual(image,"https://fuga.org.hu/wp-content/uploads/2026/11/kiallitas.jpg")
  item={"id":"source-1","url":"https://fuga.org.hu/fevent/elet-muvek/","title":"Élet-művek","desc":"A szervező hivatalos programoldalán közzétett esemény."}
  self.assertTrue(mod.apply(item,short,long,image))
  self.assertEqual(item["imageSourceUrl"],item["url"])
  self.assertIn("Szigeti",item["desc"])
 def test_no_logo_fallback_as_real_photo(self):
  soup=BeautifulSoup('<meta property="og:image" content="/assets/logo.svg"><main><img src="/images/icon.png"></main>',"html.parser")
  self.assertEqual(mod.usable_image(soup,"https://example.org/event/one","One"),"")
 def test_generic_listing_not_specific(self):
  self.assertFalse(mod.same_page("https://example.org/musor/","A koncert"))
  self.assertFalse(mod.same_page("https://example.org/esemenyek/","A koncert"))
  self.assertTrue(mod.same_page("https://fuga.org.hu/fevent/elet-muvek/","Élet-művek"))
 def test_unrelated_menu_copy_rejected(self):
  self.assertFalse(mod.meaningful("Sütik elfogadása. Megosztás minden platformon, cookie beállítások."))
if __name__=="__main__":unittest.main()
