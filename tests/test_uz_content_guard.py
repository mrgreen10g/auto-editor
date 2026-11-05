import unittest
from hockey_editor.model import Project, Block
from hockey_editor.uz_content_guard import check_combat_recording


class ContentGuardTests(unittest.TestCase):
    def setUp(self):
        self.project = Project(profile='uz_combat', blocks=[
            Block(title='Alpha Fighter — Beta Boxer')])
        self.data = [dict(start=i * 20, end=i * 20 + 15,
                          text=t, words=[]) for i, t in enumerate([
            'Valensiya Betis futbol uchrashuvi.',
            'Real Madrid Barcelona gol uradi.',
            'Valensiya Betis ikkinchi taym.',
            'Real Madrid Barcelona penalti.',
            'Valensiya Betis gol uradi.',
            'Real Madrid Barcelona futbol haqida.'])]

    def test_repeated_other_sport_content_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'разным выпускам'):
            check_combat_recording(self.project, self.data)

    def test_absent_fighter_names_alone_are_not_a_mismatch(self):
        check_combat_recording(self.project, [dict(s, text='Tushunarsiz ovoz.') for s in self.data])

    def test_short_intro_or_one_off_football_comparison_is_inconclusive(self):
        check_combat_recording(self.project, self.data[:2])
        check_combat_recording(self.project, self.data[:2] + [dict(self.data[-1], text='Boshqa gap.')])

    def test_expected_fighter_or_combat_context_prevents_wrong_rejection(self):
        for text in ('Alpha Fighter haqida.', 'UFC jang tahlili.'):
            check_combat_recording(self.project, self.data + [dict(start=120, end=125, text=text)])

    def test_football_profile_is_not_rejected(self):
        self.project.profile = 'uz_football'
        check_combat_recording(self.project, self.data)
