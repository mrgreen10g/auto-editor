import unittest,tempfile,threading
from pathlib import Path
import numpy as np
from unittest.mock import patch
from hockey_editor.microphone import measure
from hockey_editor.model import Project
from hockey_editor.host_media import analysis_source

class MicrophoneTests(unittest.TestCase):
    def test_offset_and_drift(self):
        rng=np.random.default_rng(42);a=rng.normal(size=24000)
        rate=1.0003;offset=-2.31
        b=np.interp((np.arange(23500)/100-offset)/rate*100,np.arange(len(a)),a)
        result=measure(a,b)
        self.assertAlmostEqual(result['offset'],offset,delta=.03)
        self.assertAlmostEqual(result['rate'],rate,delta=.0001)
    def test_unrelated_recording_rejected(self):
        rng=np.random.default_rng(5)
        with self.assertRaises(ValueError):measure(rng.normal(size=20000),rng.normal(size=20000))
    def test_optional_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cam=root/'cam.mp4';mic=root/'mic.mov';cam.touch();mic.touch()
            p=Project(host=str(cam),microphones={str(cam):str(mic)})
            p.save(root/'project.hockeyproj');q=Project.load(root/'project.hockeyproj')
            self.assertEqual(q.microphones,p.microphones)
            with patch('hockey_editor.host_media.probe',return_value=dict(video=True,audio=True,duration=30)),patch('hockey_editor.microphone.prepare',return_value='synced.mp4') as sync:
                result=analysis_source(q,root,threading.Event(),lambda _:None)
                self.assertEqual(result[0],'synced.mp4');sync.assert_called_once()
                q.microphones={};sync.reset_mock()
                self.assertEqual(analysis_source(q,root,threading.Event(),lambda _:None)[0],str(cam));sync.assert_not_called()
