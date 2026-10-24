import copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from test_folder_import import setup,SCRIPT
from test_mini_app import app_fixture
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mobile_inputs import Inputs
from hockey_editor.model import Block,MatchSource,Clip,EventRequest
from hockey_editor.timeline import Card,Line,placements
from hockey_editor.combat_scan import illustration_candidates,confident_fight,DETECTOR_VERSION

class HybridTests(unittest.TestCase):
 def test_new_pairs_rescan_original_root_and_preserve_uploads(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);materials=root/'materials';materials.mkdir();host,script=setup(materials)
   first=SCRIPT.replace('САЛАВАТ ЮЛАЕВ — СИБИРЬ\nСибирь играет в гостях. Мой прогноз — победа хозяев в основное время.\n','')
   script.write_text(first)
   inputs=Inputs(Bridge(app_fixture(root)),root/'index.json')
   ident=inputs.server_import(dict(folder=str(materials),host=str(host),script=str(script),profile='ru_hockey'))['id']
   before=inputs.load(ident);uid=before['blocks'][0]['uid']
   upload=root/'upload.mp4';upload.write_bytes(b'uploaded')
   row=inputs.new_file(before,dict(role='host',name=upload.name));row.update(path=str(upload),source='device',status='ready');inputs.save(before)
   result=inputs.script(dict(id=ident,text=SCRIPT,reparse=True));after=inputs.load(ident)
   self.assertEqual(result['added'],1);self.assertEqual(after['blocks'][0]['uid'],uid)
   self.assertEqual(len([r for r in after['files'] if r['role']=='host' and r['status']=='ready']),2)
   self.assertEqual(list(inputs.summary(after)['counts'].values()),[1,1])
   inputs.script(dict(id=ident,text=SCRIPT,reparse=True))
   self.assertEqual(len(inputs.load(ident)['files']),len(after['files']))
 def test_materials_first_script_and_presenter_later_from_other_locations(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);materials=root/'materials';materials.mkdir();host,script=setup(materials)
   inputs=Inputs(Bridge(app_fixture(root)),root/'index.json')
   ident=inputs.server_import(dict(folder=str(materials),profile='ru_hockey'))['id']
   self.assertFalse(inputs.summary(inputs.load(ident))['can_create'])
   inputs.script(dict(id=ident,text=SCRIPT,reparse=True));self.assertEqual(len(inputs.load(ident)['blocks']),2)
   other=root/'late';other.mkdir();late=other/'host.mp4';late.write_bytes(b'late')
   inputs.server_import(dict(id=ident,folder=str(other),host=str(late),profile='ru_hockey',refresh=True))
   d=inputs.load(ident);self.assertEqual(len(d['server_roots']),2)
   self.assertEqual(list(inputs.summary(d)['counts'].values()),[1,1]);self.assertTrue(inputs.summary(d)['can_create'])
   self.assertEqual([r['path'] for r in d['files'] if r['role']=='host'],[str(late.resolve())])
 def test_individual_server_files_mix_with_existing_draft(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/'draft';target.mkdir();inputs=Inputs(Bridge(app_fixture(root)),root/'index.json')
   ident=inputs.create(dict(folder=str(target),profile='ru_hockey',request='hybrid-local-0001'))['id']
   script=root/'late.txt';script.write_text(SCRIPT);inputs.local(dict(id=ident,role='script',path=str(script)))
   host=root/'camera.mp4';host.touch();match=root/'archive.mkv';match.touch()
   with patch('hockey_editor.media.probe',return_value=dict(duration=10,video=True,audio=True)):
    inputs.local(dict(id=ident,role='host',path=str(host)))
    block=inputs.load(ident)['blocks'][0]['uid']
    inputs.local(dict(id=ident,role='match',block=block,path=str(match),home='Амур',away='Спартак'))
   d=inputs.load(ident);self.assertTrue(inputs.summary(d)['can_create']);self.assertEqual(len(d['files']),2)
   self.assertEqual(d['script_source'],str(script.resolve()))
 def test_legacy_root_is_recovered_for_reparse(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);host,script=setup(root);inputs=Inputs(Bridge(app_fixture(root)),root/'index.json')
   ident=inputs.server_import(dict(folder=str(root),host=str(host),script=str(script),profile='ru_hockey'))['id']
   d=inputs.load(ident);d.pop('server_root');d.pop('server_roots');inputs.save(d)
   inputs.script(dict(id=ident,text=SCRIPT,reparse=True));self.assertEqual(inputs.load(ident)['server_root'],str(root.resolve()))

class FightDensityTests(unittest.TestCase):
 def test_isolated_ocr_loss_uses_context_but_not_a_break(self):
  clock=[[t,300-t,.95] for t in range(0,62,2)];clock[8]=[16,None,0]
  self.assertTrue(confident_fight(14,19,clock,[.5]*124,[False]*124))
  self.assertGreaterEqual(len(illustration_candidates(clock,[.5]*124,[False]*124,62)),8)
  for t in (14,16,18):clock[t//2]=[t,None,0]
  self.assertFalse(confident_fight(14,19,clock,[.5]*124,[False]*124))
 def test_many_illustrations_reach_timeline_under_fight_speech(self):
  from hockey_editor.combat import events
  from hockey_editor.goals import propose
  from hockey_editor.timeline import placements
  for lang in ('ru','uz'):
   s=MatchSource('fight.mp4','','',sport='combat',fighter='Petr Yan')
   phrase='Ян контролирует дистанцию и отвечает ударами' if lang=='ru' else 'Yan masofani saqlaydi va zarba beradi'
   rows=[f'{phrase} {i}.' for i in range(12)]
   b=Block(title='Пётр Ян — Мераб Двалишвили' if lang=='ru' else 'Petr Yan — Merab Dvalishvili',sport='combat',language=lang,match_ids=[s.id],script='\n'.join(rows))
   clock=[[t,300-t,.95] for t in range(0,122,2)]
   from dataclasses import asdict
   cs=[asdict(c) for c in illustration_candidates(clock,[.5]*244,[False]*244,122)]
   b.events=propose(events(b,[s]),{s.id:dict(signature='s',fighter=s.fighter,detector_version=DETECTOR_VERSION,candidates=cs)},[s])
   accepted=[e for e in b.events if e.selection and e.selection.accepted];self.assertGreaterEqual(len(accepted),10)
   b.clips=[Clip(f'{i}.mp4',e.phrase,2,'Архив боя',s.path,e.selection.source_start,'play') for i,e in enumerate(accepted)]
   lines=[Line(row,i*10,(i+1)*10) for i,row in enumerate(rows)]
   inserts,_,_=placements(b,lines,{c.path:dict(duration=5) for c in b.clips},120)
   self.assertGreaterEqual(len(inserts),10);self.assertLess(sum(c.end-c.start for c in inserts),75)
 def test_side_cards_are_left_aligned(self):
  from hockey_editor.combat_graphics import card_image
  with tempfile.TemporaryDirectory() as folder:
   for lang in ('ru','uz'):
    x,y=card_image(Card(0,5,'СТАТИСТИКА','12 KO'),Path(folder)/'card.png',lang)
    self.assertEqual((x,y),(28,28))

class TelegramEditingTests(unittest.TestCase):
 def test_add_auto_asset_replace_trim_save_and_undo(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);app=app_fixture(root);bridge=Bridge(app);kit=root/'kit';kit.mkdir()
   a=kit/'telegram.mp4';a.write_bytes(b'video');b=kit/'alternate.mp4';b.write_bytes(b'other');app.project.asset_folder=str(kit)
   with patch('hockey_editor.media.probe',return_value=dict(duration=20,video=True)):
    bridge.editor.apply(dict(op='add-telegram',revision=bridge.revision(),start=1,end=4))
    c=app.plan.cards[-1];self.assertEqual(c.asset,str(a.resolve()));self.assertEqual(c.line,-1)
    i=len(app.plan.cards)-1
    bridge.editor.apply(dict(op='save',id=f'card:{i}',revision=bridge.revision(),start=2,end=6,source_in=3,asset=str(b),text='Telegram',title='ТЕЛЕГРАМ'))
    self.assertEqual(app.plan.cards[-1].asset,str(b.resolve()));self.assertEqual(app.plan.cards[-1].source_in,3)
    bridge.editor.apply(dict(op='undo',revision=bridge.revision()));self.assertEqual(app.plan.cards[-1].asset,str(a.resolve()))
    bridge.editor.apply(dict(op='undo',revision=bridge.revision()));self.assertEqual(len(app.plan.cards),1)
 def test_bad_asset_does_not_modify_plan(self):
  from hockey_editor.mini_server import RemoteError
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);app=app_fixture(root);bridge=Bridge(app);asset=root/'tg.mp4';asset.touch();app.project.assets['telegram']=str(asset)
   before=app.plan.to_dict()
   with patch('hockey_editor.media.probe',return_value=dict(duration=1,video=True)):
    with self.assertRaises(RemoteError):bridge.editor.apply(dict(op='add-telegram',revision=bridge.revision(),start=1,end=5))
   self.assertEqual(app.plan.to_dict(),before)
