"""Camera display matrices must not rotate already oriented frames a second time."""
import shutil,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from hockey_editor.media import run,probe,normalize_encoded_orientation
from hockey_editor.engine import Engine
from hockey_editor.model import Project,Block,Settings
from hockey_editor.timeline import Plan,Line

class DisplayOrientationTests(unittest.TestCase):
    def make_video(self,d):
        upright=d/'upright.mp4'
        run(['-y','-f','lavfi','-i','color=c=blue:s=180x320:r=30:d=2',
             '-f','lavfi','-i','sine=f=220:r=48000:d=2','-vf',
             'drawbox=x=0:y=0:w=180:h=100:color=red:t=fill','-t',2,'-c:v','libx264','-c:a','aac',upright])
        return upright

    def assert_portrait(self,path,d):
        info=probe(path)
        self.assertEqual((info['width'],info['height']),(360,640))
        self.assertEqual(info['sample_aspect_ratio'],[1,1]);self.assertEqual(info['rotation'],0)
        self.assertTrue(info['audio']);self.assertAlmostEqual(info['duration'],2,delta=.08)
        image=d/(path.stem+'.png');run(['-y','-ss',.5,'-i',path,'-frames:v',1,image])
        with Image.open(image) as im:
            self.assertGreater(im.getpixel((180,50))[0],200)
            self.assertGreater(im.getpixel((180,400))[2],200)

    def test_camera_rotation_is_applied_once(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);upright=self.make_video(d)
            run(['-y','-i',upright,'-vf','transpose=clock','-c:v','libx264','-c:a','copy',d/'landscape.mp4'])
            run(['-y','-display_rotation:v:0',90,'-i',d/'landscape.mp4','-c','copy',d/'camera.mp4'])
            self.assertEqual(probe(d/'camera.mp4')['rotation'],90)
            p=Project(host=str(d/'camera.mp4'),profile='uz_football_shorts',blocks=[Block(language='uz',script='Tanlovim — Angliya X2 va total 1,5 dan ko‘p.')],settings=Settings(width=720,height=1280,auto_rotate=False,color=False,zoom=False))
            # Exercise both base render paths, including multi-part/full episode.
            for multi in (False,True):
                plan=Plan(0,2,[(0,2)],[Line('Test',0,2)],[],[],[],2,0)
                if multi:plan.media=[dict(path=p.host,start=0,end=2,rotation=0,kind='host')]
                target=d/f'output-{multi}.mp4'
                Engine(p,0,d/f'cache-{multi}',threading.Event()).render(plan,target,draft=True)
                self.assert_portrait(target,d)
                self.assertEqual(probe(d/f'cache-{multi}'/'host-prepared.mp4')['rotation'],0)
            self.assertEqual(probe(d/'camera.mp4')['rotation'],90)  # Original untouched.

    def test_old_cached_portrait_matrix_is_removed_without_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);upright=self.make_video(d)
            run(['-y','-display_rotation:v:0',90,'-i',upright,'-c','copy',d/'old-base.mp4'])
            p=Project(host=str(upright),profile='uz_football_shorts',blocks=[Block(language='uz',script='Tanlovim — Angliya X2 va total 1,5 dan ko‘p.')],settings=Settings(width=720,height=1280,color=False,zoom=False))
            plan=Plan(0,2,[(0,2)],[Line('Test',0,2)],[],[],[],2,0,[],[dict(path=p.host,start=0,end=2,rotation=0,kind='host')])
            def cached(engine,plan,base):shutil.copyfile(d/'old-base.mp4',base)
            with patch('hockey_editor.host_media.prepare_base',side_effect=cached):
                Engine(p,0,d/'cache',threading.Event()).render(plan,d/'fixed.mp4',draft=True)
            self.assert_portrait(d/'fixed.mp4',d)
            base=d/'cache/host-prepared.mp4';stamp=base.stat().st_mtime_ns
            normalize_encoded_orientation(base)
            self.assertEqual(base.stat().st_mtime_ns,stamp)

if __name__=='__main__':unittest.main()
