import tempfile,unittest
from pathlib import Path
from hockey_editor.shorts import parse_script,sections
from hockey_editor.model import Project
from hockey_editor.uz_speech import prepare,name_hits
from hockey_editor.team_names import football_identity,football_positions
from test_shorts import segments

SCRIPT="""SHORTS SSENARIY
Aral bugun uyda. Uchta uchrashuvni ko'ramiz.
Birinchi o'yin — Kattaqo'rg'on va Metallurg.
Tanlovim — Metallurg X2 va total 1,5 dan ko'p.
Telegram kanaliga obuna bo'ling. Havola tavsifda.
Ikkinchi o'yin — Aral va TerDU.
Tanlovim — Aral g'alabasi va total 1,5 dan ko'p.
Va uchinchi o'yin — G'azalkent va Paxtakor II.
Tanlovim — G'azalkent g'alabasi va total 1,5 dan ko'p.
Demak:
Kattaqo'rg'on — Metallurg: Metallurg X2 + total 1,5 dan ko'p.
Aral — TerDU: Aral g'alabasi + total 1,5 dan ko'p.
G'azalkent — Paxtakor II: G'azalkent g'alabasi + total 1,5 dan ko'p.
Layk bosing!
"""
class DeclaredPairsTests(unittest.TestCase):
    def test_unknown_clubs_do_not_require_new_catalog_release(self):
        text=SCRIPT.replace("Kattaqo'rg'on",'Example Academy').replace('Metallurg','NovelTown')
        self.assertIsNone(football_identity('Example Academy'))
        a,b,c=parse_script(text);self.assertEqual(b[0].title,'Example Academy — NovelTown')
        p=Project(profile='uz_football_shorts',intro=a,blocks=b,outro=c)
        ss=segments(p);bounds,_,_=sections(p,ss)
        self.assertEqual(bounds[1],next(s['start'] for s in ss if s['text'].startswith('Birinchi')))
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.write_bytes(b'test');p.host=str(host);prepare(p,ss)
        self.assertEqual(len(p.blocks),3)
        self.assertTrue(any('NovelTown' in c['text'] for c in p.blocks[0].speech_cards.values()))
        for block in p.blocks:
            picks=[v for v in block.speech_cards.values() if v['title']=='ПРОГНОЗ']
            self.assertEqual(len(picks),1);self.assertFalse(picks[0].get('needs_review'))
        self.assertEqual(len([v for v in p.outro.speech_cards.values() if v['title']=='ПРОГНОЗ']),3)

    def test_malformed_middle_pair_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError,'Aral va 2:1'):
            parse_script(SCRIPT.replace('Aral va TerDU.','Aral va 2:1.'))

    def test_reserve_side_is_distinct_from_senior_side(self):
        words=lambda s:[dict(word=w) for w in s.split()]
        self.assertFalse(football_positions('Paxtakor','Paxtakor II'))
        self.assertFalse(name_hits('Paxtakor II',words('Paxtakor yutdi')))
        self.assertFalse(name_hits('Paxtakor',words('Paxtakor II')))
        self.assertFalse(name_hits('Paxtakor',words('Paxtakor II yutdi')))
        self.assertTrue(name_hits('Paxtakor II',words('Paxtakor II')))
        self.assertTrue(name_hits('Paxtakor II',words('Paxtakor 2')))
        self.assertTrue(football_positions('Paxtakor','Paxtakor 2 gol urdi'))

    def test_declared_same_team_and_prose_are_rejected(self):
        for value in ['Aral va Aral.', 'hujum va himoya.']:
            with self.assertRaises(ValueError):parse_script(SCRIPT.replace('Aral va TerDU.',value))
