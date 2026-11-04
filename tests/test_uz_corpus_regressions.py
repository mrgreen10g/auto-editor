"""Synthetic reproductions of corpus failures; no private scripts or audio."""
import unittest
from hockey_editor.uz_structure import parse
from hockey_editor.uz_speech import name_hits,recap_cue,pair_hits


class CorpusRegressions(unittest.TestCase):
    def test_index_announcements_do_not_create_analysis_blocks(self):
        for sport,pairs in (
            ('football',['Arsenal — Chelsea','Roma — Real Madrid']),
            ('hockey',['SKA — Lada','Spartak — Torpedo']),
            ('combat',['Alpha Fighter — Beta Fighter','Gamma Fighter — Delta Fighter'])):
            announcements=[f'{n} uchrashuv — '+p.replace(' — ',' va ')+'.' for n,p in zip(('Birinchi','Ikkinchi'),pairs)]
            text='\n'.join([*pairs,'KIRISH','Salom.',*announcements,'Boshladik!',pairs[0],announcements[0],
                            'Birinchi tahlil.',pairs[1],announcements[1],'Ikkinchi tahlil.','YAKUN','Xayr.'])
            with self.subTest(sport=sport):
                intro,blocks,outro=parse(text,sport)
                self.assertEqual(len(blocks),2)
                self.assertTrue(all(v in intro.script for v in announcements))
                self.assertIn('Boshladik!',intro.script)
                self.assertIn(announcements[0],blocks[0].script)
                self.assertEqual(outro.script,'Xayr.')

    def test_acronym_pronunciation_is_scoped_to_named_club(self):
        for text in ('Okimaka','okimakada','okimaki','o ka em ka'):
            words=[{'word':w} for w in text.split()]
            self.assertTrue(name_hits('OKMK',words),text)
            self.assertFalse(name_hits('Nasaf',words),text)
        self.assertTrue(pair_hits("Mash'al — OKMK",[{'word':w} for w in 'Mashal Okimaka'.split()]))

    def test_shortened_recap_cue_needs_recap_context(self):
        self.assertTrue(recap_cue('Demi bugungi tanlovimiz uchta uchrashuv uchun.'))
        self.assertFalse(recap_cue('Demi kuchli jamoa.'))
        self.assertFalse(recap_cue('Bugun jamoa uyda oynaydi.'))


if __name__=='__main__':unittest.main()
