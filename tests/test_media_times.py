import unittest
from hockey_editor.media import command_args

class DurationArguments(unittest.TestCase):
    def test_telegram_rounding(self):
        self.assertEqual(command_args(['-ss',1.7763568394002505e-15,'-i','telegram.mov']), ['-ss','0','-i','telegram.mov'])
    def test_preserves_values_and_paths(self):
        self.assertEqual(command_args(['-ss','01:02:03.5','-t',1e-5,'-i','1e-15.mp4']), ['-ss','01:02:03.5','-t','0.000010000','-i','1e-15.mp4'])
    def test_signed_offsets(self):
        self.assertEqual(command_args(['-itsoffset',-0.25]), ['-itsoffset','-0.250000000'])
    def test_rejects_nonfinite(self):
        for n in [float('nan'),float('inf')]:
            with self.assertRaises(ValueError):command_args(['-ss',n])
