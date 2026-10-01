"""Real FFmpeg comparison across chunk boundaries and cancellation."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import numpy as np
from hockey_editor.media import run, Cancelled
from hockey_editor.scan_cache import hockey_frames
from hockey_editor.model import MatchSource


class ScanDecodeTests(unittest.TestCase):
    def test_one_decode_preserves_sampling_grid_and_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.mp4';cancel=threading.Event()
            run(['-y','-f','lavfi','-i','testsrc2=s=320x180:r=25:d=10.2','-c:v','libx264','-threads','2',source])
            old_score=root/'old-score';old_visual=root/'old-visual'
            old_score.mkdir();old_visual.mkdir()
            run(['-y','-i',source,'-an','-vf','fps=1/2,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2','-q:v','3','-start_number','0',old_score/'%06d.jpg'])
            run(['-y','-i',source,'-an','-vf','fps=2,scale=320:180','-q:v','3','-start_number','0',old_visual/'%06d.jpg'])
            folder=root/'cache';folder.mkdir();calls=[]
            def interrupted(args,*a,**k):
                calls.append(args)
                if len(calls)==2:raise Cancelled('stop second chunk')
                return run(args,*a,**k)
            match=MatchSource(str(source),'A','B')
            with patch('hockey_editor.scan_cache.CHUNK_SECONDS',4),patch('hockey_editor.scan_cache.run',side_effect=interrupted):
                with self.assertRaises(Cancelled):
                    hockey_frames(match,folder,10.2,cancel,lambda _:None)
            calls=[]
            def resumed(args,*a,**k):calls.append(args);return run(args,*a,**k)
            with patch('hockey_editor.scan_cache.CHUNK_SECONDS',4),patch('hockey_editor.scan_cache.run',side_effect=resumed):
                score,visual=hockey_frames(match,folder,10.2,cancel,lambda _:None)
            self.assertEqual(len(calls),2)
            for old,new in [(sorted(old_score.glob('*.jpg')),score),(sorted(old_visual.glob('*.jpg')),visual)]:
                self.assertEqual(len(old),len(new))
                for i,(a,b) in enumerate(zip(old,new)):
                    with Image.open(a) as x,Image.open(b) as y:
                        error=np.abs(np.asarray(x,dtype=float)-np.asarray(y,dtype=float)).mean()
                    self.assertLess(error,.1,f'frame {i} moved: {error}')
