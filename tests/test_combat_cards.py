import copy,json,tempfile,unittest
from pathlib import Path
from dataclasses import asdict
from hockey_editor.model import Project,Block,EventRequest
from hockey_editor.timeline import Plan,Line,Card,Insert,placements
from hockey_editor.review import attach,resolve,pending,preserve_edits
from hockey_editor.combat_cards import classify,migrate_project,migrate_plan,confidence
from hockey_editor.episode import assembly_project,combine,store_episode,saved_episode


class CombatCardTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.host=Path(self.tmp.name)/'host.mp4';self.host.touch()
  self.b=Block(uid='fight',title='VALERIY OSOBOV — RUSLAN ALIYAROV',sport='combat',language='uz',script="Osobovning rekordi — 6 g'alaba va 2 mag'lubiyat.")
  self.p=Project(profile='uz_combat',host=str(self.host),blocks=[self.b])
 def tearDown(self):self.tmp.cleanup()
 def plan(self,lines,cards=()):return Plan(0,20,[(0,20)],lines,[],list(cards),[],20)
 def test_uncertain_prose_never_becomes_a_card(self):
  lines=[Line('Masofani nazorat qiladi.',0,10,1,'Нет совпадения',''),Line('Shoshilmaydi.',10,20,1,'Нет совпадения','')]
  p=attach(self.plan(lines),self.b,self.p)
  self.assertFalse(p.cards);self.assertFalse(pending(p));self.assertEqual(p.lines[0].recognized,'')
 def test_record_is_local_despite_bad_surrounding_alignment(self):
  l=Line(self.b.script,0,10,1,'Нет надёжного совпадения.',"Asobovni umumiy rekordi oltida g‘alaba ikkita ma’lubiyot")
  title,text=classify(l.text);p=attach(self.plan([l],[Card(0,10,title,text,0)]),self.b,self.p)
  self.assertEqual(p.cards[0].text,'REKORD: 6–2');self.assertFalse(pending(p))
 def test_old_speech_annotations_cannot_restore_keyword_cards(self):
  text="Besh raundlik janglarga tayyorligi yuqoriroq ko'rinadi."
  self.b.speech_cards={'0':{'title':'СТАТИСТИКА','text':text,'needs_review':True}}
  _,cards,_=placements(self.b,[Line(text,0,20)],{},20,'high')
  self.assertFalse(any(c.title=='СТАТИСТИКА' for c in cards))
 def test_missing_or_conflicting_number_still_requires_review(self):
  for heard in ('',"Osobovning rekordi 5 g'alaba va 2 mag'lubiyat","Osobovning rekordi 2 g'alaba va 6 mag'lubiyat"):
   l=Line(self.b.script,0,10,recognized=heard);p=attach(self.plan([l],[Card(0,10,'СТАТИСТИКА','REKORD: 6–2',0)]),self.b,self.p)
   self.assertEqual(len(pending(p)),1)
 def test_record_cannot_change_fighter_or_swap_wins_and_losses(self):
  for heard in ("Aliyarovning rekordi 6 g'alaba va 2 mag'lubiyat", "Osobovning rekordi 6 mag'lubiyat va 2 g'alaba"):
   line=Line(self.b.script,0,10,recognized=heard)
   card=Card(0,10,'СТАТИСТИКА','REKORD: 6–2',0)
   self.assertTrue(confidence(card,line,self.b,self.p))
 def test_stat_selection_is_concrete_not_keyword_subtitles(self):
  for text in ('Va bu statistika uslubini tushuntiradi.',"Besh raundlik janglarga tayyorligi yuqoriroq ko'rinadi.",'Agar ikki nokaut bo‘lsa, vaziyat o‘zgaradi.'):
   self.assertIsNone(classify(text)[0])
  self.assertEqual(classify('Yetti nokaut.'),('СТАТИСТИКА','7 KO'))
  self.assertEqual(classify('Yana o‘n santimetr.'),('СТАТИСТИКА','FARQ: 10 CM'))
  self.assertEqual(classify("Rekordi — 1 g'alaba va 2 mag'lubiyat, bitta nokaut."),('СТАТИСТИКА','REKORD: 1–2'))
 def test_winner_claim_checks_outcome_owner_and_negation(self):
  card=Card(0,10,'ПРОГНОЗ',"VALERIY OSOBOV G'ALABASI",0,forecast_id=self.b.uid)
  for heard in ("Osobov Aliyarov jangida Valeriy Asobov g'alabasi kutilmoqda.","Asobov yutishi kerak."):
   self.assertFalse(confidence(card,Line('',0,10,recognized=heard),self.b,self.p))
  for heard in ("Osobov Aliyarov jangida Aliyarov g'alabasi.","Osobov yutmaydi.","Osobov kuchli jangchi."):
   self.assertTrue(confidence(card,Line('',0,10,recognized=heard),self.b,self.p))
 def legacy(self):
  line=Line('Masofani nazorat qiladi.',0,10,1,'Нет совпадения','Masofani nazorat qiladi.', 'fight:line:0')
  card=Card(0,10,'ИНФОРМАЦИЯ',line.text,0,review_id='legacy',review_reason=line.review_reason)
  p=self.plan([line],[card]);p.input_key='stable'
  p.edit_baseline={'cards':[asdict(card)],'inserts':[]}
  p.review_items=[dict(id='legacy',block_id='fight',start=0,end=10,reason=line.review_reason,script=line.text,recognized=line.recognized,status='pending')]
  return p
 def test_blanket_confirmation_is_cleaned_but_authored_text_survives(self):
  old=self.legacy();old=resolve(old,'legacy','confirmed');data=old.to_dict()
  self.assertTrue(migrate_plan(data,self.p,self.b));self.assertFalse(data['cards']);self.assertFalse(data['review_items'])
  authored=resolve(self.legacy(),'legacy','confirmed',text='МОЯ ЗАМЕТКА').to_dict()
  migrate_plan(authored,self.p,self.b);self.assertEqual(authored['cards'][0]['text'],'МОЯ ЗАМЕТКА')
 def test_removed_legacy_card_does_not_return_when_regenerated(self):
  old=resolve(self.legacy(),'legacy','confirmed').to_dict();migrate_plan(old,self.p,self.b)
  fresh=self.plan([Line('Masofani nazorat qiladi.',0,20)]);fresh.input_key='stable';fresh.edit_baseline={'cards':[],'inserts':[]}
  preserve_edits(old,fresh);self.assertFalse(fresh.cards);self.assertFalse(fresh.review_items)
 def test_migration_preserves_insert_decisions_and_valid_cache(self):
  old=self.legacy();old.inserts=[Insert(str(self.host),1,3,0,'clip')];old.edit_baseline['inserts']=[asdict(c) for c in old.inserts]
  self.b.events=[EventRequest('source','zarba','play',skipped=True)]
  self.p.whole_episode=True
  combined=combine(self.p,[old]);store_episode(self.p,combined)
  before=copy.deepcopy(self.p.episode_plan['inserts']);migrate_project(self.p)
  self.assertIsNotNone(saved_episode(self.p));self.assertEqual(self.p.episode_plan['inserts'],before);self.assertTrue(self.b.events[0].skipped)
  snapshot=copy.deepcopy(self.p.episode_plan);migrate_project(self.p);self.assertEqual(self.p.episode_plan,snapshot)
 def test_moved_project_opens_without_assets(self):
  self.p.full_video=True;self.p.assets={'disclaimer':'missing.mp4'};self.p.episode_plan=self.legacy().to_dict()
  f=Path(self.tmp.name)/'project.hockeyproj';self.p.save(f);p=Project.load(f);self.assertFalse(p.episode_plan['cards'])

if __name__=='__main__':unittest.main()
