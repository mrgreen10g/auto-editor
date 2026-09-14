import copy,itertools,tempfile,unittest
from pathlib import Path
from test_uz_speech import project,sample,segment
from hockey_editor.uz_speech import prepare,make_lines
from hockey_editor.recording_times import parse_times,recording_ranges
from hockey_editor.uz_forecasts import match_forecasts,features
from hockey_editor.framing import forecast_text
from hockey_editor.uzbek import asr_framing_cards
from hockey_editor.timeline import Line

class GapTests(unittest.TestCase):
    def test_large_gaps_keep_each_end_and_reject_overlaps(self):
        p=project('host.mp4')
        p.recording_times='00:02 00:15 Intro\n00:30 01:17 A\n01:30 01:56 B\n02:10 02:38 C\n02:50 03:14 Recap\n03:15 03:24 End'
        self.assertEqual(recording_ranges(p,sample()),[(2,15),(30,77),(90,116),(130,158),(170,204)])
        self.assertEqual(len(parse_times(p.recording_times,3)),6)
        with self.assertRaises(ValueError):parse_times(p.recording_times.replace('00:30 01:17','00:10 01:17'),3)

    def test_first_analysis_inside_first_minute_not_used_as_intro(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mp4';host.touch();p=project(host);data=sample()
            # Intro team names less clear than their later repetition.
            data[0]=segment(2,8,'Augsbur Bayir, Borussia Dortmund Padi Boron, Mays Eintraxt.')
            bounds=prepare(p,data)
            self.assertEqual(bounds[1],30)
            self.assertEqual(p.intro.asr_lines[-1]['end'],15)
            self.assertEqual(p.blocks[0].asr_lines[-1]['end'],77)

    def test_unannotated_line_never_stretches_into_recording_break(self):
        lines,cards=make_lines([segment(1,5,'Bu gap tugadi.'),segment(45,50,'Yangi bo‘lim.')],1,45,[])
        self.assertEqual(len(lines),1);self.assertEqual(lines[0]['end'],5)
        self.assertFalse(cards)

    def test_every_recap_order_retains_ids_and_card_text(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mp4';host.touch()
            texts=["Birinchi Bayer X2 va 1,5 dan ko'p gol variant.","Ikkinchi Dortmund g'alabasi va 1,5 dan ko'p gol variant.","Uchinchi Mays Eintraxt 1,5 dan ko'p gol variant."]
            for order in itertools.permutations(range(3)):
                p=project(host);data=sample()
                data[8:11]=[segment(170+j*8,178+j*8,('Yana qaytaraman. ' if j==0 else '')+texts[i]) for j,i in enumerate(order)]
                prepare(p,data)
                cards,_=asr_framing_cards(p,p.outro,[Line(**l) for l in p.outro.asr_lines],204)
                picks=[c for c in cards if c.title=='ПРОГНОЗ']
                self.assertEqual([c.forecast_id for c in picks],[p.blocks[i].uid for i in order])
                self.assertEqual([c.text for c in picks],[forecast_text(p.blocks[i]) for i in order])
                self.assertTrue(all(a.end<=b.start for a,b in zip(picks,picks[1:])))

    def test_phonetic_goal_requires_forecast_context(self):
        self.assertTrue(features("Birinchi bir yamtidan ko'p-ko'l variantni qildik.")['total'])
        self.assertFalse(features("Ko'l atrofida odamlar ko'p.")['total'])
        self.assertEqual(features('Uchrinchi uchrashuv')['ordinal'],2)

    def test_missing_forecast_not_invented_from_other_two(self):
        p=project('host.mp4');refs={b.uid:forecast_text(b) for b in p.blocks}
        with self.assertRaises(ValueError):match_forecasts(sample()[9:11],170,195,p.blocks,refs)
