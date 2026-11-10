import unittest,tempfile
from pathlib import Path
from hockey_editor.cs import TEAMS,PLAYERS,DICTIONARY,identity,pair_heading,classify,events,forecast
from hockey_editor.model import Block,MatchSource,Project
from hockey_editor.cs_scan import candidates

class CSTests(unittest.TestCase):
 def test_catalog_and_aliases(self):
  self.assertEqual([r['rank'] for r in TEAMS],list(range(1,101)))
  self.assertGreaterEqual(len(PLAYERS),490)
  self.assertTrue(all(len(DICTIONARY[n])>=2 for n in DICTIONARY))
  for text in ('Джи-ту','Джи Ту','G2'):self.assertEqual(identity(text),'G2')
  self.assertEqual(pair_heading('«Мауз» — «Джи-ту».'),'MOUZ — G2')
  from hockey_editor.cs import mentioned
  self.assertEqual(mentioned('Spirit Academy vs NAVI Junior'),['Spirit Academy','NAVI Junior'])
 def test_scoped_speech_aliases(self):
  from hockey_editor.ru_speech import tokens
  self.assertEqual(tokens('G2',cs=True),tokens('Джи-ту',cs=True))
  self.assertEqual(tokens('GamerLegion',cs=True),tokens('Геймер Легион',cs=True))
  from hockey_editor.speech_boundaries import token_similarity
  self.assertEqual(token_similarity(tokens('G2',cs=True)[0],tokens('MOUZ',cs=True)[0]),0)
 def test_import(self):
  from hockey_editor.folder_import import parse_episode
  a,b,c=parse_episode('Привет!\nРазбор1 Джи Ту — Астралис\nДжи-ту выиграли карту 16:14. Мой выбор — победа G2.\nИтак, повторю прогноз. До встречи!','ru_cs')
  self.assertEqual(b[0].sport,'cs');self.assertEqual(b[0].title,'G2 — Astralis');self.assertTrue(c.script.startswith('Итак'))
 def test_stats_and_negated_pick(self):
  self.assertEqual(classify('На Mirage винрейт восемьдесят процентов.')[0],'ВИНРЕЙТ КАРТЫ')
  self.assertEqual(classify('Процент выигранных пистолеток — 60%.')[0],'ПИСТОЛЕТНЫЕ РАУНДЫ')
  self.assertEqual(classify('У donk рейтинг 1.22 и 66 киллов.')[0],'СТАТИСТИКА ИГРОКА')
  self.assertNotEqual(classify('Я не беру минус полторы карты.')[0],'ПРОГНОЗ')
  self.assertNotEqual(classify('Мой выбор стал интереснее после этой игры.')[0],'ПРОГНОЗ')
 def test_archive_requests_have_no_score_dependency(self):
  m=MatchSource('archive.mp4','G2','MOUZ',sport='cs')
  b=Block(title='G2 — Astralis',sport='cs',script='Раньше Джи Ту выиграли эту карту со счетом 16:14.\nМой выбор — победа Джи Ту.',match_ids=[m.id])
  rows=events(b,[m]);self.assertEqual(len(rows),1);self.assertEqual(rows[0].kind,'play');self.assertIsNone(rows[0].score)
 def test_hud_requires_running_clock(self):
  self.assertEqual(len(candidates([[0,82,.95],[2,80,.95],[4,78,.95]],2400)),1)
  for values in ([82,82,82],[82,None,78],[82,80,120]):self.assertEqual(candidates([[i*2,v,.95] for i,v in enumerate(values)],2400),[])
 def test_graphics_keep_placement(self):
  from hockey_editor.graphics import card_image
  from hockey_editor.timeline import Card
  from PIL import Image
  with tempfile.TemporaryDirectory() as d:
   for title,text in [('РАЗБОР МАТЧА','G2 — Astralis'),('ПРОГНОЗ','Победа G2'),('СТАТИСТИКА ИГРОКА','donk · рейтинг 1.22'),('СМЕНА МАТЧА','Spirit — FUT')]:
    card=Card(0,4,title,text);a=Path(d)/'a.png';b=Path(d)/'b.png'
    self.assertEqual(card_image(card,a,profile='ru_hockey'),card_image(card,b,profile='ru_cs'))
    with Image.open(a) as ia,Image.open(b) as ib:self.assertEqual(ia.size,ib.size)
