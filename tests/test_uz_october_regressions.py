import unittest
from hockey_editor.uz_structure import parse
from hockey_editor.timeline import Card, Plan
from hockey_editor.card_schedule import exclusive
from hockey_editor.editing import validate_plan
from hockey_editor.model import EventRequest, EventSelection, MatchSource
from hockey_editor.goals import propose, restore_archive_decisions


class UzOctoberTests(unittest.TestCase):
    def test_single_declared_pair_with_narrative_sections(self):
        intro,blocks,outro=parse("ARSENAL — CHELSEA\nSalom do'stlar.\nBoshladik!\nBIRINCHI QISM — UY MAYDONIDAGI IMKONIYATLAR\nArsenal uyda kuchli.\nIKKINCHI QISM — SAFARDAGI IMKONIYATLAR\nChelsea hujum qiladi.\nUCHINCHI QISM — TAKTIK KURASH\nMarkazdagi kurash muhim.\nBESHINCHI QISM — ASOSIY TANLOV\nMening tanlovim total 3,5 dan kam.\nYAKUNIY XULOSA\nXayr.",'football')
        self.assertEqual([b.title for b in blocks],['Arsenal — Chelsea'])
        self.assertIn('Salom',intro.script)
        self.assertIn('Chelsea hujum',blocks[0].script)
        self.assertIn('3,5',blocks[0].script)
        self.assertNotIn('QISM',blocks[0].script)
        self.assertEqual(outro.script,'Xayr.')

    def test_real_second_fixture_not_lost(self):
        _,blocks,_=parse('Salom.\nARSENAL — CHELSEA\nBIRINCHI QISM — TAKTIKA\nArsenal kuchli.\nROMA — MILAN\nIKKINCHI QISM — TAKTIKA\nRoma kuchli.','football')
        self.assertEqual(len(blocks),2)

    def test_spoken_sentence_about_section_is_preserved(self):
        _,blocks,_=parse('ARSENAL — CHELSEA\nBirinchi qism muhim.','football')
        self.assertIn('Birinchi qism muhim.',blocks[0].script)

    def test_declared_pairs_override_mixed_alphabet_ordinal_heading(self):
        a,blocks,z=parse('ARSENAL — CHELSEA\nROMA — MILAN\nSalom.\nARSENAL — CHELSEA\nBirinchi uchrashuv — Arsenal va Chelsea.\nTahlil.\nIKКINCHI UCHRASHUV — ROMA VA MILAN\nRoma — Milan.\nIkkinchi tahlil.\nYAKUN\nXayr.','football')
        self.assertEqual([b.title.casefold() for b in blocks],['arsenal — chelsea','roma — milan'])
        self.assertIn('Birinchi uchrashuv',blocks[0].script)
        self.assertEqual(a.script,'Salom.')

    def test_animation_rounding_and_saved_recovery(self):
        card=Card(45.366666666666674,50.36666666666667,'ТЕЛЕГРАМ','Telegram',asset='promo.mov')
        cards,_=exclusive([card])
        self.assertEqual(cards[0].source_in,0)
        cards[0].source_in=-7.105427357601002e-15
        plan=Plan(0,51,[(0,51)],[],[],cards,[],51)
        validate_plan(plan,check_files=False)
        self.assertEqual(cards[0].source_in,0)
        cards[0].source_in=-.1
        with self.assertRaisesRegex(ValueError,'анимации'):validate_plan(plan,check_files=False)

    def test_missing_source_is_one_review_not_fifty_sentences(self):
        source=MatchSource('game.mp4','Arsenal','Chelsea',sport='football',id='s')
        requests=[EventRequest('s',f'Phrase {i}',kind='play') for i in range(50)]
        scans={'s':{'signature':'v1','candidates':[]}}
        found=propose(requests,scans,[source])
        self.assertEqual(len(found),1)
        found[0].skipped=True
        timed=[EventRequest('s',f'Recognized clause {i}',kind='play') for i in range(12)]
        restore_archive_decisions(timed,found,scans)
        self.assertTrue(all(e.skipped for e in propose(timed,scans,[source])))

    def test_approved_selection_survives_proposal(self):
        source=MatchSource('game.mp4','Arsenal','Chelsea',sport='football',id='s')
        choice=EventSelection('manual',5,10,7,'v1',accepted=True)
        old=EventRequest('s','Same phrase',kind='play',selection=choice)
        new=EventRequest('s','Same phrase',kind='play')
        scans={'s':{'signature':'v1','candidates':[]}}
        restore_archive_decisions([new],[old],scans)
        result=propose([new],scans,[source])
        self.assertEqual(result[0].selection,choice)

    def test_new_valid_archive_not_hidden_by_previous_missing_decision(self):
        previous=EventRequest('s','Old clause',kind='play',skipped=True)
        new=EventRequest('s','New clause',kind='play')
        restore_archive_decisions([new],[previous],{'s':{'candidates':[{'kind':'play','confidence':.9}]}})
        self.assertFalse(new.skipped)

    def test_exact_goals_remain_independent(self):
        source=MatchSource('game.mp4','Arsenal','Chelsea',sport='football',id='s')
        requests=[EventRequest('s','First goal',score=[1,0]),EventRequest('s','Second goal',score=[2,0])]
        self.assertEqual(len(propose(requests,{'s':{'signature':'v1','candidates':[]}},[source])),2)


if __name__=='__main__':unittest.main()
