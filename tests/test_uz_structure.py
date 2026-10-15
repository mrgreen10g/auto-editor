import unittest
from hockey_editor.uz_structure import parse


class StructureTests(unittest.TestCase):
    def test_no_required_labels(self):
        a, blocks, z = parse("Assalomu alaykum, bugun futbol haqida.\nARSENAL — CHELSEA\nArsenal uyda kuchli o'ynaydi.\nXullas, tanlovlarni takrorlaymiz.\nKeyingi videoda ko'rishguncha.", 'football')
        self.assertIn('Assalomu', a.script)
        self.assertEqual(len(blocks), 1)
        self.assertIn('Xullas', z.script)

    def test_hook_not_discarded_and_optional_outro(self):
        a, blocks, z = parse("HOOK\nBugun katta o'yin!\nKIRISH\nSalom do'stlar.\nTORONTO MAPLE LEAFS — BOSTON BRUINS\nToronto bugun uyda o'ynaydi.", 'hockey')
        self.assertIn('katta', a.script)
        self.assertIn('Salom', a.script)
        self.assertEqual(z.script, '')
        self.assertEqual(len(blocks), 1)

    def test_bet_is_not_a_fixture_and_internal_hyphen(self):
        a, blocks, z = parse("Salom.\nQO'QON-1912 — NASAF\nNasaf yaxshi o'ynaydi.\nNASAF MAG'LUB BO'LMAYDI — 1X\nYAKUNIY XULOSA\nBugungi tanlovimiz Nasaf.", 'football')
        self.assertEqual(len(blocks), 1)
        self.assertIn('1X', blocks[0].script)
        self.assertIn('Bugungi', z.script)

    def test_russian_notes_not_russian_team_names(self):
        _, blocks, _ = parse('Salom.\nТОРОНТО — БОСТОН\nToronto hujum qiladi.\n[МОНТАЖЁРУ: убрать]\nhttps://example.com', 'hockey')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].script, 'Toronto hujum qiladi.')

    def test_same_pair_heading_is_not_a_new_block(self):
        _, blocks, _ = parse('Salom.\nARSENAL — CHELSEA\nBirinchi gap.\nARSENAL — CHELSEA\nIkkinchi gap.', 'football')
        self.assertEqual(len(blocks), 1)
        self.assertIn('Ikkinchi', blocks[0].script)

    def test_missing_fixture_is_actionable_not_kirish_requirement(self):
        with self.assertRaisesRegex(ValueError, 'пары'):
            parse('Assalomu alaykum. Bugun futbol haqida.', 'football')

    def test_index_and_spoken_introductions_without_labels(self):
        a, blocks, z = parse('ARSENAL — CHELSEA\nROMA — REAL MADRID\nSalom, bugun ikki uchrashuv.\nBirinchi uchrashuv — Arsenal va Chelsea.\nBirinchi tahlil.\nIkkinchi uchrashuv — Roma va Real Madrid.\nIkkinchi tahlil.\nDemak, bugungi tanlovlarim quyidagicha.\nXayr.', 'football')
        self.assertEqual(len(blocks), 2)
        self.assertTrue(a.script.startswith('Salom'))
        self.assertIn('quyidagicha', z.script)

    def test_explicit_heading_and_spoken_alias_do_not_duplicate(self):
        _, blocks, _ = parse('KIRISH\nSalom.\nMANCHESTER CITY — PSG\nBirinchi uchrashuv — Manchester City va PSJ.\nTahlil.', 'football')
        self.assertEqual(len(blocks), 1)

    def test_single_fixture_with_thematic_sections(self):
        a, blocks, z = parse('🇺🇿 ARSENAL — CHELSEA | LONG SSENARIY\nKIRISH\nSalom do‘stlar.\nARSENAL NIMA TAKLIF QILADI?\nArsenal uyda kuchli.\nYAKUN\nXayr.', 'football')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(a.script, 'Salom do‘stlar.')
        self.assertIn('kuchli', blocks[0].script)

    def test_empty_optional_sections_are_not_rendered(self):
        from hockey_editor.model import Project
        from hockey_editor.episode import assembly_project
        for profile in ('uz_football','uz_hockey','uz_combat'):
            a,blocks,z=parse('ARSENAL — CHELSEA\nArsenal uyda kuchli o‘ynaydi.', 'football')
            p=Project(profile=profile,intro=a,blocks=blocks,outro=z,full_video=True)
            self.assertEqual([b.kind for b in assembly_project(p).blocks],['analysis'])
