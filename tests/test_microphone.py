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
            root=Path(tmp).resolve();cam=root/'cam.mp4';mic=root/'mic.mov';cam.touch();mic.touch()
            p=Project(host=str(cam),microphones={str(cam):str(mic)})
            p.save(root/'project.hockeyproj');q=Project.load(root/'project.hockeyproj')
            self.assertEqual(q.microphones,p.microphones)
            with patch('hockey_editor.host_media.probe',return_value=dict(video=True,audio=True,duration=30)),patch('hockey_editor.microphone.prepare',return_value='synced.mp4') as sync:
                result=analysis_source(q,root,threading.Event(),lambda _:None)
                self.assertEqual(result[0],'synced.mp4');sync.assert_called_once()
                q.microphones={};sync.reset_mock()
                self.assertEqual(analysis_source(q,root,threading.Event(),lambda _:None)[0],str(cam));sync.assert_not_called()
    def test_encoded_video_keeps_audio_delay(self):
        from hockey_editor.microphone import prepare,envelope
        from hockey_editor.media import run
        from scipy.io import wavfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rate=8000;rng=np.random.default_rng(12)
            env=np.repeat(rng.uniform(.05,.7,600),800)
            voice=(rng.normal(size=len(env))*env*10000).astype(np.int16)
            wavfile.write(root/'camera.wav',rate,voice)
            wavfile.write(root/'mic.wav',rate,voice[rate*3:])
            cam=root/'camera.mp4'
            run(['-y','-f','lavfi','-i','color=c=blue:s=160x90:r=10','-i',root/'camera.wav','-map','0:v','-map','1:a','-c:v','libx264','-preset','ultrafast','-c:a','aac','-shortest',cam])
            cancel=threading.Event();target=prepare(str(cam),str(root/'mic.wav'),root/'cache',cancel,lambda _:None)
            work=root/'verify';work.mkdir()
            result=measure(envelope(cam,work,cancel),envelope(target,work,cancel))
            self.assertAlmostEqual(result['offset'],0,delta=.04)
            self.assertAlmostEqual(result['rate'],1,delta=.0005)
