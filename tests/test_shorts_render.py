"""Real FFmpeg regression: portrait source, split game view and middle promo."""
import tempfile,threading,unittest
from pathlib import Path
from PIL import Image
from hockey_editor.media import run,probe
from hockey_editor.model import Project,Block,Settings
from hockey_editor.timeline import Plan,Card,Insert,Line
from hockey_editor.engine import Engine

class ShortsRenderTests(unittest.TestCase):
    def test_portrait_split_promo_and_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder)
            run(['-y','-f','lavfi','-i','color=c=blue:s=180x320:r=30:d=6','-f','lavfi','-i','sine=f=220:r=48000:d=6','-t',6,'-c:v','libx264','-c:a','aac',d/'host.mp4'])
            for name,color in [('game','red'),('promo','green')]:
                run(['-y','-f','lavfi','-i',f'color=c={color}:s=320x180:r=30:d=2','-c:v','libx264',d/(name+'.mp4')])
            p=Project(host=str(d/'host.mp4'),profile='uz_football_shorts',blocks=[Block(title='Germaniya — Italiya',language='uz',script='Tanlovim — Italiya X2 va total 1,5 dan ko‘p.')],settings=Settings(width=720,height=1280,auto_rotate=False,zoom=False,transitions=False,animate_cards=False,wobble=False,color=False))
            p.assets['telegram']=str(d/'promo.mp4')
            plan=Plan(0,6,[(0,6)],[Line('Test',0,6)],[Insert(str(d/'game.mp4'),1,3,0,'Game')],[Card(3,5.5,'ТЕЛЕГРАМ','Telegram',asset=p.assets['telegram'])],[],6,0,[],[dict(path=p.host,start=0,end=6,rotation=0,kind='host')])
            engine=Engine(p,0,d/'cache',threading.Event());engine.render(plan,d/'result.mp4')
            meta=probe(d/'result.mp4');self.assertEqual((meta['width'],meta['height']),(720,1280));self.assertTrue(meta['audio']);self.assertAlmostEqual(meta['duration'],6,delta=.08)
            for t in (2,5):
                run(['-y','-ss',t,'-i',d/'result.mp4','-frames:v',1,d/f'{t}.png'])
            with Image.open(d/'2.png') as im:
                self.assertGreater(im.getpixel((360,180))[0],200)
                self.assertGreater(im.getpixel((360,800))[2],200)
            with Image.open(d/'5.png') as im:
                # Short promo holds its final frame; no leak of the blue host.
                red,green,blue=im.getpixel((360,640));self.assertGreater(green,80);self.assertLess(blue,40)
            engine.render(plan,d/'draft.mp4',draft=True)
            self.assertEqual((probe(d/'draft.mp4')['width'],probe(d/'draft.mp4')['height']),(360,640))

if __name__=='__main__':unittest.main()
