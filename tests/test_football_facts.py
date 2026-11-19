import tempfile,unittest,wave
from pathlib import Path
from hockey_editor.football_facts import digits,classify,visual,enrich
from hockey_editor.model import Block,Settings
from hockey_editor.timeline import Line,Card,Plan

class FootballFactsTests(unittest.TestCase):
 def test_numbers(self):
  self.assertEqual(digits('На семьдесят девятой минуте. С сорока тремя очками. Пятьдесят четыре процента.'),'На 79 минуте. С 43 очками. 54%.')
  self.assertEqual(digits('Меньше полутора, дважды, девять побед.'),'Меньше 1,5, 2 раза, 9 побед.')
 def test_context_and_negation(self):
  text='В трёх домашних матчах не одержал ни одной победы.'
  data=visual(text,classify(text));self.assertNotIn({'value':'1','label':'победы'},data['metrics']);self.assertIn({'value':'0','label':'побед'},data['metrics'])
  text='Косово ни разу не забивало больше одного гола за матч.'
  self.assertNotIn({'value':'0','label':'голов'},visual(text,classify(text))['metrics'])
 def test_uncertain_is_not_statistic(self):
  text='Если хозяева начнут рисковать, гости могут забить два гола.'
  self.assertEqual(classify(text),'ФАКТОР РИСКА');self.assertEqual(visual(text,classify(text))['metrics'],[])
  self.assertIn('Если',visual(text,classify(text))['source'])
 def test_categories(self):
  for text,label in [('Защитник получил травму колена и не сыграет.','СОСТАВ КОМАНДЫ'),('Автор гола получил красную карточку.','ДИСЦИПЛИНА'),('Итог — 0:0.','РЕЗУЛЬТАТ ВСТРЕЧИ'),('Между матчами всего три дня.','КАЛЕНДАРЬ')]:self.assertEqual(classify(text),label)
  self.assertFalse(classify('Пишите свои прогнозы в комментариях.'))
  self.assertFalse(classify('Сможет ли Ирландия победить?'))
 def test_all_facts_and_manual_edits_survive(self):
  text='За тринадцать матчей девять побед, четыре ничьи и ни разу не проиграли.'
  line=Line(text,2,10);block=Block();cards=enrich(block,[line],[])
  self.assertEqual(len(cards),1);self.assertEqual(cards[0].start,2);self.assertEqual(cards[0].end,10)
  self.assertEqual(cards,enrich(block,[line],cards));self.assertIn('13 матчей',cards[0].text);self.assertIn('9 побед',cards[0].text)
  block.card_overrides={'0':'Мой исправленный текст'};manual=Card(2,10,'ФАКТ','Мой исправленный текст',0)
  self.assertEqual(enrich(block,[line],[manual]),[manual])
 def test_saved_plan_and_artwork(self):
  from hockey_editor.graphics import card_image
  from PIL import Image
  text='Израиль владел мячом пятьдесят четыре процента времени.'
  cards=enrich(Block(),[Line(text,0,4)],[]);plan=Plan(0,4,[(0,4)],[],[],cards,[],4)
  restored=Plan.from_dict(plan.to_dict());self.assertEqual(restored,plan)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'card.png';x,y=card_image(cards[0],path,profile='ru_football')
   with Image.open(path) as im:self.assertLessEqual(y+im.height,720);self.assertLessEqual(x+im.width,1280)
 def test_sound_disabled_and_duration(self):
  from hockey_editor.card_sounds import create
  cards=enrich(Block(),[Line('Пять побед подряд.',1,3)],[]);plan=Plan(0,4,[(0,4)],[],[],cards,[],4)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.assertIsNone(create(plan,Settings(card_sound_volume=0),root));self.assertIsNone(create(plan,Settings(animate_cards=False),root))
   path=create(plan,Settings(),root)
   with wave.open(str(path)) as wav:
    self.assertEqual(wav.getnframes(),4*24000);self.assertEqual(set(wav.readframes(24000)),{0})
if __name__=='__main__':unittest.main()
