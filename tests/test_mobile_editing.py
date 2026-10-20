import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from test_mini_app import app_fixture
from test_folder_import import setup,SCRIPT
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mobile_inputs import Inputs
from hockey_editor.mobile_scripts import doc_id,local_script,fetch_document
from hockey_editor.mobile_editing import cut_range
from hockey_editor.timeline import Plan,Card,Insert,Line
from hockey_editor.mini_server import RemoteError

class MobileEditingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.app=app_fixture(self.root);self.bridge=Bridge(self.app)
 def tearDown(self):self.tmp.cleanup()
 def act(self,**data):return self.bridge.editor.apply(dict(revision=self.bridge.revision(),**data))
 def test_card_type_edit_persists_and_undo_redo_survive_bridge_restart(self):
  self.act(op='save',id='card:0',start='00:01.20',end='00:03.50',title='ВОПРОС ЗРИТЕЛЮ',text='Кто победит?',owner='')
  self.assertEqual(self.app.plan.cards[0].title,'ВОПРОС ЗРИТЕЛЮ');self.assertEqual(self.app.plan.cards[0].start,1.2)
  self.bridge=Bridge(self.app);self.assertTrue(self.bridge.editor.state()['undo'])
  self.act(op='undo');self.assertEqual(self.app.plan.cards[0].text,'Три гола')
  self.act(op='redo');self.assertEqual(self.app.plan.cards[0].text,'Кто победит?')
 def test_cut_shifts_media_overlay_sources_and_review(self):
  self.app.plan.media=[dict(path=self.app.project.host,start=10,end=18)]
  self.app.plan.inserts=[Insert(self.app.project.host,1,7,0,'Игра',source_max=8)]
  p=cut_range(self.app.plan,2,4)
  self.assertEqual(p.duration,6);self.assertEqual(p.keep,[(0,2),(4,8)])
  self.assertEqual([(m['start'],m['end']) for m in p.media],[(10,12),(14,18)])
  self.assertEqual([(i.start,i.end,i.source_in) for i in p.inserts],[(1,2,0),(2,5,3)])
  self.assertEqual((p.cards[0].start,p.cards[0].end),(1,2));self.assertEqual(p.review_items[0]['end'],2)
 def test_cut_updates_section_keep_and_line_count(self):
  p=self.app.plan;p.sections=[dict(start=0,end=8,block_id=self.app.project.blocks[0].uid,title='Матч',keep=[(0,8)],line_start=0,line_count=1,source_start=0,source_end=8)]
  result=cut_range(p,2,3)
  self.assertEqual(result.sections[0]['keep'],[(0,2),(3,8)]);self.assertEqual(result.sections[0]['line_count'],1)
  with self.assertRaises(RemoteError):cut_range(p,0,8)
 def test_reject_stale_revision_and_invalid_edit_without_changing_project(self):
  revision=self.bridge.revision();self.act(op='delete',id='card:0')
  with self.assertRaises(RemoteError):self.bridge.editor.apply(dict(revision=revision,op='undo'))
  self.act(op='undo');before=self.app.plan.to_dict()
  with self.assertRaises(ValueError):self.act(op='save',id='card:0',start=7,end=10,title='СТАТИСТИКА',text='Bad')
  self.assertEqual(self.app.plan.to_dict(),before)
 def test_create_uses_selected_folder_without_nested_name(self):
  folder=self.root/'Выбранная';folder.mkdir();inputs=Inputs(self.bridge,self.root/'catalog.json')
  result=inputs.create(dict(folder=str(folder),profile='ru_hockey',request='request-0001'))
  self.assertEqual(inputs.load(result['id'])['folder'],str(folder.resolve()));self.assertTrue((folder/'Ведущий').is_dir())
  self.assertEqual(inputs.create(dict(folder=str(folder),profile='ru_hockey',request='request-0002')),result)
 def test_server_script_repair_before_parse_and_conflict(self):
  folder=self.root/'materials';folder.mkdir();host,script=setup(folder);script.write_text('Ошибка определения пары',encoding='utf8');inputs=Inputs(self.bridge,self.root/'catalog.json')
  payload=dict(folder=str(folder),profile='ru_hockey',script=str(script));read=local_script(inputs,payload)
  local_script(inputs,dict(payload,version=read['version'],text=SCRIPT),True)
  self.assertEqual(script.read_text(encoding='utf8'),SCRIPT);self.assertTrue(list((folder/'История сценария').iterdir()))
  with self.assertRaises(RemoteError):local_script(inputs,dict(payload,version=read['version'],text='stale'),True)
  self.assertTrue(inputs.server_import(dict(payload,host=str(host)))['id'])
 def test_same_download_reused_for_another_block(self):
  inputs=Inputs(self.bridge,self.root/'catalog.json');folder=self.root/'new';folder.mkdir();ident=inputs.create(dict(folder=str(folder),profile='ru_hockey',request='request-0001'))['id'];inputs.script(dict(id=ident,text=SCRIPT));d=inputs.load(ident)
  row=inputs.new_file(d,dict(role='match',block=d['blocks'][0]['uid'],home='Амур',away='Спартак'));row.update(status='ready',path=self.app.project.host,url='https://www.youtube.com/watch?v=abcdefghijk',source='youtube');inputs.save(d)
  with patch.object(inputs,'launch') as launch:inputs.link(dict(id=ident,role='match',block=d['blocks'][1]['uid'],url=row['url']));launch.assert_not_called()
  files=inputs.load(ident)['files'];self.assertEqual(len(files),2);self.assertEqual(files[0]['path'],files[1]['path'])
 def test_google_doc_only_and_text_export(self):
  self.assertEqual(doc_id('https://docs.google.com/document/d/abcdefghijk/edit?usp=sharing'),'abcdefghijk')
  for u in ['https://evil.test/document/d/abcdefghijk','https://docs.google.com.evil.test/document/d/abcdefghijk','file:///document/d/abcdefghijk']:
   with self.assertRaises(RemoteError):doc_id(u)
  response=Mock(status_code=200);response.iter_content.return_value=[SCRIPT.encode()];response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);client=Mock();client.get.return_value=response
  with patch('hockey_editor.mobile_scripts.drive.session',return_value=(client,None)),patch('hockey_editor.mobile_scripts.drive.check'):
   self.assertEqual(fetch_document('abcdefghijk'),SCRIPT)
  self.assertEqual(client.get.call_args.kwargs['params'],{'mimeType':'text/plain'});client.close.assert_called_once()
 def test_project_script_change_invalidates_plan_and_undo_restores_it(self):
  rows=self.bridge.editor.state()['blocks'];rows[1]['script']='Исправленный текст сценария.'
  self.act(op='project',blocks=rows)
  self.assertIsNone(self.app.plan);self.assertEqual(self.app.project.blocks[0].script,'Исправленный текст сценария.')
  self.act(op='undo');self.assertIsNotNone(self.app.plan)

 def test_whole_episode_cut_across_sections_survives_save_reload(self):
  from hockey_editor.model import Project,Block
  from hockey_editor.episode import combine,store_episode,saved_episode
  p=Project(host=self.app.project.host,blocks=[Block(title='A',script='One'),Block(title='B',script='Two')],whole_episode=True)
  a=Plan(0,5,[(0,5)],[Line('one',0,5)],[],[Card(1,4,'СТАТИСТИКА','one')],[],5)
  b=Plan(5,10,[(0,5)],[Line('two',0,5)],[],[Card(1,4,'СТАТИСТИКА','two')],[],5)
  store_episode(p,cut_range(combine(p,[a,b]),4,6));path=self.root/'episode.hockeyproj';p.save(path);q=Project.load(path)
  self.assertEqual(saved_episode(q).duration,8);self.assertEqual([x.edit_plan['duration'] for x in q.blocks],[4,4])
 def test_history_root_survives_pair_rename_and_changing_cache(self):
  self.app.cache_path=lambda:self.root/self.app.project.blocks[0].title
  old=self.bridge.editor.root();rows=self.bridge.editor.state()['blocks'];rows[1]['title']='Другая пара'
  self.act(op='project',blocks=rows);self.bridge=Bridge(self.app)
  self.assertEqual(self.bridge.editor.root(),old);self.assertTrue(self.bridge.editor.state()['undo']);self.act(op='undo')
  self.assertEqual(self.app.project.blocks[0].title,'СКА — Лада')
