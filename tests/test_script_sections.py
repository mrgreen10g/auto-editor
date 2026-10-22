import unittest
from hockey_editor.folder_import import parse_episode
from hockey_editor.script_sections import MARKER

class ScriptSectionTests(unittest.TestCase):
    def test_markers_all_standard_profiles_and_unlimited_count(self):
        for profile in ('ru_hockey','ru_hockey_shorts','ru_football','ru_football_shorts','uz_hockey','uz_hockey_shorts','uz_football','uz_football_shorts','uz_combat','uz_combat_shorts'):
            title='Petr Yan — Merab Dvalishvili' if 'combat' in profile else 'Alpha — Beta'
            text='Hello!\n'+ '\n'.join(f'Разбор{i} {title}\nAnalysis number {i}.' for i in range(1,12))+'\nИтоги\nGoodbye.'
            intro,blocks,outro=parse_episode(text,profile)
            self.assertEqual(len(blocks),11,profile)
            self.assertEqual(intro.script,'Hello!')
            self.assertIn('Goodbye',outro.script)
            for b in blocks:
                self.assertEqual(b.title,title)
                self.assertNotIn('Разбор',b.script)
    def test_adjacent_and_suffix(self):
        for text in ('Разбор1\n\nAlpha — Beta\nText.','Alpha — Beta\nРазбор1\nText.','Alpha — Beta Разбор1\nText.'):
            self.assertEqual(parse_episode(text,'ru_football')[1][0].script,'Text.')
    def test_invalid_marker_has_no_silent_fallback(self):
        for text in ('Разбор1\nNo pair\nText.', 'Разбор1 Alpha — Beta\nText\nРазбор1 Alpha — Beta\nText'):
            with self.assertRaises(ValueError):parse_episode(text,'ru_football')
        self.assertIsNone(MARKER.search('Разбор 1'))
        self.assertIsNone(MARKER.search('ПредРазбор1'))
    def test_folder_hints_and_reparse(self):
        from hockey_editor.mobile_reparse import parse
        from dataclasses import asdict
        text='Hello\nUnknown FC — Other FC\nAnalysis text.'
        hints=['Unknown FC — Other FC']
        intro,blocks,outro=parse_episode(text,'ru_football',hints)
        self.assertEqual(len(blocks),1)
        d=dict(profile='ru_football',pair_hints=hints,blocks=[asdict(b) for b in blocks])
        again=parse(d,text+' More.')
        self.assertEqual(again['blocks'][0]['uid'],blocks[0].uid)
        self.assertIn('More.',again['blocks'][0]['script'])
    def test_markers_override_hook_and_unmarked_headings(self):
        text='Арсенал — Челси\nСегодня футбол.\nРазбор1\nЛиверпуль — Эвертон\nПрогноз на игру.\nАрсенал — Челси\nЭто сравнение.'
        intro,blocks,_=parse_episode(text,'ru_football')
        self.assertEqual(len(blocks),1)
        self.assertIn('Арсенал',intro.script)
        self.assertIn('Это сравнение',blocks[0].script)

if __name__=='__main__':unittest.main()
