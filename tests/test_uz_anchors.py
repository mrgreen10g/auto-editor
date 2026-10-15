import unittest
from hockey_editor.model import Block
from hockey_editor.uz_anchors import script_ranges
from hockey_editor.card_schedule import exclusive
from hockey_editor.timeline import Card
from test_uz_speech import segment


class AnchorTests(unittest.TestCase):
    def test_intro_fixture_list_does_not_steal_analysis(self):
        text='Arsenal uy maydonida hujum qiladi lekin Chelsea himoyada juda yaxshi ishlaydi.'
        ending='Bugungi ikki uchrashuv haqidagi fikrlarimiz shunday endi tanlovlarni yana takrorlaymiz.'
        blocks=[Block(kind='intro',script='Salom Arsenal Chelsea.'),Block(script=text),Block(kind='outro',script=ending)]
        data=[segment(0,5,'Arsenal Chelsea bugun juda qiziqarli uchrashuv.'),segment(20,30,text),segment(60,70,ending)]
        self.assertEqual(script_ranges(blocks,data,75),[(0.,20.),(20.,60.),(60.,75)])

    def test_partial_match_cannot_invent_complete_boundaries(self):
        blocks=[Block(kind='intro',script='Salom'),Block(script='a b c d e f g h i j'),Block(kind='outro',script='Unrelated ending words do not match this sample at all')]
        self.assertIsNone(script_ranges(blocks,[segment(10,20,'a b c d e f g h i j')],30))

    def test_repeated_evidence_is_ambiguous(self):
        text='bir ikki uch tort besh olti yetti sakkiz boshqa sozlar'
        blocks=[Block(kind='intro',script='Salom'),Block(script=text)]
        self.assertIsNone(script_ranges(blocks,[segment(10,20,text),segment(40,50,text)],60))


class CardScheduleTests(unittest.TestCase):
    def test_priorities_stay_within_original_speech(self):
        original=[Card(0,5,'РАЗБОР МАТЧА','Pair'),Card(2,9,'СТАТИСТИКА','Facts'),Card(6,12,'ПРОГНОЗ','Bet')]
        cards,omitted=exclusive(original)
        self.assertEqual([(c.start,c.end) for c in cards],[(0,5),(5,6),(6,12)])
        self.assertFalse(omitted);self.assertEqual(original[1].start,2)
        self.assertTrue(all(a.end<=b.start for a,b in zip(cards,cards[1:])))

    def test_hidden_fact_is_reported_not_moved_to_other_speech(self):
        cards,omitted=exclusive([Card(0,10,'ПРОГНОЗ','Bet'),Card(3,6,'СТАТИСТИКА','Fact')])
        self.assertEqual(len(cards),1);self.assertEqual(omitted[0].text,'Fact')

    def test_trimmed_asset_updates_source_offset(self):
        cards,_=exclusive([Card(0,3,'ТЕЛЕГРАМ','',asset='a'),Card(1,8,'ПОДПИСКА','',asset='b',source_in=4)])
        self.assertEqual(cards[1].source_in,6)
