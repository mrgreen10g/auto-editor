import json,tempfile,unittest
import threading
from pathlib import Path
from unittest.mock import patch
from test_uz_speech import sample,project,segment
from hockey_editor.uz_speech import prepare,telegram_spans
from hockey_editor.uz_forecasts import match_forecasts
from hockey_editor.framing import forecast_text

class ForecastTests(unittest.TestCase):
 def test_total_value_ignores_unrelated_odds(self):
  from hockey_editor.uz_forecasts import features
  self.assertEqual(features("Koeffitsiyent 1.90, jami 2,5 dan ko'p gol.")['value'],2.5)
 def test_intro_names_do_not_capture_preceding_bayer(self):
  from hockey_editor.uz_speech import pair_hits
  words=segment(0,8,'Augsburg Bayer, Borussia Dortmund, Maddi Boron yoki Mays Antraxtda.')['words']
  a,b=pair_hits('Borussiya Dortmund — Paderborn',words)[0]
  self.assertEqual(words[a]['word'],'Borussia');self.assertEqual(words[b]['word'],'Boron')
 def test_unrecognized_short_farewell_retained_without_extending_telegram(self):
  from hockey_editor.media import run,probe
  from hockey_editor.model import Project,Block
  from hockey_editor.engine import Engine
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);host=root/'host.mp4'
   run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=8','-f','lavfi','-i','sine=f=650:r=48000:d=8','-t','8','-af','afade=t=out:st=6.5:d=0.1','-c:v','libx264','-c:a','aac',host])
   b=Block(kind='outro',language='uz',script='Telegram kanalimizda yangiliklar. Havola tavsifda.',asr_lines=[{'text':'Telegram kanalimizda yangiliklar. Havola tavsifda.','start':3,'end':6.8,'agreement':0}],speech_cards={'0':{'title':'ТЕЛЕГРАМ','text':'Telegram'}})
   p=Project(profile='uz_football',host=str(host),blocks=[b],assets={'telegram':str(host)})
   p.settings.auto_rotate=False;p.settings.cut_pauses=True
   e=Engine(p,0,root/'cache',threading.Event());plan=e.analyze()
   self.assertAlmostEqual(plan.source_end,8,delta=.04);self.assertEqual(plan.lines[-1].text,'')
   card=next(c for c in plan.cards if c.title=='ТЕЛЕГРАМ');self.assertGreater(plan.duration-card.end,1)
 def test_same_words_merged_or_split_into_asr_chunks(self):
  with tempfile.TemporaryDirectory() as d:
   host=Path(d)/'host.mp4';host.touch();p=project(host);data=sample()
   expected=prepare(p,data)
   original=[(p.outro.asr_lines[int(i)]['start'],p.outro.asr_lines[int(i)]['end'],c['forecast_id']) for i,c in p.outro.speech_cards.items() if c['title']=='ПРОГНОЗ']
   words=[w for s in data[8:11] for w in s['words']]
   for groups in ([words],[words[i:i+3] for i in range(0,len(words),3)]):
    changed=data[:8]+[{'start':ws[0]['start'],'end':ws[-1]['end'],'text':' '.join(w['word'] for w in ws),'words':ws} for ws in groups]+data[11:]
    self.assertEqual(prepare(p,changed),expected)
    got=[(p.outro.asr_lines[int(i)]['start'],p.outro.asr_lines[int(i)]['end'],c['forecast_id']) for i,c in p.outro.speech_cards.items() if c['title']=='ПРОГНОЗ']
    self.assertEqual(got,original)

 def test_reported_phonetic_recaps_and_extra_generic_summary(self):
  with tempfile.TemporaryDirectory() as d:
   host=Path(d)/'host.mp4';host.touch();p=project(host);data=sample()
   data[8]=segment(170,180,"Yana qaytaraman, birinchi uchrashuv bo'yicha bayir ma'lubim edik, sikki va umumiylik o'son biryamtidan ko'p degan variantni qildik.")
   data[9]=segment(180,188,"Uchrashuvda Borussiya g'alabasi va briyamtalarni ko'p go'l degan variantni qildik.")
   data[10]=segment(188,194,"Oxirgi o'yinda umumiygul soni briyamtalarni ko'p degan variantni qildik.")
   data.insert(11,segment(194,195,"Va mana shula asosida tanlovlarimizni qildik."))
   prepare(p,data)
   cards=[c for c in p.outro.speech_cards.values() if c['title']=='ПРОГНОЗ']
   self.assertEqual([c['forecast_id'] for c in cards],[b.uid for b in p.blocks]);self.assertTrue(all(c['needs_review'] for c in cards))

 def test_compound_pick_spans_two_sentences(self):
  p=project('host.mp4');owner=p.blocks[0];refs={owner.uid:forecast_text(owner)}
  data=[segment(10,13,'Mening tanlovim Bayer X2.'),segment(13,17,"Va 1,5 dan ko'p gol.")]
  got=match_forecasts(data,0,20,[owner],refs,False)
  self.assertEqual((got[0]['start'],got[0]['end']),(10,17));self.assertFalse(got[0]['needs_review'])

 def test_contradictory_total_cannot_hide_in_second_sentence(self):
  p=project('host.mp4');owner=p.blocks[0];refs={owner.uid:forecast_text(owner)}
  data=[segment(10,13,'Mening tanlovim Bayer X2.'),segment(13,17,"Va 2,5 dan ko'p gol.")]
  with self.assertRaises(ValueError):match_forecasts(data,0,20,[owner],refs,False)

 def test_wrong_team_or_order_is_not_assigned_by_count(self):
  p=project('host.mp4');refs={b.uid:forecast_text(b) for b in p.blocks}
  data=[segment(10,14,"Borussiya g'alabasi va 1,5 dan ko'p gol variant."),segment(15,19,"Bayer X2 va 1,5 dan ko'p gol variant."),segment(20,24,"Oxirgi o'yinda 1,5 dan ko'p gol variant.")]
  with self.assertRaises(ValueError):match_forecasts(data,0,30,p.blocks,refs)

 def test_distorted_telegram_requires_channel_and_link_context(self):
  data=segment(250,265,"Vaziyat o'zgarishi mumkin, va shunga o'xshirish svej informatsiyalar hammasi tizligi amkonimizda topiladi, silqa esa tavsifda.")
  spans=telegram_spans(data['words']);self.assertEqual(len(spans),1)
  va=next(w for w in data['words'] if w['word']=='va');self.assertEqual(spans[0][0],va['start'])
  self.assertFalse(telegram_spans(segment(1,5,'Shunga informatsiyalar hammasi yaxshi bo‘ladi.')['words']))
