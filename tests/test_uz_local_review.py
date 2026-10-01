"""Synthetic regression cases; no user recording or script is included."""
import tempfile,unittest
from pathlib import Path
from test_uz_speech import project,sample,segment
from hockey_editor.uz_speech import prepare,intro_sequence_spans
from hockey_editor.uz_forecasts import match_forecasts,features
from hockey_editor.framing import forecast_text


class LocalReviewTests(unittest.TestCase):
    def test_one_missing_pick_does_not_downgrade_other_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            host=Path(tmp)/'host';host.touch();p=project(host);data=sample()
            reference=project(host);prepare(reference,sample(),review=True,duration=204)
            expected={b.title:sum(bool(c.get('needs_review')) for c in b.speech_cards.values()) for b in [reference.intro,*reference.blocks,reference.outro]}
            data[7]=segment(150,158,'Bu uchrashuv haqida fikrlarimiz shunday.')
            prepare(p,data,review=True,duration=204)
            for b in [p.intro,*p.blocks[:2],p.outro]:
                self.assertFalse(any(v.get('review_reason') for v in b.asr_lines))
                self.assertEqual(sum(bool(v.get('needs_review')) for v in b.speech_cards.values()),expected[b.title],b.title)
            disputed=[v for v in p.blocks[2].speech_cards.values() if v.get('needs_review')]
            self.assertEqual(len(disputed),1)
            self.assertEqual(disputed[0]['title'],'ПРОГНОЗ')

    def test_missing_recap_preserves_other_recap_picks(self):
        p=project('host');data=sample();refs={b.uid:forecast_text(b) for b in p.blocks}
        data[10]=segment(188,194,'Bugungi sport yangiliklari mana shunday.')
        got=match_forecasts(data,170,195,p.blocks,refs,partial=True)
        self.assertIsNotNone(got[0]);self.assertIsNotNone(got[1]);self.assertIsNone(got[2])
        with self.assertRaises(ValueError):match_forecasts(data,170,195,p.blocks,refs)

    def test_spoken_halves_split_decimals_and_suffixes(self):
        for text,expected in [('total biryamdan ko‘p',1.5),('total ikki yarmtana kam',2.5),('total 4 ,5 tanan kam',4.5),('talnoyimiz bir yamtidan ko‘p total',1.5)]:
            with self.subTest(text=text):self.assertEqual(features(text)['value'],expected)

    def test_rejected_threshold_does_not_capture_later_choice(self):
        p=project('host');b=p.blocks[2];refs={b.uid:forecast_text(b)}
        data=[segment(10,20,"Total ikki yarmtana ko'p baland variant, talnoyimiz bir yamtidan ko'p total bo'yicha.")]
        got=match_forecasts(data,0,25,[b],refs,False)[0]
        self.assertGreater(got['start'],10)
        self.assertEqual(features(got['text'])['value'],1.5)
        self.assertFalse(got['needs_review'])

    def test_low_confidence_numeric_pick_stays_reviewable(self):
        p=project('host');b=p.blocks[2];data=[segment(1,6,"Mening tanlovim total 1,5 dan ko'p gol.")]
        for w in data[0]['words']:w['probability']=.3 if w['word']=='1,5' else .98
        self.assertTrue(match_forecasts(data,0,10,[b],{b.uid:forecast_text(b)},False)[0]['needs_review'])

    def test_intro_uses_ordered_fixture_list_after_hook(self):
        p=project('host')
        data=[segment(0,2,'Borussia Dortmund Paderborn haqida.'),sample()[0]]
        words=[w for s in data for w in s['words']]
        spans=intro_sequence_spans(p.blocks,words)
        self.assertEqual(len(spans),3)
        self.assertGreaterEqual(spans[1][0],2)
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(spans,spans[1:])))

    def test_old_pending_task_does_not_survive_without_its_card(self):
        from hockey_editor.timeline import Plan,Line,Card
        from hockey_editor.review import preserve_edits,pending
        from dataclasses import asdict
        card=Card(1,3,'СТАТИСТИКА','Old',review_id='id')
        old=Plan(0,10,[(0,10)],[Line('text',0,10)],[],[card],[],10,input_key='same')
        old.edit_baseline={'cards':[asdict(card)]}
        old.review_items=[dict(id='id',status='pending')]
        new=Plan(0,10,[(0,10)],[Line('text',0,10)],[],[],[],10,input_key='same')
        preserve_edits(old.to_dict(),new)
        self.assertFalse(pending(new))

    def test_old_deletion_cannot_delete_different_fact_at_same_line_id(self):
        from hockey_editor.timeline import Plan,Line,Card
        from hockey_editor.review import preserve_edits,pending
        from dataclasses import asdict
        oldcard=Card(1,3,'СТАТИСТИКА','Old',review_id='id')
        old=Plan(0,10,[(0,10)],[Line('text',0,10)],[],[],[],10,input_key='same')
        old.edit_baseline={'cards':[asdict(oldcard)]};old.review_items=[dict(id='id',status='deleted')]
        newcard=Card(2,4,'СТАТИСТИКА','New fact',review_id='id')
        new=Plan(0,10,[(0,10)],[Line('text',0,10)],[],[newcard],[],10,input_key='same')
        new.review_items=[dict(id='id',status='pending')]
        preserve_edits(old.to_dict(),new)
        self.assertEqual(new.cards,[newcard]);self.assertEqual(len(pending(new)),1)
