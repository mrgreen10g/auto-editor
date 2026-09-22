import tempfile,threading,unittest,copy,wave
from pathlib import Path
from unittest.mock import patch,Mock
from hockey_editor.model import Project,Block,MatchSource,EventRequest
from hockey_editor.combat import parse_script,events,prepare,framing_cards,recover_gaps
from hockey_editor.combat_scan import clock_value,live_ranges
from hockey_editor.goals import propose,montage_block
from hockey_editor.episode import assembly_project
from hockey_editor.timeline import Plan,Line,Card
from hockey_editor.review import attach,framing_draft,draft_alignment
from hockey_editor.speech_boundaries import intro_floor,first_analysis_start
from test_uz_speech import segment

SCRIPT='''TOP DOG
ALEKSANDR XALZOV — AZAMAT ESPAY
ALEKSEY MELNIKOV — MAKSIM SULGIN
KIRISH | 0:00–0:55
Salom. Birinchi jang Aleksandr Xalzov va Azamat Espay.
Telegram kanal. Havola video tavsifida. Boshladik!
[МОНТАЖЁРУ:
DO NOT READ THIS
https://example.org
]
1. ALEKSANDR XALZOV — AZAMAT ESPAY | 0:55–3:10
Birinchi jang Aleksandr Xalzov va Azamat Espay.
Xalzovning rekordi 4 g'alaba va 1 mag'lubiyat.
U texnik jihatdan yaxshi jangchi.
Lekin Espayning asosiy xavfi kuchli zarba va agressiv jang.
U masofani qisqartirib raqibni almashinuvga tortadi.
Xalzov va Espay kuchli jangchilar.
U juda kuchli zarba beradi.
Shuning uchun birinchi tanlovim — Aleksandr Xalzov g'alabasi.
PROGNOZ: ALEKSANDR XALZOV G'ALABASI.
'''

class CombatTests(unittest.TestCase):
 def project(self):
  a,b,z=parse_script(SCRIPT);return Project(profile='uz_combat',intro=a,blocks=b,outro=z,full_video=True)
 def test_partial_script_does_not_create_index_blocks_or_read_notes(self):
  p=self.project();self.assertEqual(len(p.blocks),1);self.assertEqual(len(p.intro.featured_pairs),2)
  self.assertNotIn('DO NOT READ',p.intro.script);self.assertFalse(p.outro.script)
  self.assertEqual(len(assembly_project(p).blocks),2);self.assertNotIn('PROGNOZ:',p.blocks[0].script)
 def test_complete_many_fights(self):
  s='KIRISH\nSalom do‘stlar bugun juda qiziqarli janglar.\n'
  for i in range(12):s+=f'{i+1}. FIGHTER ALPHA — FIGHTER BETA | 1:00–2:00\nBugun bu jangchilar haqida juda batafsil gaplashamiz.\n'
  s+='YAKUNIY TANLOVLAR\nTanlovlarni takrorlaymiz va hammaga xayr.'
  _,b,z=parse_script(s);self.assertEqual(len(b),12);self.assertTrue(z.script)
 def test_no_mandatory_forecast(self):
  p=self.project();b=p.blocks[0];b.forecast='';b.script='Xalzov kuchli jangchi. Espay juda kuchli raqib.'
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'host';path.touch();p.host=str(path)
   plan=Plan(0,10,[(0,10)],[Line(b.script,0,10)],[],[],[],10);attach(plan,b,p)
   self.assertFalse(any(c.title=='ПРОГНОЗ' for c in plan.cards))
 def test_fighter_ownership_and_comparison_reset(self):
  p=self.project();b=p.blocks[0]
  sources=[MatchSource('a','Alex','',sport='combat',fighter='ALEKSANDR XALZOV'),MatchSource('b','Azamat','',sport='combat',fighter='AZAMAT ESPAY')]
  b.match_ids=[s.id for s in sources];found=events(b,sources)
  self.assertEqual([e.source_id for e in found],[sources[0].id]*2+[sources[1].id]*2)
  self.assertFalse(any('U juda kuchli' in e.phrase for e in found))
 def test_no_other_fighter_substitution_or_auto_acceptance(self):
  a=MatchSource('a','A','',sport='combat',fighter='A');b=MatchSource('b','B','',sport='combat',fighter='B')
  candidate=dict(id='combat-0',start=2,end=5,time=3,confidence=.9,kind='play',score=None,before=None,note='Check')
  e=EventRequest(a.id,'zarba','play')
  propose([e],{b.id:{'signature':'b','candidates':[candidate]}},[a,b],True);self.assertIsNone(e.selection)
  propose([e],{a.id:{'signature':'a','candidates':[candidate]}},[a,b],True);self.assertFalse(e.selection.accepted)
  missing=EventRequest('','zarba','play');propose([missing],{a.id:{'signature':'a','candidates':[candidate]}},[a,b],True);self.assertIsNone(missing.selection)
 def test_empty_asr_preserves_script_without_fake_outro(self):
  p=self.project()
  with tempfile.TemporaryDirectory() as d:
   host=Path(d)/'host';host.touch();p.host=str(host);prepare(p,[],100)
   self.assertTrue(p.blocks[0].asr_lines);self.assertTrue(all(l['review_reason'] for l in p.blocks[0].asr_lines));self.assertFalse(p.outro.asr_lines)
 def test_absent_telegram_is_normal_in_production_cards(self):
  p=self.project();lines=[Line('Telegram kanal. Havola.',0,5,recognized='Boshqa so‘zlar')]
  cards,_=framing_draft(p,p.intro,lines,5);self.assertFalse(any(c.title=='ТЕЛЕГРАМ' for c in cards))
 def test_roundtrip(self):
  p=self.project();p.matches=[MatchSource('fight.mp4','','',sport='combat',fighter='ALEKSANDR XALZOV')]
  with tempfile.TemporaryDirectory() as d:
   file=Path(d)/'project.hockeyproj';p.save(file);q=Project.load(file)
   self.assertEqual(q.blocks[0].sport,'combat');self.assertEqual(q.blocks[0].forecast,p.blocks[0].forecast);self.assertEqual(q.intro.featured_pairs,p.intro.featured_pairs);self.assertEqual(q.matches[0].fighter,p.matches[0].fighter)
 def test_pending_footage_does_not_abort_timing(self):
  p=self.project();b=p.blocks[0];b.match_ids=['x'];b.events=[EventRequest('x','zarba','play')]
  self.assertFalse(montage_block(p,0,'.',threading.Event()).clips)
 def test_clock_two_digit_minutes_and_frozen_interview_rejected(self):
  self.assertEqual(clock_value('00:51'),51);self.assertEqual(clock_value('2:01'),121);self.assertIsNone(clock_value('31:55'))
  self.assertFalse(live_ranges([(0,51),(2,51),(4,51),(6,51)],8))
  self.assertEqual(live_ranges([(0,51),(2,49),(4,47),(6,45)],8),[[.5,5.5]])
 def test_silence_is_not_retranscribed(self):
  import numpy as np
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'voice.wav'
   with wave.open(str(path),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(np.zeros(16000*20,dtype='<i2').tobytes())
   model=Mock();segments=[segment(0,2,'Salom'),segment(18,20,'Xayr')]
   self.assertEqual(recover_gaps(model,path,segments,threading.Event(),lambda _:None),segments);model.transcribe.assert_not_called()
 def test_combat_cards_have_no_logo_dependency(self):
  from hockey_editor.graphics import card_image
  with tempfile.TemporaryDirectory() as d:
   for i,(title,text) in enumerate([('РАЗБОР МАТЧА','ALEKSANDR XALZOV — AZAMAT ESPAY'),('ПРОГНОЗ',"ALEKSANDR XALZOV G'ALABASI"),('СТАТИСТИКА','23 yosh · 4 g‘alaba · 2 KO'),('СМЕНА МАТЧА','ALEKSANDR XALZOV — AZAMAT ESPAY')]):
    path=Path(d)/f'{i}.png';card_image(Card(0,5,title,text),path,{'ALEKSANDR XALZOV':'missing-logo.png'},'uz_combat');self.assertTrue(path.is_file())

class IntroBoundaryTests(unittest.TestCase):
 def test_cue_end_is_not_six_words_early(self):
  s=segment(0,10,'Ссылка находится в описании. Переходим к разбору.');self.assertAlmostEqual(intro_floor(s['words']),s['words'][-1]['end'])
 def test_pair_after_promo_wins_over_intro_pair(self):
  blocks=[Block(kind='intro'),Block(title='Салават Юлаев — Нефтехимик')]
  seg=[segment(0,5,'Сегодня Салават Юлаев Нефтехимик.'),segment(8,16,'Ставки в телеграм канале ссылка находится в описании.'),segment(16,18,'Переходим к разбору.'),segment(18,23,'Соловат Юлаев Нефтихимик сегодня играют.')]
  self.assertAlmostEqual(first_analysis_start(blocks,seg),18)
 def test_no_telegram_but_transition_cue(self):
  blocks=[Block(kind='intro'),Block(title='Торпедо — Спартак')];seg=[segment(0,3,'Начинаем разбор.'),segment(3,8,'Торпедо Спартак встречаются сегодня.')]
  self.assertAlmostEqual(first_analysis_start(blocks,seg),3)
 def test_weak_alignment_still_respects_intro_boundary(self):
  blocks=[Block(kind='intro',script='Сегодня хоккей. Ставки в телеграм. Переходим к разбору.'),Block(title='Торпедо — Спартак',script='Торпедо — Спартак. Здесь будет победа хозяев.')]
  segments=[segment(0,5,'Всем привет ставки в телеграм.'),segment(5,7,'Переходим к разбору.'),segment(7,15,'Торпедо Спартак непохожие слова.')]
  result=draft_alignment(blocks,segments,15,'Проверьте');self.assertEqual(result[blocks[1].uid][0][0].start,7);self.assertEqual(result[blocks[0].uid][0][-1].end,7)

if __name__=='__main__':unittest.main()
