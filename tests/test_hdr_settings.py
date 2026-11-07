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
