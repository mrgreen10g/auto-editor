"""Regression for real FFmpeg frame-rate conversion, animated overlays and denoise."""
import unittest,tempfile,threading,re
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from hockey_editor.media import run,probe
from hockey_editor.model import Project,Block
from hockey_editor.timeline import Plan,Line,Insert,Card
from hockey_editor.engine import Engine

class MediaTests(unittest.TestCase):
    def test_denoise_reduces_stationary_background(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);sr=48000;t=np.arange(sr*4)/sr;rng=np.random.default_rng(8)
            signal=rng.normal(0,.004,len(t));signal[(t>1)&(t<3)]+=.1*np.sin(2*np.pi*230*t[(t>1)&(t<3)])
            wavfile.write(d/'input.wav',sr,(signal*32767).astype('int16'))
            run(['-y','-i',d/'input.wav','-af','highpass=f=70,afftdn=nr=10:nf=-40:tn=1','-c:a','pcm_s16le',d/'clean.wav'])
            _,clean=wavfile.read(d/'clean.wav');_,raw=wavfile.read(d/'input.wav')
            before=np.sqrt(np.mean(raw[int(sr*3.5):].astype(float)**2));after=np.sqrt(np.mean(clean[int(sr*3.5):].astype(float)**2))
            self.assertLess(after,before*.85)
    def test_export_retains_video_audio_duration_with_25fps_source(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=25:d=14','-f','lavfi','-i','sine=f=220:r=48000:d=14','-t','14','-c:v','libx264','-c:a','aac',d/'host.mp4'])
            run(['-y','-f','lavfi','-i','color=c=red:s=320x180:r=25:d=3','-c:v','libx264',d/'clip.mp4'])
            p=Project(host=str(d/'host.mp4'),blocks=[Block(title='Проверка',script='Достаточно длинная строка сценария для проверки.')])
            plan=Plan(0,14,[(0,14)],[Line('Проверка',0,14)],[Insert(str(d/'clip.mp4'),2,4,.4,'Гол')],[Card(6,11,'СТАТИСТИКА','Броски: 36 — 32')],[],14)
            e=Engine(p,0,d/'cache',threading.Event());e.render(plan,d/'result.mp4')
            self.assertTrue((d/'result.srt').is_file());self.assertTrue((d/'result.timing.json').is_file())
            for selector in ('-an','-vn'):
                log=run(['-i',d/'result.mp4',selector,'-progress','pipe:2','-f','null','-'])
                times=re.findall(r'out_time_us=(\d+)',log)
                self.assertTrue(times)
                self.assertAlmostEqual(int(times[-1])/1e6,14,delta=.06)
            with self.assertRaises(ValueError):e.render(plan,d/'result.mp4')

if __name__=='__main__':unittest.main()
