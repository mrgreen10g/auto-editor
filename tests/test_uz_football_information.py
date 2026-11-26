import tempfile,unittest
from pathlib import Path
from hockey_editor.uz_football_facts import digits,classify,visual,enrich
from hockey_editor.uz_structure import parse
from hockey_editor.uzbek import classify as bet_classify
from hockey_editor.framing import forecast_text
from hockey_editor.model import Block
from hockey_editor.timeline import Line,Card
from hockey_editor.uz_forecasts import features,match_forecasts,missing_forecast
from test_uz_speech import segment

class UzbekFootballInformationTests(unittest.TestCase):
 def test_editorial_subheadings_not_matches_or_forecasts(self):
  text="""Assalomu alaykum!
BIRINCHI O'YIN — UELS VA PORTUGALIYA
Birinchi uchrashuv — Uels va Portugaliya!
UELS — O'Z MAYDONIDA XAVFLI RAQIB
PORTUGALIYA QANDAY G'ALABA QOZONADI?
Portugaliya to'rtta g'alaba qozongan.
Mening birinchi prognozim — Portugaliya g'alabasi!
IKKINCHI O'YIN — CHILI VA KOLUMBIYA
Chili — Kolumbiya!
LUIS DIAS — CHILI UCHUN ASOSIY XAVFLARDAN BIRI
IKKITA O'RTOQLIK UCHRASHUVI — TAKTIK AFZALLIK
Mening tanlovim — Kolumbiya mag'lub bo'lmaydi!
YAKUNIY XULOSA
Xayr!"""
  _,blocks,_=parse(text,'football');self.assertEqual(len(blocks),2)
  self.assertIn('Portugaliya',forecast_text(blocks[0]))
  self.assertEqual(forecast_text(blocks[1]),"Kolumbiya mag'lub bo'lmaydi")
  for title in ["MUHIM G'ALABA!","CHILI QANDAY G'ALABA QOZONADI?","BIRINCHI G'ALABA"]:self.assertNotEqual(bet_classify(title)[0],'ПРОГНОЗ')
 def test_spoken_numbers_scores_and_qualifiers(self):
  self.assertEqual(digits("O'n ikkita ochko, yigirma ikkita zarba. Ikkiyu bir!"),'12 ta ochko, 22 ta zarba. 2:1!')
  self.assertIn('64%',visual("Portugaliya to'pni 64% nazorat qilgan.",'TO‘P NAZORATI')['metrics'][0]['value'])
  text="To'rtta urilgan gol. Beshta o'tkazib yuborilgan gol."
  self.assertEqual([(m['value'],m['label']) for m in visual(text,'HUJUM VA HIMOYA')['metrics']],[('4','Gollar'),('5','O‘tkazilgan gollar')])
 def test_wide_categories_and_conditions(self):
  for text in ["Sanches jarohat olgan.","Murabbiy tarkibni almashtirdi.","Jamoa jadvalda 3 o'rinda.","Uels 5 zarba bergan.","Portugaliya ketma-ket 4 g'alaba qozongan."]:
   self.assertTrue(classify(text),text)
  t='Agar Chili birinchi gol ursa, 3 ta gol bo‘lishi mumkin.'
  self.assertEqual(classify(t),'EHTIMOL VA XAVF');self.assertFalse(visual(t,classify(t))['metrics'])
  self.assertFalse(classify('Mening prognozim — Portugaliya g‘alabasi!'))
  self.assertFalse(visual('Toshkent vaqti bilan soat 01:00.','TAQVIM VA YUKLAMA')['metrics'])
 def test_forecast_semantics_and_no_intro_fallback(self):
  b=Block(title='Chili — Kolumbiya',language='uz',sport='football')
  ref={b.uid:"Kolumbiya mag'lub bo'lmaydi"}
  self.assertTrue(features(ref[b.uid])['double'])
  data=[segment(0,4,'Birinchi uchrashuv Chili va Kolumbiya.'),segment(50,55,"Mening prognozim — Kolumbiya mag'lub bo'lmaydi.")]
  got=match_forecasts(data,0,60,[b],ref,recap=False)[0];self.assertGreaterEqual(got['start'],50)
  self.assertGreater(missing_forecast([segment(0,12,'Chili va Kolumbiya bugun maydonga chiqadi va bu yerda juda qiziqarli kurash bor.')],0,12,b)['start'],0)
  wrong=[segment(50,55,"Mening prognozim — Chili g'alabasi.")]
  self.assertIsNone(match_forecasts(wrong,0,60,[b],{b.uid:"Kolumbiya g'alabasi"},False,True)[0])
 def test_information_preserves_forecast_and_override(self):
  b=Block(language='uz',sport='football');lines=[Line('Jamoa 9 ochko olgan.',0,3),Line("Mening tanlovim — total 2,5 dan ko'p!",3,6)]
  forecast=Card(3,6,'ПРОГНОЗ','total',1)
  cards=enrich(b,lines,[forecast]);self.assertEqual(len(cards),2);self.assertIs(cards[-1],forecast)
  self.assertTrue(cards[0].visual)
 def test_actual_graphics_both_formats(self):
  from hockey_editor.graphics import card_image
  text="Portugaliya to'pni 64% nazorat qilgan."
  card=Card(0,4,'TO‘P NAZORATI',text,0,visual=visual(text,'TO‘P NAZORATI'))
  with tempfile.TemporaryDirectory() as d:
   for profile in ['uz_football','uz_football_shorts']:
    path=Path(d)/(profile+'.png');card_image(card,path,profile=profile);self.assertTrue(path.stat().st_size>1000)

 def test_recap_and_sentence_boundaries(self):
  from hockey_editor.uz_speech import recap_cue,make_lines
  self.assertTrue(recap_cue("Demek, buvi ikki uchrashuv bo'yicha tanloymiz."))
  self.assertTrue(recap_cue("Demi, bugungi ikki uchrashuv bo'yicha prognozlarimiz quyidagicha."))
  self.assertFalse(recap_cue("Demak, ikki uchrashuvda jamoa g'alaba qozongan."))
  self.assertFalse(recap_cue("Jamoa mavsumni yakunlab, bugun maydonga chiqadi."))
  data=[segment(0,12,"Jamoa 12 ochko olgan. Uels 5 zarba bergan. Mening tanlovim Portugaliya g'alabasi.")]
  lines,cards=make_lines(data,0,12,[],sentence_split=True)
  self.assertEqual(len(lines),3)
  self.assertEqual(lines[0]['text'],'Jamoa 12 ochko olgan.')
 def test_contextual_numbers_do_not_invent_totals(self):
  lines=[Line("O'tkazib yuborilgan gollar soni.",0,2),Line('Atletiko — beshta.',2,4),Line("Viking esa to'qqizta.",4,6)]
  cards=enrich(Block(language='uz',sport='football'),lines,[])
  self.assertEqual(cards[1].visual['metrics'],[{'value':'5','label':'O‘tkazilgan gollar'}])
  self.assertEqual(cards[2].visual['metrics'][0]['value'],'9')
  self.assertFalse(visual("Jamoa uchta golni bekor qildi.",'VAR VA HAKAM QARORI')['metrics'])
  self.assertFalse(visual("Jamoa uchta g'alaba qozona olmadi.",'JAMOA FORMASI')['metrics'])
