import json,tempfile,threading,unittest
from pathlib import Path
from hockey_editor.top5 import parse_script,facts,events
from hockey_editor.model import Project,Block,MatchSource,EventRequest
from hockey_editor.timeline import Line,Plan,Insert,placements
from hockey_editor.alignment import split_script

SCRIPT='''Топ пять команд. Первое место вас удивит. Всем привет!
На пятом месте СКА. Три победы подряд.
Четвёртый, сам Амур. Команда не проигрывала.
Третье место — Трактор. Семь заброшенных шайб.
Дополнительные прогнозы в Telegram-канале. Ссылка на него находится в шапке профиля.
Вторая — Северсталь. Два поражения подряд.
И вот первое место.
ЦСКА.
Одиннадцать побед подряд. Шестнадцать забитых шайб.
А кого бы вы поставили на первое место? Пишите в комментариях.'''

def timed(block):return [Line(t,i*3,(i+1)*3) for i,t in enumerate(split_script(block.script))]

class TopFiveTests(unittest.TestCase):
    def test_team_ranks_inline_and_split_heading(self):
        for text in (SCRIPT,SCRIPT.replace('\n',' ')):
            intro,blocks,outro=parse_script(text)
            self.assertEqual([(b.top5_rank,b.title) for b in blocks],[(5,'СКА'),(4,'Амур'),(3,'Трактор'),(2,'Северсталь'),(1,'ЦСКА')])
            self.assertIn('вас удивит',intro.script);self.assertIn('кого бы',outro.script)
            self.assertIn('И вот первое место.',blocks[-1].script)

    def test_match_rank_and_qualified_dynamo(self):
        text=SCRIPT.replace('СКА. Три','СКА против «Лады». Три').replace('сам Амур','минское «Динамо»')
        _,blocks,_=parse_script(text)
        self.assertEqual(blocks[0].title,'СКА — Лада');self.assertEqual(blocks[1].title,'Динамо Минск')

    def test_football_identity_and_wrong_sport(self):
        text=SCRIPT
        for a,b in [('ЦСКА','Манчестер Сити'),('СКА','Арсенал'),('Амур','Эвертон'),('Трактор','Брайтон'),('Северсталь','Челси')]:text=text.replace(a,b)
        _,blocks,_=parse_script(text,'football');self.assertEqual(blocks[-1].title,'Манчестер Сити')
        self.assertTrue(all(b.sport=='football' for b in blocks))
        with self.assertRaises(ValueError):parse_script(text,'hockey')

    def test_missing_or_duplicate_place_does_not_silently_drop_blocks(self):
        for text in (SCRIPT.replace('Третье место','Второе место'),SCRIPT.replace('Третье место — Трактор.','Трактор.')):
            with self.assertRaises(ValueError):parse_script(text)

    def test_no_bet_cards_or_missing_bet_review(self):
        from hockey_editor.review import attach,framing_draft
        from hockey_editor.shorts import finish_cards
        intro,blocks,outro=parse_script(SCRIPT);p=Project(profile='ru_hockey_top5_shorts',blocks=blocks,intro=intro,outro=outro,assets={'telegram':'promo.mp4'})
        for b in blocks:
            lines=timed(b);duration=lines[-1].end
            ins,cards,warnings=placements(b,lines,{},duration,shorts=True)
            cards,ins=finish_cards(p,b,lines,cards,ins,duration)
            plan=attach(Plan(0,duration,[(0,duration)],lines,ins,cards,[],duration),b,p)
            self.assertFalse(plan.review_items)
            self.assertFalse(any(c.title=='ПРОГНОЗ' for c in cards))
            self.assertEqual(sum(c.title==f'{b.top5_rank} МЕСТО' for c in cards),1)
            self.assertTrue(any(c.title in ('СТАТИСТИКА','ФАКТ') for c in cards))
        self.assertEqual(framing_draft(p,outro,timed(outro),6),([],[]))

    def test_scores_are_not_shots_and_do_not_become_subtitles(self):
        b=Block(title='СКА — Лада',top5_rank=1,sport='hockey',script='Первое место — СКА против Лады.\n2:1.\n3:1.\n3:2.\nЧетырнадцать шайб.\nДля меня это удивительно.')
        cards=facts(b,timed(b),18)
        self.assertTrue(any(c.text=='2:1 → 3:1 → 3:2' for c in cards))
        self.assertFalse(any('Броски' in c.text or 'удивительно' in c.text for c in cards))

    def test_footage_owned_by_team_or_fixture_and_promo_excluded(self):
        a=MatchSource('a.mp4','Трактор','Амур');b=MatchSource('b.mp4','СКА','Лада')
        _,blocks,_=parse_script(SCRIPT);block=blocks[2];block.match_ids=[a.id,b.id]
        requests=events(block,[a,b]);self.assertTrue(requests)
        self.assertTrue(all(r.source_id==a.id and r.kind=='play' and r.score is None and r.strict_source for r in requests))
        self.assertFalse(any('Telegram' in r.phrase or 'Ссылка' in r.phrase for r in requests))
        block.title='Трактор — Лада';self.assertFalse(events(block,[a,b]))

    def test_no_unrelated_fallback_and_good_play_auto_accepted(self):
        from hockey_editor.goals import propose
        a=MatchSource('a.mp4','СКА','Лада');b=MatchSource('b.mp4','Амур','Трактор')
        candidate=dict(id='play1',start=1,end=5,time=3,confidence=.9,kind='play',score=None,before=None,note='game')
        e=EventRequest(a.id,'Три победы подряд',kind='play',strict_source=True)
        scans={b.id:dict(signature='test',candidates=[candidate])}
        propose([e],scans,[a,b],True);self.assertIsNone(e.selection)
        scans[a.id]=scans[b.id];propose([e],scans,[a,b],True);self.assertTrue(e.selection.accepted)

    def test_telegram_owns_link_sentence_and_replaces_footage(self):
        from hockey_editor.shorts import finish_cards
        _,blocks,_=parse_script(SCRIPT);b=blocks[2];lines=timed(b);duration=lines[-1].end
        p=Project(profile='ru_hockey_top5_shorts',assets={'telegram':'promo.mp4'})
        cards,inserts=finish_cards(p,b,lines,facts(b,lines,duration),[Insert('match.mp4',0,duration,0,'test')],duration)
        promo=next(c for c in cards if c.title=='ТЕЛЕГРАМ')
        self.assertEqual(promo.end,lines[-1].end)
        self.assertFalse(any(c.start<promo.end and c.end>promo.start for c in inserts))

    def test_folder_import_single_team_and_roundtrip(self):
        from hockey_editor.folder_import import build_import
        from hockey_editor.profiles import apply_profile
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();host=root/'host.mp4';host.touch();script=root/'text.txt';script.write_text(SCRIPT,encoding='utf-8')
            folder=root/'СКА';folder.mkdir();(folder/'СКА — Лада.mp4').touch()
            p=Project();apply_profile(p,'ru_hockey_top5_shorts')
            p,_,_=build_import(p,root,host,script);self.assertEqual(len(p.blocks[0].match_ids),1)
            p.blocks[0].events=events(p.blocks[0],p.matches)
            file=root/'p.json';p.save(file);q=Project.load(file)
            self.assertEqual([b.top5_rank for b in q.blocks],[5,4,3,2,1]);self.assertTrue(q.blocks[0].events[0].strict_source)
            q.validate();self.assertEqual((q.settings.width,q.settings.height),(1080,1920))

    def test_rank_and_fact_graphics_fit_portrait(self):
        from hockey_editor.graphics import card_image
        from PIL import Image
        _,blocks,_=parse_script(SCRIPT)
        with tempfile.TemporaryDirectory() as d:
            for b in blocks:
                for i,c in enumerate(facts(b,timed(b),40)):
                    p=Path(d)/f'{b.uid}-{i}.png';x,y=card_image(c,p,profile='ru_hockey_top5_shorts')
                    with Image.open(p) as im:self.assertLessEqual(x+im.width,720);self.assertLessEqual(y+im.height,1280)
