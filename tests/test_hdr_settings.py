import unittest
from unittest.mock import patch
from hockey_editor.video_color import sdr_filter
from hockey_editor.mobile_settings import validate
class Tests(unittest.TestCase):
 def test_hdr_only(self):
  for t in ('arib-std-b67','smpte2084'):
   with patch('hockey_editor.video_color.probe',return_value={'color_transfer':t}):self.assertIn('tonemap',sdr_filter('x'))
  with patch('hockey_editor.video_color.probe',return_value={}):self.assertEqual(sdr_filter('x'),'')
 def test_overrides(self):
  self.assertEqual(validate({'mirror_host':True,'subtitles':False,'insert_frequency':'high'}),{'mirror_host':True,'subtitles':False,'insert_frequency':'high'})
  for v in ({'mirror_host':'false'},{'zoom_max':3.0},{'fps':60},{'music_db':float('nan')},{'unknown':1}):
   with self.assertRaises(ValueError):validate(v)

class HDRRenderTests(unittest.TestCase):
 def test_packaged_ffmpeg_hdr_conversion_and_sdr_tags(self):
  import tempfile
  from pathlib import Path
  from hockey_editor.media import run,probe
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'hdr.mov';target=Path(d)/'sdr.mp4'
   run(['-y','-f','lavfi','-i','testsrc2=s=160x90:r=30:d=1','-c:v','libx265','-x265-params','pools=1:frame-threads=1:colorprim=9:transfer=18:colormatrix=9:log-level=error','-pix_fmt','yuv420p10le','-color_primaries','bt2020','-color_trc','arib-std-b67','-colorspace','bt2020nc',source])
   import subprocess
   from hockey_editor.media import ffmpeg
   diagnostic=subprocess.run([ffmpeg(),'-hide_banner','-i',str(source)],capture_output=True,text=True).stderr
   self.assertEqual(probe(source)['color_transfer'],'arib-std-b67',diagnostic)
   run(['-y','-i',source,'-vf',sdr_filter(source)+'null','-c:v','libx264',target])
   self.assertEqual(probe(target)['color_transfer'],'bt709')
   self.assertEqual(sdr_filter(target),'')

class CameraAudioTests(unittest.TestCase):
 def test_apac_falls_back_to_aac(self):
  from types import SimpleNamespace
  from hockey_editor.media import _probe_cached
  text='Warning (Video: h264): probing stream.\nDuration: 00:00:23.35\n Stream #0:0: Video: hevc, yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67), 1920x1080\n Stream #0:1: Audio: none (apac), 48000 Hz\n Stream #0:2: Audio: aac (LC), 48000 Hz'
  _probe_cached.cache_clear()
  with patch('hockey_editor.media.ffmpeg',return_value='ffmpeg'),patch('hockey_editor.media.subprocess.run',return_value=SimpleNamespace(stderr=text)):
   result=_probe_cached('iphone-fixture',1,1)
  self.assertEqual(result['audio_stream'],2)
  self.assertEqual(result['color_transfer'],'arib-std-b67')
