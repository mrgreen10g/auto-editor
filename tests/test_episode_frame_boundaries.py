"""Frame rounding at joins must not create empty speech intervals."""
import copy
import unittest

from hockey_editor.editing import validate_plan
from hockey_editor.episode import combine, crop_padding_at_next_speech, trim_overlap
from hockey_editor.model import Block, Project
from hockey_editor.timeline import Line, Plan, frame


class EpisodeFrameBoundaryTests(unittest.TestCase):
    def plans(self):
        # Same frame coordinates as the reported two-analysis boundary.
        a = Plan(frame(3587/30), 229., [(0., 109.2), (109.3, frame(3283/30))],
                 [Line('First analysis', 0., 109.2)], [], [], [], frame(109.2 + 4/30))
        b = Plan(frame(6866/30), frame(7166/30), [(0., 10.)],
                 [Line('Next analysis', 0., 10.)], [], [], [], 10.)
        return a, b

    def test_crop_drops_frame_boundary_residue(self):
        a, b = self.plans()
        original = copy.deepcopy(a)
        cropped = crop_padding_at_next_speech(a, b)
        self.assertEqual(cropped.keep, [(0., 109.2)])
        self.assertEqual(cropped.duration, 109.2)
        self.assertEqual(a, original)
        validate_plan(cropped)

    def test_overlap_drops_fully_consumed_padding_frame(self):
        # 1/3 - 0.2 is microscopically less than 4/30 in binary floats.
        p = Plan(0.2, 2., [(0., 4/30), (0.3, 1.3)],
                 [Line('Speech', 4/30, 34/30)], [], [], [], 34/30)
        result = trim_overlap(p, 1/3)
        self.assertEqual(result.keep, [(0.3, 1.3)])
        self.assertEqual(result.duration, 1.)
        self.assertEqual(result.lines[0].start, 0.)
        validate_plan(result)

    def test_combined_plan_round_trip_has_only_positive_frame_intervals(self):
        p = Project(blocks=[Block(title='First'), Block(title='Second')])
        result = combine(p, list(self.plans()))
        result = validate_plan(Plan.from_dict(result.to_dict()))
        self.assertEqual(len(result.sections), 2)
        self.assertEqual(result.duration, 119.2)
        self.assertEqual(len(result.lines), 2)
        self.assertTrue(all(round(b*30) > round(a*30) for a, b in result.keep))
        self.assertEqual(result.keep[-1], (6866/30, 7166/30))

    def test_genuine_invalid_interval_still_rejected(self):
        a, _ = self.plans()
        a.keep.append((1., 1.))
        with self.assertRaisesRegex(ValueError, 'монтажной разметке'):
            validate_plan(a)


if __name__ == '__main__':
    unittest.main()
