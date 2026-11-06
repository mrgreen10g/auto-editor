"""Boundary regressions using synthetic speech, never private recordings."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hockey_editor.model import Project, Block
from hockey_editor.timeline import Line
from hockey_editor.uz_hockey import prepare
from hockey_editor.uz_hockey_support import spoken_pair_in
from hockey_editor.uz_hockey_boundaries import ordinal_starts, episode_recap,first_body_after_pause
from test_uz_speech import segment


class HockeyBoundaryTests(unittest.TestCase):
    def test_distinct_noisy_names_need_pair_context(self):
        for title, text in [
            ('Metallurg — Amur', 'Birinchi oyin Metallurk Amr uchrashuvi.'),
            ('Severstal — Salavat Yulaev', 'Sevistal Salovat Yulayev oyinini koramiz.'),
            ('Neftekhimik — Shanghai Dragons', 'Ikkinchi oyin nefti xemik Shahay Dragons.'),
            ('SKA — Dinamo Moskva', 'Skai Dynamo Moskva uchrashuvi.')]:
            self.assertTrue(spoken_pair_in(title, text), (title, text))
        for title, text in [
            ('CSKA — Spartak', 'SKA Spartak'), ('SKA — Spartak', 'CSKA Spartak'),
            ('Dinamo Minsk — Lada', 'Dinamo Moskva Lada'),
            ('New York Rangers — Toronto Maple Leafs', 'New York Islanders Toronto'),
            ('New York Islanders — Toronto Maple Leafs', 'New York Rangers Toronto'),
            ('Metallurg — Amur', 'Metallurk boshqa tahlil'),
            ('Severstal — Salavat Yulaev', 'Salovat Yulayev boshqa tahlil')]:
            self.assertFalse(spoken_pair_in(title, text), (title, text))

    def test_ordinal_needs_correct_number_and_nearby_team(self):
        data = [segment(100, 105, '  Ikkinchi  uchrashuvga otamiz.'),
                segment(120, 125, 'Spartak haqida gaplashamiz.')]
        self.assertEqual(ordinal_starts('CSKA — Spartak', data, 2, 80), [100])
        self.assertEqual(ordinal_starts('CSKA — Spartak', data, 1, 80), [])
        self.assertEqual(ordinal_starts('CSKA — Spartak', data, 2, 110), [])
        self.assertEqual(ordinal_starts('CSKA — Spartak', data[:1], 2, 80), [])
        distant = [data[0], segment(135, 140, 'Spartak haqida gaplashamiz.')]
        self.assertEqual(ordinal_starts('CSKA — Spartak', distant, 2, 80), [])
        for text in ('Ikkinchi bolimda gol uradi.', 'Ikkinchi ssenariy haqida.'):
            self.assertEqual(ordinal_starts('CSKA — Spartak', [segment(100,105,text),data[1]],2,80), [])

    def test_first_take_requires_intro_pause_and_distinctive_club(self):
        title='Severstal — Salavat Yulaev'
        data=[segment(25,34,'Kirish tugadi.'),segment(53,61,'Sevisida Salovat Yulaev oyinini koramiz.')]
        self.assertEqual(first_body_after_pause(title,data,24),[53])
        self.assertEqual(first_body_after_pause(title,data,0),[])
        self.assertEqual(first_body_after_pause(title,[data[0],segment(38,45,data[1]['text'])],24),[])
        self.assertEqual(first_body_after_pause(title,[data[0],segment(150,155,data[1]['text'])],24),[])
        for text in ('Boshqa jamoa haqida gapiramiz.', 'SKA haqida.', 'Salavat Yulaev va Traktor.'):
            self.assertEqual(first_body_after_pause(title,[data[0],segment(53,61,text)],24),[])

    def test_recap_requires_episode_context(self):
        for text in ('Xullas bu jamoa gol uradi.', 'Demak bu uchrashuv qiziqarli.',
                     'Jamoa javob golini qaytardi.'):
            self.assertFalse(episode_recap([segment(100, 105, text)], 0), text)
        self.assertTrue(episode_recap([segment(100,110,'Endi tanlovlamizni yana bir bor eslatib otaman.')],0))
        data=[segment(100,110,'Ikkita uchrashuvni tahlil qilishga harakat qildim.'),
              segment(112,117,'Yana bir bor eslataman.')]
        self.assertTrue(episode_recap(data,0))
        self.assertFalse(episode_recap(data[:1],0))
        self.assertFalse(episode_recap([data[0],segment(130,135,data[1]['text'])],0))

    def test_late_draft_estimate_cannot_hide_spoken_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.touch()
            p=Project(host=str(host), profile='uz_hockey', blocks=[
                Block(title='Severstal — Salavat Yulaev',script='Unrelated first script body.',language='uz',sport='hockey'),
                Block(title='SKA — Lada',script='Unrelated second script body.',language='uz',sport='hockey'),
                Block(title='Spartak — Torpedo',script='Unrelated third script body.',language='uz',sport='hockey')])
            p.intro.script='Salom.';p.outro.script='Xayr.';p.settings.cut_pauses=False
            blocks=[p.intro,*p.blocks,p.outro]
            rough={b.uid:([Line('Draft',a,z)],[]) for b,a,z in zip(blocks,[0,300,320,340,380],[300,320,340,380,400])}
            data=[segment(0,10,'Severstal Salavat Yulaev SKA Lada Spartak Torpedo. Boshladik!'),
                  segment(50,60,'Sevistal Salovat Yulayev oyinini koramiz.'),
                  segment(150,160,'Ikkinchi oyin SKA Lada uchrashuvi.'),
                  segment(250,260,'Spartak Torpedo oyiniga otamiz.'),
                  segment(350,360,'Endi variantlarimizni yana bir bor takrorlaymiz.'),
                  segment(370,380,'Severstal Salavat Yulaev SKA Lada Spartak Torpedo.')]
            with patch('hockey_editor.review.draft_alignment',return_value=rough),patch('hockey_editor.uz_anchors.script_ranges',return_value=None):
                ranges=prepare(p,data,400)
            self.assertEqual(ranges,[(0,50),(50,150),(150,250),(250,350),(350,400)])
            self.assertTrue(all(not b.asr_lines[0].get('review_reason') for b in blocks))


if __name__=='__main__':unittest.main()
