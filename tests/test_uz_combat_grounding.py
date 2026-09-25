import tempfile,unittest
from pathlib import Path
from hockey_editor.combat import name_position,parse_script,prepare,framing_cards,events
from hockey_editor.combat_cards import classify,confidence
from hockey_editor.fighters import same_fighter
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.timeline import Line,Card,placements
from test_uz_speech import segment

class GroundingTests(unittest.TestCase):
 def test_rematch_nickname_and_shared_surname(self):
  self.assertIsNotNone(name_position('DENIS POGODIN II','Deniz Paguddin'))
  self.assertIsNotNone(name_position('NABI “GANNIBAL” GADJIEV','Gannibal'))
  self.assertTrue(same_fighter('Maksim Barmin','MAKSIM “BALU” BARMIN'))
  self.assertFalse(same_fighter('Nabi Gadjiev','Abdulkadyr Gadjiev'))
 def test_counts_without_record_keyword_and_multiple_facts(self):
  title,body=classify("31 yosh, bazasi boks, yettita g‘alaba, beshta mag‘lubiyat, bitta durang. To‘rtta g‘alabasini nokaut bilan yakunlagan.")
  self.assertEqual(title,'СТАТИСТИКА')
  for fact in ('31 YOSH','REKORD: 7–5–1','4 KO','BAZA: BOKS'):self.assertIn(fact,body)
 def test_rhetorical_one_and_age_difference(self):
  self.assertIsNone(classify('Nabi har bir soniyada nokaut izlab yurmaydi.')[0])
  self.assertIn('6 YOSH KICHIK',classify('U olti yosh kichik.')[1])
 def test_spoken_bundle_autoaccepted_but_numbers_conflict_reviewed(self):
  text="31 yosh, yettita g‘alaba, beshta mag‘lubiyat, bitta durang."
  title,body=classify(text);b=Block(title='ALPHA FIRST — BETA SECOND')
  self.assertFalse(confidence(Card(0,8,title,body),Line(text,0,8,recognized=text),b,Project()))
  self.assertTrue(confidence(Card(0,8,title,body),Line(text,0,8,recognized=text.replace('yettita','oltita')),b,Project()))
 def test_no_written_unspoken_facts_and_intro_pairs_do_not_overlap(self):
  p=Project(profile='uz_combat',recording_times='00:00 00:10 intro\n00:10 00:30 fight',intro=Block(uid='intro',kind='intro',language='uz',sport='combat',script='Salom. Maksim Barmin David Oganesyan. Nabi Gadjiev Denis Pogodin.',featured_pairs=['MAKSIM BARMIN — DAVID OGANESYAN','NABI GADJIEV — DENIS POGODIN II']),blocks=[Block(title='MAKSIM “BALU” BARMIN — DAVID OGANESYAN',language='uz',sport='combat',script="Barmin 177 cm. Rekordi 3 g‘alaba 6 mag‘lubiyat.")],outro=Block(kind='outro',script=''))
  spoken=[segment(0,2,'Salom.'),segment(2,8,'Maksim Barmin David Agassian Nabi Gajiev Deniz Pogodiy'),segment(10,20,'Barmin umumiy beshta g‘alaba oltita mag‘lubiyat.')]
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'host';f.touch();p.host=str(f);prepare(p,spoken,30)
  self.assertNotIn('177',' '.join(l['text'] for l in p.blocks[0].asr_lines))
  self.assertIn('REKORD: 5–6',classify(p.blocks[0].asr_lines[0]['text'])[1])
  cards,_=framing_cards(p,p.intro,[Line(**l) for l in p.intro.asr_lines],10)
  self.assertEqual(len(cards),2);self.assertLessEqual(cards[0].end,cards[1].start)
 def test_nickname_source_binding_and_comparison_safety(self):
  source=MatchSource('fight.mp4','','',sport='combat',fighter='Maksim Barmin')
  b=Block(title='MAKSIM “BALU” BARMIN — DAVID OGANESYAN',match_ids=[source.id],sport='combat',script='Balu bosimni oshiradi. Barmin va Oganesyan tajribali. U zarba beradi.')
  found=events(b,[source]);self.assertEqual(len(found),1);self.assertEqual(found[0].source_id,source.id)
 def test_football_words_and_arguments(self):
  from hockey_editor.uzbek import classify as football
  self.assertEqual(football('So‘nggi beshta uchrashuvda uchta g‘alaba.')[0],'СТАТИСТИКА')
  self.assertEqual(football('Jamoaning himoyasida katta muammo bor.')[0],'ИНФОРМАЦИЯ')
  self.assertIsNone(football('Bugun qiziqarli uchrashuv kutmoqda.')[0])
 def test_anonymous_pick_does_not_create_premature_bet(self):
  b=Block(title='MAKSIM BARMIN — DAVID OGANESYAN',language='uz',sport='combat',forecast='BARMIN G‘ALABASI')
  _,cards,_=placements(b,[Line('Bizning tanlovimiz g‘alaba bo‘ladi.',6,10)],{},15)
  self.assertFalse(any(c.title=='ПРОГНОЗ' for c in cards))
class RetryTests(unittest.TestCase):
 def test_retry_cannot_lose_a_bet_or_change_clear_numbers(self):
  from hockey_editor.uz_refine import preferable
  def segment(text,p):return {'text':text,'words':[dict(word=w,probability=p) for w in text.split()]}
  a=segment("Mening tanlovim Barmin g‘alabasi kutilmoqda",.5)
  b=segment("Mening tanlovim Barmin jang qiladi",.95)
  self.assertFalse(preferable(a,b,'uz_combat'))
  a=segment("Barmin beshta g‘alaba oltita mag‘lubiyat",.9)
  b=segment("Barmin uchta g‘alaba oltita mag‘lubiyat",.99)
  self.assertFalse(preferable(a,b,'uz_combat'))
 def test_arguments_are_compact_and_keep_uncertainty(self):
  _,body=classify('G‘alaba qaraymiz, chunki uning jismoniy bosim va tempi raqibga juda ko‘p muammo yaratishi mumkin.')
  self.assertEqual(body,'Bosim va temp raqibga muammo yaratishi mumkin')
  self.assertLess(len(body.split()),12)
  _,body=classify('Agar raqibi bosimni oshirsa, javob berishi mumkin.')
  self.assertIn('Agar',body)
 def test_ufc_rates_and_finish_types(self):
  title,body=classify("UFC daqiqasiga 2,4 ta muhim zarba, zarbalardan himoyasi 64 foiz, takedownlardan himoyasi 77 foiz.")
  self.assertEqual(title,'СТАТИСТИКА')
  for fact in ('2.4','64%','77%'):self.assertIn(fact,body)
  self.assertEqual(classify('Vieira 9 ta sabmishen.'),('СТАТИСТИКА','9 SUB'))
 def test_catalog_disambiguates_first_names_and_needs_no_assets(self):
  from hockey_editor.fighters import roster_names
  self.assertTrue(roster_names('Nabi Gadjiev'))
  self.assertFalse(any('Абдулкадыр' in n for n in roster_names('Nabi Gadjiev')))

if __name__=='__main__':unittest.main()
