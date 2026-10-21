import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_mini_app import app_fixture
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_live import key,scene,artwork,prepare
from hockey_editor.mini_server import RemoteError
from hockey_editor.timeline import Card,Insert,Plan
from hockey_editor.graphics import card_image

class LivePreviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.app=app_fixture(self.root);self.bridge=Bridge(self.app)
 def tearDown(self):self.tmp.cleanup()
 def data(self,**kw):return dict(revision=self.bridge.revision(),**kw)
 def test_bed_reused_after_text_logo_geometry_timing_changes(self):
  p=self.app.project;plan=self.app.plan;before=key(p,plan)
  plan.cards[0].text='Новый текст';plan.cards[0].start=2;plan.cards[0].scale=.5;plan.cards[0].offset_x=30
  p.team_logos={'СКА':str(self.root/'logo.png')};p.settings.animate_cards=not p.settings.animate_cards
  self.assertEqual(key(p,plan),before)
  plan.cards.append(Card(4,6,'СТАТИСТИКА','Добавлено'));self.assertEqual(key(p,plan),before)
  plan.inserts.append(Insert(p.host,4,6,0,'Игра'));self.assertNotEqual(key(p,plan),before)
 def test_bed_invalidates_source_settings_and_assets(self):
  for change in [lambda p,v:setattr(p.settings,'mirror_host',not p.settings.mirror_host),lambda p,v:v.cards.append(Card(2,4,'ТГ','',asset=p.host)),lambda p,v:setattr(v,'keep',[(0,7)])]:
   p=copy.deepcopy(self.app.project);v=copy.deepcopy(self.app.plan);before=key(p,v);change(p,v);self.assertNotEqual(before,key(p,v))
  before=key(self.app.project,self.app.plan);Path(self.app.project.host).write_bytes(b'new-source');self.assertNotEqual(before,key(self.app.project,self.app.plan))
 def test_artwork_draft_does_not_mutate_and_geometry_matches_export(self):
  c=self.app.plan.cards[0];original=c.text
  a=artwork(self.bridge,self.data(id='card:0',text='Черновик'))
  self.assertTrue(a['image']);self.assertEqual(c.text,original)
  plain=self.root/'plain.png';changed=self.root/'changed.png'
  x,y=card_image(c,plain);c.offset_x=23;c.offset_y=-17;c.scale=.5
  xx,yy=card_image(c,changed);self.assertEqual((xx,yy),(x+23,y-17))
  with Image.open(plain) as im,Image.open(changed) as other:self.assertEqual(other.size,(round(im.width*.5),round(im.height*.5)))
 def test_geometry_save_reload_and_undo(self):
  self.bridge.editor.apply(self.data(op='save',id='card:0',start=1,end=4,text='Три гола',title='СТАТИСТИКА',offset_x=80,offset_y=-40,scale=.8))
  self.assertEqual(self.app.plan.cards[0].scale,.8)
  self.assertEqual(Plan.from_dict(self.app.plan.to_dict()).cards[0].offset_x,80)
  self.bridge.editor.apply(self.data(op='undo'));self.assertEqual(self.app.plan.cards[0].scale,1)
  before=self.app.plan.to_dict()
  with self.assertRaises(RemoteError):self.bridge.editor.apply(self.data(op='save',id='card:0',start=1,end=4,text='Три гола',scale=float('nan')))
  self.assertEqual(before,self.app.plan.to_dict())
 def test_scene_and_preparation_leave_asset_cards_in_bed(self):
  self.app.plan.cards.append(Card(4,6,'ТГ','',asset=self.app.project.host))
  state=scene(self.bridge,self.data());self.assertEqual(len(state['cards']),1)
  spec,digest=prepare(self.bridge,self.data());self.assertEqual(len(spec['plan'].cards),1);self.assertTrue(spec['plan'].cards[0].asset)
  self.assertEqual(digest,state['key']);self.assertEqual(len(self.app.plan.cards),2)
 def test_live_job_survives_card_revision_but_not_video_change(self):
  import time
  file=self.root/'bed.mp4';file.write_bytes(b'video')
  self.bridge.jobs['test']=dict(status='ready',live=True,key=key(self.app.project,self.app.plan),revision=self.bridge.revision(),created=time.time(),file=str(file))
  self.app.plan.cards[0].text='Правка';self.assertEqual(self.bridge.handle('preview-stream',dict(job='test'))['file'],str(file))
  self.app.project.settings.mirror_host=True
  with self.assertRaises(RemoteError):self.bridge.handle('preview-stream',dict(job='test'))
 def test_cached_bed_does_not_call_renderer(self):
  from hockey_editor.mini_preview import render
  spec,digest=prepare(self.bridge,self.data());(self.root/(digest+'.mp4')).write_bytes(b'cached')
  with patch('hockey_editor.engine.Engine.render') as renderer:
   result=render(spec,self.root,'unused');renderer.assert_not_called();self.assertEqual(result['duration'],8)
 def test_stale_artwork_revision_rejected(self):
  d=self.data(id='card:0');self.app.plan.cards[0].text='Изменено'
  with self.assertRaises(RemoteError):artwork(self.bridge,d)
