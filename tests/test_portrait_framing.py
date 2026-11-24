import copy,threading,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from hockey_editor import shorts_framing as framing
from hockey_editor.model import Project,Block,Settings,Clip
from hockey_editor.timeline import Plan,Line,Insert,Card,placements
from hockey_editor.insert_limit import apply
from hockey_editor.goals import montage_block
from hockey_editor.live_cards import base_key

class FramingTests(unittest.TestCase):
 def test_crop_fills_without_stretch_and_clamps(self):
  for x,y,z in [(0,0,1),(1,1,2),(.52,.5,1.2)]:
   a,b,w,h=framing.rectangle(1920,1080,dict(x=x,y=y,zoom=z))
   self.assertGreaterEqual(a,0);self.assertGreaterEqual(b,0)
   self.assertLessEqual(a+w,1920);self.assertLessEqual(b+h,1080)
   self.assertLess(abs(w/h-9/16),.005)
   self.assertTrue(all(n%2==0 for n in (a,b,w,h)))
 def test_vertical_movement_with_zoom(self):
  a=framing.rectangle(1920,1080,dict(x=.5,y=.2,zoom=1.4))
  b=framing.rectangle(1920,1080,dict(x=.5,y=.8,zoom=1.4))
  self.assertLess(a[1],b[1])
 def test_reject_invalid(self):
  for value in [dict(x=float('nan')),dict(y=-1),dict(zoom=0),dict(zoom=3)]:
   with self.assertRaises(ValueError):framing.validate(value)
 def test_preview_size_and_mirror(self):
  im=Image.new('RGB',(640,360),'red')
  im.paste('blue',(320,0,640,360))
  out=framing.preview(im,dict(x=.5,y=.5,zoom=1))
  mirrored=framing.preview(im,dict(x=.5,y=.5,zoom=1),True)
  self.assertEqual(out.size,(288,512));self.assertEqual(out.getpixel((0,0)),mirrored.getpixel((287,0)))
 def test_portable_project_and_preview_cache(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);host=root/'camera.mp4';host.touch()
   p=Project(host=str(host),profile='ru_combat_shorts');p.host_framing[str(host)]={'x':.2,'y':.6,'zoom':1.3,'approved':True}
   target=root/'episode.hockeyproj';p.save(target);loaded=Project.load(target)
   self.assertEqual(loaded.host_framing,p.host_framing)
   plan=Plan(0,4,[(0,4)],[],[],[],[],4);first=base_key(plan,p)
   p.host_framing[str(host)]['x']=.7
   self.assertNotEqual(first,base_key(plan,p))
 def test_landscape_only_and_original_microphone_mapping(self):
  p=Project(profile='ru_combat_shorts')
  with patch('hockey_editor.shorts_framing.dimensions',return_value=(1920,1080)),patch('hockey_editor.shorts_framing.entry',return_value=dict(x=.3,y=.5,zoom=1)) as entry:
   self.assertTrue(framing.filter_for(p,'prepared.mp4',0,'.',original='camera.mov').startswith('crop='))
   self.assertEqual(entry.call_args.args[1],'camera.mov')
  with patch('hockey_editor.shorts_framing.dimensions',return_value=(1080,1920)):
   self.assertEqual(framing.filter_for(p,'camera.mov',0,'.'),'')
  p.profile='ru_combat';self.assertEqual(framing.filter_for(p,'missing.mov',0,'.'),'')
 def test_disabled_inserts_preserve_cards_and_skip_media(self):
  block=Block(title='А — Б',script='Боец одержал восемнадцать побед.',clips=[Clip('missing.mp4','Боец')])
  p=Project(blocks=[block]);p.settings.insert_frequency='none';p.settings.use_manual_clips=True
  clean=montage_block(p,0,'.',threading.Event());self.assertEqual(clean.clips,[])
  ins,cards,_=placements(block,[Line(block.script,0,5)],{},5,'none')
  self.assertEqual(ins,[]);self.assertTrue(cards)
  plan=Plan(0,5,[(0,5)],[],[Insert('missing',1,4,0,'test')],cards,[],5)
  before=copy.deepcopy(cards);apply(plan,'none')
  self.assertEqual(plan.cards,before);self.assertEqual(plan.inserts,[])
 def test_mobile_accepts_none(self):
  from hockey_editor.mobile_settings import validate
  self.assertEqual(validate({'insert_frequency':'none'}),{'insert_frequency':'none'})
