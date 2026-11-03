import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_mini_app import app_fixture
from test_folder_import import setup
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mobile_inputs import Inputs
from hockey_editor.folder_import import microphone_files

class MicrophoneImportTests(unittest.TestCase):
 def test_import_replace_and_camera(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);folder=root/'release';folder.mkdir();host,script=setup(folder)
   mic=folder/'microphone.mkv';mic.write_bytes(b'audio')
   inputs=Inputs(Bridge(app_fixture(root)),root/'catalog.json')
   payload=dict(folder=str(folder),host=str(host),script=str(script),profile='ru_hockey',refresh=True)
   self.assertIn(mic.resolve(),[Path(p).resolve() for p in inputs.server_files(payload)['microphones']])
   self.assertNotIn(host.resolve(),microphone_files(folder,host))
   with patch('hockey_editor.media.probe',return_value={'audio':True,'duration':10}):
    result=inputs.server_import(dict(payload,microphone=str(mic)))
    d=inputs.load(result['id']);camera=next(r for r in d['files'] if r['role']=='host')
    self.assertEqual([r['block'] for r in d['files'] if r['role']=='mic' and r['status']=='ready'],[camera['id']])
    inputs.server_import(dict(payload,microphone=str(mic)))
    d=inputs.load(result['id']);self.assertEqual(sum(r['role']=='mic' and r['status']=='ready' for r in d['files']),1)
   inputs.server_import(dict(payload,microphone=''));d=inputs.load(result['id'])
   self.assertFalse(any(r['role']=='mic' and r['status']=='ready' for r in d['files']))
   with self.assertRaises(ValueError):inputs.server_import(dict(payload,microphone=str(host)))
   with self.assertRaises(ValueError):inputs.server_import(dict(payload,microphone=str(root/'other.mp4')))
