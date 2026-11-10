import unittest,threading,time,tempfile,subprocess,os
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from hockey_editor.parallel_scan import scan_many
from hockey_editor.zoom_expression import expression
from hockey_editor.performance import scan_budget,budget

class SpeedTests(unittest.TestCase):
 def test_parallel_order_duplicates_and_errors(self):
  barrier=threading.Barrier(2);calls=[]
  class Scanner:
   def __init__(self,**kw):pass
   def scan(self,s):
    calls.append(s.path);barrier.wait(timeout=3)
    if s.path=='b':raise ValueError('bad')
    return {'path':s.path}
  sources=[SimpleNamespace(id=i,path=p,title=p) for i,p in enumerate(['a','b','a'])]
  with patch('hockey_editor.goals.source_signature',side_effect=lambda s:s.path),patch('hockey_editor.performance.scan_workers',return_value=2):
   scans,errors=scan_many(sources,threading.Event(),lambda s:None,Scanner)
  self.assertEqual(sorted(calls),['a','b']);self.assertEqual(list(scans),[0,2]);self.assertEqual(errors,['b: bad'])
 def test_cancel_before_start(self):
  from hockey_editor.media import Cancelled
  event=threading.Event();event.set()
  with patch('hockey_editor.goals.source_signature',return_value='a'):
   with self.assertRaises(Cancelled):scan_many([SimpleNamespace(id=1,title='a')],event,lambda s:None)
 def test_thread_budget_restored(self):
  with patch('hockey_editor.performance.os.cpu_count',return_value=8),patch('hockey_editor.performance.mode',return_value='new'):
   self.assertEqual(budget('speech'),7)
   with scan_budget():self.assertEqual(budget('speech'),2)
   self.assertEqual(budget('speech'),7)
 def test_zoom_same_frames(self):
  from hockey_editor.media import ffmpeg
  windows=[(.1,.3,.4,.6),(.8,1.,1.1,1.3),(1.5,1.7,1.8,2.)]
  parts=[]
  for w in windows:
   a,b,c,d=[round(t*30) for t in w]
   parts.append(f'if(between(on,{a},{b}),(1-cos(PI*(on-{a})/{b-a}))/2,if(between(on,{b},{c}),1,if(between(on,{c},{d}),(1+cos(PI*(on-{c})/{d-c}))/2,0)))')
  old='1+0.2*('+'+'.join(parts)+')'
  def frames(expr):
   return subprocess.check_output([ffmpeg(),'-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=30:duration=2.2','-vf',f"zoompan=z='{expr}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=160x90:fps=30",'-f','framemd5','-'])
  self.assertEqual(frames(old),frames(expression(windows,.2)))

 def test_hdr_selection_matches_original_pixels(self):
  from hockey_editor.video_color import sdr_filter
  from hockey_editor.media import ffmpeg
  with patch('hockey_editor.video_color.probe',return_value={'color_transfer':'arib-std-b67'}):color=sdr_filter('fixture')
  cut="fps=30,select='not(mod(n,3))',setpts=N/(30*TB)"
  def frames(graph):
   return subprocess.check_output([ffmpeg(),'-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=60:duration=1','-vf',"format=yuv420p10le,setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc,"+graph,'-f','framemd5','-'])
  self.assertEqual(frames(color+cut),frames(cut+','+color.rstrip(',')))
