import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_mini_app import app_fixture
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_server import RemoteError
from hockey_editor.mini_framing import handle

class MobileFramingTests(unittest.TestCase):
 def test_async_preview_save_and_stale_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);app=app_fixture(root);bridge=Bridge(app);app.project.profile='ru_combat_shorts'
   image=root/'face.jpg';Image.new('RGB',(640,360),'gray').save(image)
   value=dict(x=.4,y=.5,zoom=1.,signature='test',rotation=0,face_found=True)
   with patch('hockey_editor.shorts_framing.pending',return_value=[app.project.host]),patch('hockey_editor.shorts_framing.dimensions',return_value=(1920,1080)),patch('hockey_editor.orientation.detect_rotation',return_value=0),patch('hockey_editor.shorts_framing.detect',return_value=(value,image)):
    first=handle(bridge,'portrait-start',{'revision':bridge.revision()})
    for _ in range(200):
     state=handle(bridge,'portrait-status',first)
     if state['status']!='running':break
     time.sleep(.01)
    self.assertEqual(state['status'],'ready')
    self.assertNotIn('path',state['items'][0])
    self.assertTrue(state['items'][0]['image'].startswith('data:image/jpeg;base64,'))
    handle(bridge,'portrait-save',{**first,'values':[dict(x=.6,y=.5,zoom=1.2)]})
    self.assertTrue(app.project.host_framing[app.project.host]['approved'])
    self.assertEqual(app.project.host_framing[app.project.host]['x'],.6)
    self.assertTrue(app.project_path.exists())
    with self.assertRaises(RemoteError):handle(bridge,'portrait-save',{**first,'values':[value]})
 def test_long_video_has_no_prompt(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=app_fixture(Path(tmp));bridge=Bridge(app)
   self.assertEqual(handle(bridge,'portrait-start',{'revision':bridge.revision()}),dict(ready=True,items=[]))
