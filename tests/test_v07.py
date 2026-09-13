"""Profile isolation, Uzbek semantics and football footage bounds."""
import copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image,ImageDraw
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.profiles import apply_profile,kit_path
from hockey_editor.uzbek import parse_script,prepared,classify,events,spoken_uz,framing_cards_uz
from hockey_editor.timeline import Line,placements,Card
from hockey_editor.graphics import card_image
from hockey_editor.goals import source_signature,propose,Candidate
from hockey_editor.editing import project_edit_key

SCRIPT="""KIRISH
0:00–1:00
Assalomu alaykum! Birinchi o'yin — Roma va Milan.
Aytgancha, qo'shimcha prognozlarim bor.
Ularni Telegram kanalimga joylayman.
Havola video tavsifida.
AUGSBURG — BAYER
1:00–3:20
Augsburg o'z maydonida o'ynaydi.
Mening tanlovim — Bayer X2 va 1,5 tadan ko'p gol.
BORUSSIYA DORTMUND — PADERBORN
3:20–5:40
Mening tanlovim — Dortmund g'alaba qiladi va 1,5 tadan ko'p gol bo'ladi.
YAKUNIY TANLOVLAR
5:40–7:00
Augsburg — Bayer.
Mening tanlovim — Bayer X2 va 1,5 tadan ko'p gol.
Borussiya Dortmund — Paderborn.
Mening tanlovim — Dortmund g'alaba qiladi va 1,5 tadan ko'p gol bo'ladi.
YAKUNIY CTA
7:00–7:30
Telegram haqida unutmang!
Havola video tavsifida.
Layk bosing va kanalga obuna bo'ling.
Barchangizga omad!
Keyingi videoda ko'rishguncha!
"""
class V07Tests(unittest.TestCase):
 def test_incomplete_clip_cache_is_rebuilt_before_use(self):
  from hockey_editor.goals import cut_candidate
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=MatchSource(str(root/'source.mp4'),'Roma','Milan',sport='football')
   selected=SimpleNamespace(source_signature='key',source_start=1,event_time=3,source_end=5)
   def metadata(path):
    if str(path)==source.path:return {'duration':20,'video':True}
    if Path(path).read_bytes()!=b'complete':raise ValueError('Incomplete MP4')
    return {'duration':4,'video':True}
   def render(args,cancel):Path(args[-1]).write_bytes(b'complete')
   with patch('hockey_editor.goals.source_signature',return_value='key'),patch('hockey_editor.goals.probe',side_effect=metadata),patch('hockey_editor.goals.run',side_effect=render) as run:
    path=cut_candidate(source,selected,root,threading.Event());self.assertEqual(run.call_count,1)
    path.write_bytes(b'interrupted')
    self.assertEqual(cut_candidate(source,selected,root,threading.Event()),path);self.assertEqual(run.call_count,2)
    self.assertEqual(cut_candidate(source,selected,root,threading.Event()),path);self.assertEqual(run.call_count,2)
    self.assertEqual(path.read_bytes(),b'complete')
 def test_timecodes_are_metadata_not_speech(self):
  intro,blocks,outro=parse_script(SCRIPT)
  self.assertEqual(len(blocks),2);self.assertEqual(blocks[0].source_hint,[60,200]);self.assertEqual(outro.source_hint,[340,450]);self.assertEqual(outro.language,'uz')
  self.assertNotIn('1:00',prepared(blocks[0]));self.assertNotIn('YAKUNIY CTA',prepared(outro))
  tg=[s for s in prepared(intro).splitlines() if 'Telegram' in s];self.assertEqual(len(tg),1);self.assertIn('Havola',tg[0])
 def test_bets_keep_team_direction_and_total_not_fixture_specific(self):
  cases=[("Mening tanlovim — Milan X2 va 2,5 tadan ko'p gol.",'Milan X2\nJami gollar: 2,5 dan ko‘p'),("Mening tanlovim — Roma g'alaba qiladi va 3,5 tadan kam gol.",'Roma g‘alabasi\nJami gollar: 3,5 dan kam'),("1,5 TADAN KO'P GOL.",'Jami gollar: 1,5 dan ko‘p')]
  for text,want in cases:self.assertEqual(classify(text),('ПРОГНОЗ',want))
  self.assertNotEqual(classify("Agar Roma hisobni ochsa, ko'proq hujum qiladi.")[0],'ПРОГНОЗ')
 def test_conditions_and_injuries_retain_subject(self):
  for s in ["Birinchisi — Milan 90 daqiqada mag'lub bo'lmasligi kerak.","Ikkinchisi — uchrashuvda kamida ikkita gol bo'lishi kerak.","Paderbornning gol urishi majburiy emas.","2:0 — mos."]:
   title,text=classify(s);self.assertEqual(title,'УСЛОВИЯ ПРОГНОЗА');self.assertTrue(text)
  self.assertIn('Milan',classify("Birinchisi — Milan 90 daqiqada mag'lub bo'lmasligi kerak.")[1])
  s='Futbolchi jarohat sabab uchrashuvda ishtirok eta olmaydi.';self.assertEqual(classify(s),('СОСТАВ КОМАНДЫ',s))
 def test_single_source_also_covers_other_references(self):
  m=MatchSource('a.mp4','Roma','Milan',sport='football');other=MatchSource('b.mp4','Mainz','Bayer',sport='football')
  b=Block(language='uz',match_ids=[m.id],script="Avvalgi uchrashuvda Juventus kuchli o'ynadi.\nRoma o'z maydonida hujum qiladi.\nMening tanlovim — Milan X2 va 1,5 tadan ko'p gol.")
  requests=events(b,[m,other]);self.assertEqual(len(requests),2);self.assertTrue(all(e.kind=='play' and e.source_id==m.id and e.score is None for e in requests))
  b.match_ids.append(other.id)
  with self.assertRaisesRegex(ValueError,'bitta|одну'):events(b,[m,other])
 def test_profile_save_and_cache_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Project(host=str(Path(d)/'host.mp4'));Path(p.host).touch();old=project_edit_key(p,0);p.assets={'telegram':'russian.mov'}
   with patch('hockey_editor.profiles.kit_path',return_value=Path(d)/'empty.json'):apply_profile(p,'uz_football')
   self.assertEqual(p.assets,{});self.assertNotEqual(old,project_edit_key(p,0));self.assertEqual(p.intro.language,'uz')
   p.blocks[0].source_hint=[60,200];p.save(Path(d)/'project.json');loaded=Project.load(Path(d)/'project.json')
   self.assertEqual(loaded.profile,'uz_football');self.assertEqual(loaded.blocks[0].source_hint,[60,200]);self.assertEqual(loaded.outro.language,'uz')
   self.assertNotEqual(kit_path('ru_hockey'),kit_path('uz_football'))
   m=MatchSource(p.host,'A','B');before=source_signature(m);m.sport='football';self.assertNotEqual(before,source_signature(m))
 def test_uzbek_numbers(self):
  value=spoken_uz("X2 va 2,5 gol, 90 daqiqa, 1:2.")
  self.assertIn('iks ikki',value);self.assertIn('ikki butun besh',value);self.assertIn("to'qson",value);self.assertIn('bir ikki',value)
 def test_recap_separate_pair_and_bet_reuses_primary(self):
  intro,blocks,outro=parse_script(SCRIPT);p=Project(profile='uz_football',blocks=blocks,assets={'telegram':'tg.mov','subscribe':'sub.mov'})
  ls=[Line(t,i*4,(i+1)*4) for i,t in enumerate(prepared(outro).splitlines())]
  blocks[0].edit_plan={'cards':[{'title':'ПРОГНОЗ','text':'Bayer X2 · tahrir'}]}
  with patch('hockey_editor.media.probe',return_value={'duration':3}):cards,_=framing_cards_uz(p,outro,ls,ls[-1].end)
  bets=[c for c in cards if c.title=='ПРОГНОЗ'];self.assertEqual([c.forecast_id for c in bets],[b.uid for b in blocks]);self.assertEqual(bets[0].text,'Bayer X2 · tahrir')
  tg=next(c for c in cards if c.title=='ТЕЛЕГРАМ');self.assertEqual((tg.start,tg.end),(ls[tg.line].start,ls[tg.line].end))
 def test_card_render_and_placement(self):
  b=Block(title='Roma — Milan',language='uz');lines=[Line("Mening tanlovim — Milan X2 va 2,5 tadan ko'p gol.",5,9)]
  _,cards,_=placements(b,lines,{},10);self.assertTrue(any(c.text.startswith('Milan X2') for c in cards))
  with tempfile.TemporaryDirectory() as d:
   for i,c in enumerate(cards):
    out=Path(d)/f'{i}.png';xy=card_image(c,out,profile='uz_football');self.assertTrue(out.exists());self.assertGreaterEqual(xy[0],0)
 def test_football_rejects_empty_field_and_closeup(self):
  from hockey_editor.football import frame_features,gameplay_ranges
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);im=Image.new('RGB',(240,135),(40,140,40));im.save(d/'field.png');self.assertFalse(frame_features(d/'field.png')[1])
   draw=ImageDraw.Draw(im)
   for x,y in [(30,45),(70,70),(110,95),(170,60),(205,110)]:draw.rectangle((x,y,x+2,y+6),fill='white')
   im.save(d/'play.png');self.assertTrue(frame_features(d/'play.png')[1])
   draw.rectangle((60,20,190,130),fill=(210,160,110));im.save(d/'close.png');self.assertFalse(frame_features(d/'close.png')[1])
   # Invalid frame splits the range; guarded intervals cannot cross it.
   states=[(None,True,1,5)]*20+[(None,False,0,0)]+[(None,True,1,5)]*20
   import numpy as np
   count=[0]
   def features(_):
    i=count[0];count[0]+=1;return np.ones((2,2))*((i%2)*10),states[i][1],1,5
   with patch('hockey_editor.football.frame_features',side_effect=features):ranges=gameplay_ranges(list(range(41)),10.25,threading.Event())
   self.assertEqual(len(ranges),2);self.assertLess(ranges[0][1],5);self.assertGreater(ranges[1][0],5)
