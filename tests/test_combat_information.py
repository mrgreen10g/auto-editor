import unittest,tempfile
from pathlib import Path
from PIL import Image
from hockey_editor.combat_facts import digits,classify,visual,enrich,image
from hockey_editor.model import Block
from hockey_editor.timeline import Line,Card
from hockey_editor.profiles import SPEAKER_GROUPS,PROFILES,group_for,group_profiles

class CombatInformationTests(unittest.TestCase):
 def test_literal_numbers(self):
  self.assertIn('177',digits('сто семьдесят семь ударов'))
  self.assertIn('5,67',digits('пять целых шестьдесят семь сотых'))
  data=visual('Контроль семь минут сорок шесть секунд против двух минут сорока шести секунд.','БОРЬБА И КОНТРОЛЬ')
  self.assertIn('7:46',[x['value'] for x in data['metrics']])
 def test_elliptical_context(self):
  lines=[Line('Пропускает 5,67 значимого удара в минуту.',0,3),Line('А Стирлинг — только 2,46.',3,6)]
  cards=enrich(Block(sport='combat'),lines,[])
  self.assertEqual(len(cards),2)
  self.assertEqual(cards[1].visual['metrics'][0]['value'],'2,46')
  self.assertEqual(enrich(Block(sport='combat'),lines[1:],[]),[])
 def test_risks_are_not_facts(self):
  t='Если он нанесет 177 ударов, может победить.'
  self.assertEqual(classify(t),'СЦЕНАРИЙ И РИСК')
  self.assertEqual(visual(t,classify(t))['metrics'],[])
  self.assertFalse(classify('Мой прогноз — победа бойца.'))
  self.assertEqual(classify('Перенес операцию на шее.'),'ЗДОРОВЬЕ И ВЕСОГОНКА')
 def test_groups_complete_and_exclusive(self):
  found=[]
  for group,_ in SPEAKER_GROUPS:
   for key,_ in group_profiles(group):
    self.assertEqual(group_for(key),group);found.append(key)
  self.assertEqual(len(found),len(set(found)))
  self.assertEqual(set(found),{k for rows in PROFILES.values() for k,_ in rows})
 def test_render_both_formats(self):
  text='Он нанес 177 значимых ударов против 174 значимых ударов.'
  card=Card(0,5,'УДАРНАЯ СТАТИСТИКА',text,visual=visual(text,'УДАРНАЯ СТАТИСТИКА'))
  with tempfile.TemporaryDirectory() as tmp:
   for shorts in (False,True):
    p=Path(tmp)/f'{shorts}.png';image(card,p,shorts=shorts)
    with Image.open(p) as im:self.assertEqual(im.mode,'RGBA');self.assertGreater(im.width,100)
