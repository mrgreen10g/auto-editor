"""Real export regression: informational panels + quiet accents + unchanged length."""
import sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hockey_editor.model import Project,Block,Settings
from hockey_editor.timeline import Line,Plan
from hockey_editor.football_facts import enrich
from hockey_editor.media import run,probe
from hockey_editor.engine import Engine

def check():
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);source=root/'source.mp4'
  run(['-y','-f','lavfi','-i','color=c=gray:s=1280x720:r=30:d=4','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',source])
  text='Команда владела мячом пятьдесят четыре процента времени.';block=Block(script=text,sport='football')
  project=Project(host=str(source),profile='ru_football',blocks=[block],settings=Settings(auto_rotate=False,color=False,denoise=False,zoom=False,wobble=False))
  lines=[Line(text,.5,3.8)];cards=enrich(block,lines,[])
  plan=Plan(0,4,[(0,4)],lines,[],cards,[],4,rotation=0)
  cache=root/'cache';out=root/'result.mp4';Engine(project,0,cache,threading.Event()).render(plan,out,draft=True)
  info=probe(out);assert info['audio'] and abs(info['duration']-4)<.1,info
  graph=(cache/'final-filter.txt').read_text();assert '[fxaudio]' in graph and 'overlay=' in graph
  print('INFORMATIONAL EXPORT OK')
if __name__=='__main__':check()
