"""Synthetic regression for merged promos and paraphrased multi-match speech."""
import unittest
from test_uz_speech import segment
from hockey_editor.model import Project, Block
from hockey_editor.uz_speech import sections, recap_cue, telegram_spans


class SectionTransitions(unittest.TestCase):
    def sample(self):
        p=Project(profile='uz_football',blocks=[Block(title=t,language='uz',script='Mening tanlovim total 1,5 dan kop') for t in
            ['Augsburg — Bayer','Dortmund — Paderborn','Mayns — Frankfurt']])
        p.intro.script='Salom';p.outro.script='Xayr'
        ss=[segment(0,8,'Augsburg Bayer Dortmund Paderborn Mayns Frankfurt.'),
            segment(20,27,'Telegram kanalimizga sport prognozlari havola tavsifida,'),
            segment(28,32,'endi boshladik Augsburg Bayer.'),
            segment(33,100,'Bu oyinda gol haqida gaplashamiz.'),
            segment(121,125,'Augsburg Bayer tanlovimiz total uchdan kam.'),
            segment(126,134,'Ikkinchi uchrashuv Dortmund Paderborn boladi endi uchrashuvga otsak.'),
            segment(170,175,'Dortmund Paderborn maglub etgan.'),
            segment(240,241,'Uchinchi'),segment(241,248,'bahs Mayns Frankfurt oz maydonida.'),
            segment(260,268,'Frankfurt mavsumida yuqori orinlarni yakunlab.'),
            segment(360,370,'Demir bugun uchta uchrashuvni tahlil qildik birinchi oyin Augsburg Bayer.'),
            segment(400,405,'Xayr.')]
        return p,ss

    def test_merged_promo_does_not_swallow_first_match(self):
        p,ss=self.sample();bounds,tg,_=sections(p,ss)
        self.assertEqual(bounds,[0,30,126,240,360,405])
        self.assertLessEqual(tg[0][1],29)

    def test_script_markers_do_not_change_spoken_boundaries(self):
        p,ss=self.sample();expected=sections(p,ss)[0]
        for i,b in enumerate(p.blocks,1):b.script=f'Разбор{i}\n'+b.script
        self.assertEqual(sections(p,ss)[0],expected)

    def test_merged_previous_pick_and_next_announcement(self):
        p,ss=self.sample()
        ss[4:6]=[segment(121,134,'Augsburg Bayer tanlovimiz total kam. Ikkinchi uchrashuv Dortmund Paderborn boladi.')]
        bounds,_,_=sections(p,ss)
        words=ss[4]['words'];transition=next(w['start'] for w in words if w['word']=='Ikkinchi')
        self.assertEqual(bounds[2],transition)

    def test_club_season_finish_is_not_an_episode_recap(self):
        self.assertFalse(recap_cue('Jamoa mavsumni yuqori orinlarda yakunlab yaxshi oynadi.'))
        self.assertTrue(recap_cue('Demir bugun uchta uchrashuvni tahlil qildik.'))

    def test_promo_without_transition_keeps_existing_end(self):
        ss=[segment(10,15,'Telegram kanalimizda prognozlar. Havola tavsifida.')]
        spans=telegram_spans(ss[0]['words'])
        self.assertEqual(spans,[(10,15)])
