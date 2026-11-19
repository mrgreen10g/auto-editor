import tempfile,unittest
from pathlib import Path
from PIL import Image
from hockey_editor.shorts_cta import cards,TITLE,is_invitation
from hockey_editor.shorts import finish_cards
from hockey_editor.model import Project,Block
from hockey_editor.timeline import Line,Card,Plan,Insert
from hockey_editor.review import attach
from hockey_editor.graphics import card_image

PHRASE='Мои прогнозы на эти матчи — в полном разборе.'
POINTER='Жми на видео под этим роликом!'
class ShortsInvitationTests(unittest.TestCase):
 def test_two_aligned_sentences_become_one_card(self):
  lines=[Line(PHRASE,2,4),Line(POINTER,4.2,6)]
  result=cards(lines,7)
  self.assertEqual(len(result),1);self.assertEqual((result[0].start,result[0].end),(2,6));self.assertEqual(result[0].line,-1)
  self.assertEqual(result[0].text,PHRASE+' '+POINTER)
 def test_one_line_and_no_false_telegram_match(self):
  self.assertEqual(len(cards([Line(PHRASE+' '+POINTER,1,6)],6)),1)
  self.assertFalse(is_invitation('Все прогнозы — в моём телеграм-канале.'))
  self.assertFalse(is_invitation('Мой прогноз — победа Ливерпуля.'))
 def test_timing_uncertainty_is_not_hidden(self):
  c=cards([Line(PHRASE,1,3,review_reason='Проверьте фразу'),Line(POINTER,3,5)],5)[0]
  self.assertEqual(c.review_reason,'Проверьте фразу')
 def test_final_card_has_priority_and_cuts_game_insert(self):
  b=Block(script=PHRASE+' '+POINTER,sport='football');p=Project(profile='ru_football_shorts',blocks=[b])
  lines=[Line(PHRASE,2,4),Line(POINTER,4,6)]
  output,clips=finish_cards(p,b,lines,[Card(2,6,'ПРОГНОЗ','ошибочно определённый прогноз')],[Insert('game.mp4',1,6,0,'Игра')],6)
  self.assertEqual([c.title for c in output],[TITLE]);self.assertEqual(clips[0].end,2)
  second,_=finish_cards(p,b,lines,output,clips,6);self.assertEqual(second,output)
 def test_no_invented_pick_in_teaser_or_unbet_short(self):
  for script in (PHRASE+' '+POINTER,'Команда забила девятнадцать голов за десять туров.'):
   b=Block(script=script,sport='football');p=Project(profile='ru_football_shorts',blocks=[b]);lines=[Line(script,0,6)]
   plan=Plan(0,6,[(0,6)],lines,[],cards(lines,6),[],6)
   attach(plan,b,p);self.assertFalse(any(c.title=='ПРОГНОЗ' for c in plan.cards));self.assertFalse(plan.review_items)
 def test_long_missing_pick_still_reviewed(self):
  b=Block(script='Команда забила два гола.',sport='football');p=Project(profile='ru_football',blocks=[b]);plan=Plan(0,6,[(0,6)],[Line(b.script,0,6)],[],[],[],6)
  attach(plan,b,p);self.assertTrue(any(c.title=='ПРОГНОЗ' for c in plan.cards))
 def test_explicit_short_pick_kept(self):
  b=Block(script='Мой прогноз — победа Ливерпуля.',sport='football');p=Project(profile='ru_football_shorts',blocks=[b]);plan=Plan(0,6,[(0,6)],[Line(b.script,0,6)],[],[Card(0,6,'ПРОГНОЗ','Победа Ливерпуля',0)],[],6)
  attach(plan,b,p);self.assertEqual(plan.cards[0].text,'Победа Ливерпуля')
 def test_graphic_is_phone_safe_and_not_plain_fact(self):
  c=cards([Line(PHRASE+' '+POINTER,0,5)],5)[0]
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'cta.png';x,y=card_image(c,p,profile='ru_football_shorts')
   with Image.open(p) as im:
    self.assertEqual(im.size,(608,256));self.assertEqual(y+im.height,1100)
    self.assertGreater(im.getpixel((304,225))[1],180)
