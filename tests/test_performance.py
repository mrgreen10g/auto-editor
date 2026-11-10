import unittest
from unittest.mock import patch
from hockey_editor.performance import budget,ffmpeg_args
class PerformanceTests(unittest.TestCase):
 def test_budget(self):
  with patch('hockey_editor.performance.os.cpu_count',return_value=8),patch('hockey_editor.performance.mode',return_value='new'):
   self.assertEqual(budget('encode'),7);self.assertEqual(budget('speech'),7);self.assertEqual(budget('filters'),4)
 def test_no_quality_or_decoder_changes(self):
  args=['-threads','2','-i','a','-threads','1','-i','b','-filter_complex_threads','2','-c:v','libx264','-crf','19','-preset','fast','-threads','4','out.mp4']
  with patch('hockey_editor.performance.mode',return_value='new'),patch('hockey_editor.performance.os.cpu_count',return_value=8):
   out=ffmpeg_args(args);self.assertEqual(out[:8],args[:8]);self.assertEqual(out[10:16],args[10:16]);self.assertEqual(out[-2],'7');self.assertEqual(args[-2],'4')
  with patch('hockey_editor.performance.mode',return_value='old'),patch('hockey_editor.performance.os.cpu_count',return_value=8):
   result=ffmpeg_args(args);self.assertEqual(result[-2],'6');self.assertEqual(result[9],'3')
 def test_small_machine(self):
  with patch('hockey_editor.performance.mode',return_value='new'),patch('hockey_editor.performance.os.cpu_count',return_value=2):self.assertEqual(budget('encode'),1)
