"""Synthetic reproductions of corpus failures; no private scripts or audio."""
import unittest
from hockey_editor.uz_structure import parse
from hockey_editor.uz_speech import name_hits,recap_cue,pair_hits


class CorpusRegressions(unittest.TestCase):
    def test_hockey_decoder_spellings_require_the_exact_other_team(self):
        from hockey_editor.uz_hockey_support import spoken_pair_in
        for title,text in [('Lokomotiv — Traktor', 'O’lakomay sub-traktor'),
                           ('Avtomobilist — Dinamo Moskva', 'Keyingi oyinda avtomobiliz Dinamo Moskva oyini bor.'),
                           ('Ak Bars — Sibir', 'Akbar Sibir oyini.'),
                           ('Ak Bars — Sibir', 'Oxirgi oyinda Akbars Sibir oyniga yetib keldik.')]:
            self.assertTrue(spoken_pair_in(title,text),text)
        self.assertFalse(spoken_pair_in('Ak Bars — Sibir','Akbar bugun gapiradi.'))
        self.assertFalse(spoken_pair_in('Ak Bars — Lada','Akbar Sibir oyini.'))
        self.assertFalse(spoken_pair_in('Avtomobilist — Dinamo Minsk','avtomobiliz Dinamo Moskva'))

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

    def test_mixed_body_headings_keep_oral_only_match(self):
        intro,blocks,outro=parse('ARSENAL — CHELSEA\nROMA — MILAN\nKIRISH\nSalom.\n'
            'ARSENAL — CHELSEA\nBirinchi tahlil.\nIkkinchi uchrashuv — Roma va Milan.\n'
            'Ikkinchi tahlil.\nYAKUN\nXayr.','football')
        self.assertEqual(len(blocks),2)
        self.assertIn('Ikkinchi tahlil.',blocks[1].script)

    def test_recap_pair_heading_does_not_disable_spoken_body(self):
        intro,blocks,outro=parse('ARSENAL — CHELSEA\nKIRISH\nSalom.\n'
            'Birinchi uchrashuv — Arsenal va Chelsea.\nTahlil.\nYAKUN\n'
            'ARSENAL — CHELSEA\nXayr.','football')
        self.assertEqual(len(blocks),1)
        self.assertIn('Tahlil.',blocks[0].script)
        self.assertIn('Xayr.',outro.script)

    def test_curly_apostrophe_ordinal_is_not_a_literal_team(self):
        _,blocks,_=parse('ARSENAL — CHELSEA\nKIRISH\nSalom.\n'
            'BIRINCHI O’YIN — ARSENAL VA CHELSEA\n'
            'Birinchi uchrashuv — Arsenal va Chelsea.\nTahlil.','football')
        self.assertEqual(len(blocks),1)
        self.assertEqual(blocks[0].title.casefold(),'arsenal — chelsea')

    def test_weight_announcement_does_not_create_another_fight(self):
        _,blocks,_=parse('KIRISH\nSalom.\nALPHA FIGHTER — BETA FIGHTER\n'
            'Birinchi jang — 64 kilogrammgacha vaznda Alpha Fighter va Beta Fighter.\n'
            'Bu jang haqida tahlil.','combat')
        self.assertEqual(len(blocks),1)
        self.assertIn('64 kilogrammgacha vaznda',blocks[0].script)

    def test_adjacent_short_unknown_name_and_full_announcement_are_one_block(self):
        _,blocks,_=parse('LEX — BAYER\nKIRISH\nSalom.\n'
            'IKKINCHI O’YIN — LEX VA BAYER\n'
            'Ikkinchi uchrashuv — Lex Poznan va Bayer Leverkuzen.\nTahlil.','football')
        self.assertEqual(len(blocks),1)
        self.assertIn('Lex Poznan',blocks[0].script)

    def test_shortened_recap_cue_needs_recap_context(self):
        for cue in ('Demi', 'Demek', 'Demak'):
            self.assertTrue(recap_cue(cue+' bugungi tanlovimiz uchta uchrashuv uchun.'))
        self.assertFalse(recap_cue('Demi kuchli jamoa.'))
        self.assertFalse(recap_cue('Bugun jamoa uyda oynaydi.'))

    def test_acronym_and_recap_do_not_force_whole_episode_draft(self):
        from hockey_editor.model import Project,Block
        from hockey_editor.uz_speech import sections
        from test_uz_speech import segment
        p=Project(profile='uz_football',blocks=[
            Block(title='Andijon — Qizilqum',language='uz',script='Birinchi tahlil.'),
            Block(title="Mash'al — OKMK",language='uz',script='Ikkinchi tahlil.')])
        p.intro.script='Salom.';p.outro.script='Xayr.'
        data=[segment(0,8,'Andijon Qizilqum Mashal Okimaka.'),
              segment(12,16,'Birinchi oyin Andijon Qizilqum.'),
              segment(20,35,'Bu uyin haqida tahlil.'),
              segment(43,48,'Ikinchi Mashal Okimaka oyini.'),
              segment(60,80,'Bu ikkinchi tahlil.'),
              segment(90,100,'Demi bugungi tanlovimiz ikkita uyin uchun.'),
              segment(110,120,'Xayr.')]
        self.assertEqual(sections(p,data)[0],[0,12,43,90,120])


if __name__=='__main__':unittest.main()
