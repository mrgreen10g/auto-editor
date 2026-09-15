import unittest
from unittest.mock import patch
from hockey_editor.model import Project,Block
from hockey_editor.timeline import Line,Card
from hockey_editor.uzbek import asr_framing_cards,framing_cards_uz
from hockey_editor.framing import optional_subscription

class OptionalSubscriptionTests(unittest.TestCase):
 def test_uz_paths_skip_long_keep_short_and_question(self):
  p=Project(blocks=[],assets={'subscribe':'sub.mov'})
  b=Block(kind='outro',language='uz')
  lines=[Line('Obuna bo‘ling, izoh yozing?',7,9),Line('Xayr, ko‘rishguncha!',9,10)]
  for renderer in (asr_framing_cards,framing_cards_uz):
   for length in (2,3,8):
    with self.subTest(renderer=renderer.__name__,length=length),patch('hockey_editor.media.probe',return_value={'duration':length}):
     cards,warnings=renderer(p,b,lines,10)
     subs=[c for c in cards if c.title=='ПОДПИСКА']
     self.assertEqual(bool(subs),length<=3)
     if subs:self.assertEqual(subs[0].end-subs[0].start,length)
     self.assertEqual(bool(warnings),length>3)
     self.assertTrue(any(c.title=='ВОПРОС ЗРИТЕЛЯМ' for c in cards))
     self.assertEqual(lines[-1].end,10)
 def test_cached_subscription_filter_leaves_other_cards_untouched(self):
  bet=Card(4,6,'ПРОГНОЗ','X2');tg=Card(1,4,'ТЕЛЕГРАМ','Telegram')
  cards,warnings=optional_subscription([bet,tg,Card(8,15,'ПОДПИСКА','Obuna')],10)
  self.assertEqual(cards,[bet,tg]);self.assertEqual(len(warnings),1)
  self.assertEqual(optional_subscription(cards,10),(cards,[]))
