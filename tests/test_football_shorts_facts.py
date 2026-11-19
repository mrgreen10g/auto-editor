import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from hockey_editor.football_facts import enrich,visual,classify
from hockey_editor.timeline import Line,Card
from hockey_editor.model import Block,Project
from hockey_editor.graphics import card_image
from hockey_editor.keyboard import shortcut

class PortraitFactsTests(unittest.TestCase):
 def test_dense_fact_fits_phone(self):
  text='Каталонцы выиграли одиннадцать из двенадцати матчей чемпионата и забили сорок восемь голов!'
  cards=enrich(Block(),[Line(text,0,5)],[])
  self.assertIn('11 из 12',cards[0].text)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'card.png';x,y=card_image(cards[0],path,profile='ru_football_shorts')
   with Image.open(path) as im:
    self.assertGreaterEqual(y,700);self.assertLessEqual(y+im.height,1100);self.assertLessEqual(x+im.width,660)
 def test_specific_metrics(self):
  d=visual('Девятнадцать пропущенных голов за десять туров!','СТАТИСТИКА МАТЧА')
  self.assertIn({'value':'19','label':'пропущенных голов'},d['metrics'])
  d=visual('Девять побед и ни одного поражения!','ФОРМА КОМАНДЫ')
  self.assertIn({'value':'0','label':'поражений'},d['metrics'])
  self.assertEqual(classify('Восемнадцатого ноября работу с Юнайтед начал Маурисио Почеттино!'),'СОСТАВ КОМАНДЫ')
 def test_short_priorities_remain_disjoint(self):
  from unittest.mock import patch
  from hockey_editor.shorts import finish_cards
  lines=[Line('Пять побед подряд.',0,4),Line('Дополнительные ставки в телеграм-канале.',4,8)]
  b=Block(sport='football');p=Project(profile='ru_football_shorts',blocks=[b],assets={'telegram':'tg.mp4'})
  cards=enrich(b,lines,[Card(0,1,'РАЗБОР МАТЧА','А — Б'),Card(4,8,'ТЕЛЕГРАМ','Telegram',1,'tg.mp4')])
  cards,_=finish_cards(p,b,lines,cards,[],8)
  self.assertTrue(any(c.visual for c in cards));self.assertTrue(any(c.asset=='tg.mp4' for c in cards))
  for a,b in zip(cards,cards[1:]):self.assertLessEqual(a.end,b.start)

class KeyboardTests(unittest.TestCase):
 def widget(self,state='normal',kind='TEntry'):
  self.events=[]
  return SimpleNamespace(winfo_class=lambda:kind,cget=lambda _:state,event_generate=self.events.append)
 def test_russian_clipboard_key(self):
  w=self.widget();e=SimpleNamespace(widget=w,keycode=86,keysym='Cyrillic_em',state=4)
  self.assertEqual(shortcut(e,True),'break');self.assertEqual(self.events,['<<Paste>>'])
 def test_no_double_paste_or_altgr(self):
  w=self.widget();e=SimpleNamespace(widget=w,keycode=86,keysym='v',state=4)
  self.assertIsNone(shortcut(e,True));self.assertEqual(self.events,[])
  e.keysym='Cyrillic_em';e.state=12;self.assertIsNone(shortcut(e,True));self.assertEqual(self.events,[])
 def test_disabled_and_non_text_untouched(self):
  for state,kind in [('disabled','Text'),('readonly','TCombobox'),('normal','Button')]:
   e=SimpleNamespace(widget=self.widget(state,kind),keycode=86,keysym='Cyrillic_em',state=4)
   shortcut(e,True);self.assertEqual(self.events,[])
