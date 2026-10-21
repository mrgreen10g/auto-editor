import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from test_mini_app import app_fixture
from test_folder_import import setup,SCRIPT
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mobile_inputs import Inputs
from hockey_editor.mobile_reparse import refresh_script
from hockey_editor.mini_server import RemoteError

class ReparseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.folder=self.root/'release';self.folder.mkdir();self.host,self.script=setup(self.folder)
  self.app=app_fixture(self.root);self.bridge=Bridge(self.app);self.inputs=Inputs(self.bridge,self.root/'catalog.json')
  self.payload=dict(folder=str(self.folder),host=str(self.host),script=str(self.script),profile='ru_hockey');self.ident=self.inputs.server_import(self.payload)['id']
 def tearDown(self):self.tmp.cleanup()
 def test_import_refresh_really_reads_new_file_and_keeps_sources(self):
  before=self.inputs.load(self.ident);self.script.write_text(SCRIPT.replace('Амур играет дома.','Амур играет дома. Новый факт.'),encoding='utf-8')
  result=self.inputs.server_import(dict(self.payload,refresh=True));after=self.inputs.load(self.ident)
  self.assertEqual(result['id'],self.ident);self.assertIn('Новый факт',after['blocks'][0]['script'])
  self.assertEqual([b['uid'] for b in before['blocks']],[b['uid'] for b in after['blocks']])
  self.assertEqual(len([f for f in after['files'] if f['status']=='ready']),3)
 def test_explicit_text_reparse_keeps_matches_and_failed_parse_is_atomic(self):
  before=self.inputs.load(self.ident)
  result=refresh_script(self.inputs,dict(id=self.ident,reparse=True,text=SCRIPT+'\nНовая концовка.'))
  self.assertEqual(result['count'],2);after=self.inputs.load(self.ident)
  self.assertEqual([f['path'] for f in before['files']],[f['path'] for f in after['files']])
  with self.assertRaises(RemoteError):refresh_script(self.inputs,dict(id=self.ident,reparse=True,text=''))
  self.assertEqual(after,self.inputs.load(self.ident))
 def test_removed_pair_media_can_be_reused(self):
  text=SCRIPT.replace('САЛАВАТ ЮЛАЕВ — СИБИРЬ\nСибирь играет в гостях. Мой прогноз — победа хозяев в основное время.\n','')
  refresh_script(self.inputs,dict(id=self.ident,reparse=True,text=text));draft=self.inputs.load(self.ident)
  self.assertEqual(len(draft['blocks']),1);old=next(f for f in draft['files'] if f.get('unassigned'))
  self.assertTrue(Path(old['path']).is_file());self.inputs.reuse(dict(id=self.ident,from_draft=self.ident,file=old['id'],block=draft['blocks'][0]['uid']))
  self.assertEqual(self.inputs.summary(self.inputs.load(self.ident))['counts'][draft['blocks'][0]['uid']],2)
 def test_reread_and_created_project_preserved(self):
  self.app.restore_plan=Mock();self.app.status.set=Mock()
  old=Path(self.inputs.activate(dict(id=self.ident,revision=self.bridge.revision()))['project']);previous=old.read_bytes()
  self.script.write_text(SCRIPT.replace('Амур играет дома.','Амур играет дома. Исправлено.'),encoding='utf-8')
  result=refresh_script(self.inputs,dict(id=self.ident,reparse=True),from_file=True)
  self.assertEqual(result['previous_project'],str(old));self.assertEqual(old.read_bytes(),previous)
  new=Path(self.inputs.activate(dict(id=self.ident,revision=self.bridge.revision()))['project'])
  self.assertNotEqual(old,new);self.assertTrue(old.exists());self.assertIn('Исправлено.',self.app.project.blocks[0].script)
