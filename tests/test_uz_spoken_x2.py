"""Regression coverage for spoken markets and partially recognized openings."""
import unittest
from test_uz_speech import project,sample,segment
from hockey_editor.uz_forecasts import features,match_forecasts
from hockey_editor.uz_speech import sections,recap_cue
from hockey_editor.framing import forecast_text

class SpokenX2Tests(unittest.TestCase):
    def test_spoken_x2_overrides_insured_win_wording(self):
        for value in ('X2','X 2','X ikki','X-ikki','eksikki','eksiki','medeksiki'):
            with self.subTest(value=value):
                f=features("Bayer g‘alabasini sug‘urtaladik, "+value)
                self.assertTrue(f['double']);self.assertFalse(f['winner'])
        self.assertFalse(features("Bayer g‘alabasi va ikki gol.")['double'])

    def test_split_words_and_compound_market_keep_same_span(self):
        p=project('host.mp4');b=p.blocks[0];refs={b.uid:forecast_text(b)}
        data=[segment(10,13,"Bayer g‘alabasini sug‘urtaladik."),segment(13,14,'X'),segment(14,18,"ikki va 1,5 dan ko‘p gol variant.")]
        a=match_forecasts(data,0,20,[b],refs)[0]
        words=[w for s in data for w in s['words']]
        merged=[dict(start=10,end=18,text=' '.join(w['word'] for w in words),words=words)]
        c=match_forecasts(merged,0,20,[b],refs)[0]
        self.assertEqual((a['start'],a['end'],a['forecast_id']),(10,18,b.uid))
        self.assertEqual(a,c)
        data[-1]=segment(14,18,"ikki va 2,5 dan ko‘p gol variant.")
        with self.assertRaises(ValueError):match_forecasts(data,0,20,[b],refs)

    def test_recap_return_phrase_requires_context(self):
        self.assertTrue(recap_cue('Video oxirida tanlovlarimiz yana eslata o‘tamiz.'))
        self.assertFalse(recap_cue('Jamoaning o‘yinini eslatib o‘tamiz.'))
        self.assertFalse(recap_cue('Tanlovlarimiz yaxshi.'))

    def test_ordinal_requires_matching_team_and_block(self):
        p=project('host.mp4');data=sample()
        # Only one recognizable team, with the correct section ordinal.
        data[2]=segment(30,37,'Birinchi o‘yin Bayer noma nom.')
        self.assertEqual(sections(p,data)[0][1],30)
        for text in ('Ikkinchi o‘yin Bayer noma nom.','Birinchi o‘yin noma nom.'):
            data[2]=segment(30,37,text)
            with self.subTest(text=text),self.assertRaises(ValueError):sections(p,data)

    def test_asosuna_opening_before_clearer_pair(self):
        from hockey_editor.model import Block
        p=project('host.mp4')
        p.blocks[0]=Block(title='Atletiko Madrid — Osasuna')
        data=sample();data[0]=segment(2,8,'Atletiko Madrid Osasuna, Borussia Dortmund Padi Boron, Mays Eintraxt.')
        data[2]=segment(30,37,'Birinchi o‘yin Atletika Asosuna o‘yini.')
        data[3]=segment(70,77,'Atletiko Madrid Osasuna uchrashuvi.')
        self.assertEqual(sections(p,data)[0][1],30)
