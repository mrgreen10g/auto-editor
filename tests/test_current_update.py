import copy,json,tempfile,threading,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
import numpy as np
from hockey_editor.model import Settings,Project
from hockey_editor.timeline import Plan,Card,Insert
from hockey_editor.music_level import bed_filter
from hockey_editor.insert_limit import apply
from hockey_editor.mobile_inputs import Inputs
from hockey_editor.mini_bridge import Bridge
from hockey_editor import drive_upload as storage
from test_mini_app import app_fixture
from test_folder_import import setup

class MusicAndDensityTests(unittest.TestCase):
 def test_percentage_is_after_normalization(self):
  from hockey_editor.media import ffmpeg
  levels=[]
  for volume in (0,25,50,100):
   filt=bed_filter(Settings(music_volume=volume),4)
   output=subprocess.check_output([ffmpeg(),'-v','error','-f','lavfi','-i','sine=frequency=500:duration=4','-af',filt,'-f','f32le','-ac','1','-ar','48000','-'])
   samples=np.frombuffer(output,dtype='<f4')[48000:96000];levels.append(np.sqrt(np.mean(samples**2)))
  self.assertEqual(levels[0],0)
  self.assertAlmostEqual(levels[2]/levels[1],2,places=4);self.assertAlmostEqual(levels[3]/levels[2],2,places=4)
 def test_legacy_level_and_roundtrip(self):
  self.assertAlmostEqual(Settings(music_db=-28).music_volume,25.118864,places=4)
  from hockey_editor.mobile_settings import apply as setting_apply,validate
  self.assertEqual(setting_apply(Settings(),{'music_volume':0},'ru_hockey').music_volume,0)
  for v in (-1,101,float('nan')):
   with self.assertRaises(ValueError):validate({'music_volume':v})
 def test_entire_episode_limit_never_changes_cards(self):
  p=Plan(0,100,[(0,100)],[],[Insert('a',i*2,i*2+1,0,str(i)) for i in range(40)],[Card(i,i+1,'ФАКТ',str(i)) for i in range(60)],[],100)
  original=copy.deepcopy(p.cards);apply(p,'low');self.assertEqual(len(p.inserts),10);self.assertEqual(p.cards,original)
  self.assertEqual(p.inserts[0].start,0);self.assertEqual(p.inserts[-1].start,78)
  same=copy.deepcopy(p);apply(p,'low');self.assertEqual(p,same)
 def test_normal_keeps_all_insertions(self):
  p=Plan(0,100,[(0,100)],[],[Insert('a',i,i+1,0,str(i)) for i in range(30)],[],[],100)
  apply(p,'normal');self.assertEqual(len(p.inserts),30)

class DraftRecoveryAndPresenterTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.folder=self.root/'release';self.folder.mkdir()
  self.host,self.script=setup(self.folder);self.inputs=Inputs(Bridge(app_fixture(self.root)),self.root/'index.json')
  self.payload=dict(folder=str(self.folder),profile='ru_hockey',host=str(self.host),script=str(self.script),refresh=True)
 def tearDown(self):self.tmp.cleanup()
 def test_missing_metadata_recovers_without_losing_settings(self):
  ident=self.inputs.server_import(self.payload)['id'];d=self.inputs.load(ident);d['settings']={'music_volume':38};self.inputs.save(d)
  (self.folder/'mobile-draft.json').unlink();loaded=self.inputs.load(ident)
  self.assertEqual(loaded['settings']['music_volume'],38);self.assertTrue((self.folder/'mobile-draft.json').exists())
 def test_legacy_missing_metadata_can_reimport(self):
  ident=self.inputs.server_import(self.payload)['id'];(self.folder/'mobile-draft.json').unlink()
  from hockey_editor.draft_store import backup_path
  backup_path(self.inputs,ident).unlink()
  new=self.inputs.server_import(self.payload)['id'];self.assertNotEqual(new,ident)
  self.assertEqual(len(self.inputs.catalog()),1);self.assertEqual(len(self.inputs.load(new)['blocks']),2)
 def test_stale_catalog_id_resolves_to_actual_draft(self):
  ident=self.inputs.server_import(self.payload)['id'];rows=self.inputs.catalog();rows[0]['id']='f'*32;storage.write(self.inputs.index,rows)
  self.assertEqual(self.inputs.load('f'*32)['id'],ident);self.assertEqual([r['id'] for r in self.inputs.catalog()],[ident])
 def test_multiple_parts_and_shared_microphone(self):
  second=self.folder/'second.mp4';second.write_bytes(b'v');mic=self.folder/'mic.mp4';mic.write_bytes(b'm')
  with patch('hockey_editor.media.probe',return_value=dict(video=True,audio=True,duration=30)):
   ident=self.inputs.server_import(dict(self.payload,hosts=[str(second),str(self.host)],microphone=str(mic)))['id']
   d=self.inputs.load(ident);self.assertEqual([r['path'] for r in d['files'] if r['role']=='host' and r['status']=='ready'],[str(second),str(self.host)])
   self.assertEqual([r['block'] for r in d['files'] if r['role']=='mic' and r['status']=='ready'],['*'])
   from hockey_editor.presenter_inputs import update
   microw=next(r for r in d['files'] if r['role']=='mic' and r['status']=='ready');microw['name']='Original microphone.mp4';self.inputs.save(d)
   update(self.inputs,dict(id=ident,hosts=[str(self.host),str(second)],microphone=str(mic)))
   self.assertEqual(self.inputs.summary(self.inputs.load(ident))['microphone'],'Original microphone.mp4')
   self.inputs.server_import(dict(self.payload,hosts=[str(second),str(self.host)],microphone=str(mic)))
   self.assertEqual(self.inputs.summary(self.inputs.load(ident))['microphone'],'Original microphone.mp4')
   update(self.inputs,dict(id=ident,hosts=[str(self.host)],microphone=''))
   d=self.inputs.load(ident);self.assertEqual(self.inputs.summary(d)['hosts'],[self.host.name]);self.assertEqual(self.inputs.summary(d)['microphone'],'')
 def test_invalid_selection_is_transactional(self):
  ident=self.inputs.server_import(self.payload)['id'];before=self.inputs.load(ident)
  from hockey_editor.presenter_inputs import update
  with self.assertRaises(Exception):update(self.inputs,dict(id=ident,hosts=[str(self.root/'missing.mp4')]))
  self.assertEqual(self.inputs.load(ident),before)
 def test_no_artificial_presenter_count_limit(self):
  ident=self.inputs.server_import(self.payload)['id'];d=self.inputs.load(ident)
  for i in range(205):self.inputs.new_file(d,dict(role='host',name=f'{i}.mp4'))
  self.assertGreater(len(d['files']),200)
