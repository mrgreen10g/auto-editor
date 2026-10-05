"""Regional club names and conjunction-prefixed spoken introductions."""
import unittest,tempfile
from pathlib import Path
from hockey_editor.shorts import parse_script,sections
from hockey_editor.team_names import football_identity,football_positions
from hockey_editor.model import Project
from hockey_editor.uz_speech import prepare
from test_shorts import segments

SCRIPT="""SHORTS SSENARIY
Bugun uchta uchrashuvni ko'ramiz.
Birinchi o'yin — BuxDU va Lochin.
Tanlovim — Lochin X2 va total 1,5 dan ko'p.
Telegram kanaliga obuna bo'ling. Havola tavsifda.
Ikkinchi o'yin — Olimpik MobiUz va FarDU.
Tanlovim — FarDU X2 va total 1,5 dan ko'p.
Va uchinchi o'yin — Sho'rtan va QMU Jayxun.
Birinchi o'zaro uchrashuvda Sho'rtan 2:1 hisobida yutdi.
Tanlovim — Sho'rtan g'alabasi va total 1,5 dan ko'p.
Demak:
BuxDU — Lochin: Lochin X2 + total 1,5 dan ko'p.
Olimpik MobiUz — FarDU: FarDU X2 + total 1,5 dan ko'p.
Sho'rtan — Jayxun: Sho'rtan g'alabasi + total 1,5 dan ko'p.
Layk bosing!
"""
class ProLigaShortsTests(unittest.TestCase):
    def test_script_has_three_matches_bets_and_middle_telegram(self):
        a,b,c=parse_script(SCRIPT)
        self.assertEqual([v.title for v in b],['BuxDU — Lochin','Olimpik MobiUz — FarDU',"Sho'rtan — QMU Jayxun"])
        p=Project(profile='uz_football_shorts',intro=a,blocks=b,outro=c,full_video=True)
        ss=segments(p);bounds,_,_=sections(p,ss)
        self.assertEqual(bounds[1],next(s['start'] for s in ss if s['text'].startswith('Birinchi')))
        self.assertLessEqual(bounds[3],next(s['end'] for s in ss if s['text'].startswith('Va uchinchi')))
        self.assertEqual(bounds[4],next(s['start'] for s in ss if s['text'].startswith('Demak')))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'host';path.write_bytes(b'test');p.host=str(path);prepare(p,ss)
        for block in p.blocks:
            picks=[c for c in block.speech_cards.values() if c['title']=='ПРОГНОЗ']
            self.assertEqual(len(picks),1);self.assertIn('1,5',picks[0]['text']);self.assertFalse(picks[0].get('needs_review'))
        self.assertEqual(len([c for c in p.outro.speech_cards.values() if c['title']=='ПРОГНОЗ']),3)
        self.assertTrue(any(c['title']=='ТЕЛЕГРАМ' for c in p.blocks[0].speech_cards.values()))

    def test_bet_preserves_club_spelling(self):
        from hockey_editor.uzbek import bet
        self.assertTrue(bet('Tanlovim — FarDU X2.').startswith('FarDU X2'))
        self.assertTrue(bet("Tanlovim — Sho'rtan g'alabasi.").startswith("Sho'rtan"))

    def test_short_names_suffixes_and_distinct_bukhara_club(self):
        self.assertNotEqual(football_identity('BuxDU'),football_identity('Buxoro'))
        self.assertEqual(football_identity('Jayxun'),'QMU Jayxun')
        self.assertTrue(football_positions('FarDU','FarDUning formasi'))
        self.assertTrue(football_positions('QMU Jayxun','Jayxunni'))
        self.assertTrue(football_positions('Olimpik MobiUz',"Olimpik uyda o'ynaydi"))
        self.assertEqual(football_identity('Sho‘rtan'),"Sho'rtan")
