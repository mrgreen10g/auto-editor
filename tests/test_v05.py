"""Multi-block persistence, real media joins and revised editing rules."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from hockey_editor.model import Project,Block
from hockey_editor.timeline import Plan,Line,Card,Insert,format_time,parse_time,game_transitions
from hockey_editor.episode import combine,store_episode,saved_episode,EpisodeEngine
from hockey_editor.editing import saved_plan,store_plan,validate_plan
from hockey_editor.media import run,probe
from hockey_editor.graphics import card_image
from hockey_editor.alignment import bounded_dtw


def block_plan(start,title,path=None):
    return Plan(start,start+8,[(0,3),(4,8)],[Line(title,0,3),Line('Мой выбор',3,7)],
                [Insert(str(path),3,5,1,'Игра',source_max=7)] if path else [],
                [Card(0,3,'РАЗБОР МАТЧА',title,0),Card(5,7,'ПРОГНОЗ','Лада +2',1)],[],7,0)


class V05Tests(unittest.TestCase):
    def test_episode_restores_with_noncanonical_source_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'nested').mkdir();(root/'game.mp4').touch()
            media=root/'nested'/'..'/'game.mp4'
            p=Project(host=str(media),blocks=[Block(title='A'),Block(title='B')],whole_episode=True)
            merged=combine(p,[block_plan(0,'A',media),block_plan(12,'B',media)])
            store_episode(p,merged);p.save(root/'saved.hockeyproj')
            restored=saved_episode(Project.load(root/'saved.hockeyproj'))
            self.assertIsNotNone(restored)
            self.assertEqual(len(restored.inserts),2)

    def test_time_input_and_legacy_seconds(self):
        self.assertEqual(format_time(649.9),'10:49.90')
        for value in ('10:49.90','649.9','00:10:49,90'):self.assertAlmostEqual(parse_time(value),649.9)
        self.assertEqual(format_time(59.999),'01:00.00')
        for value in ('NaN','-1','10:99','1.5:02','1:2:3:4','inf'):
            with self.assertRaises(ValueError):parse_time(value)

    def test_two_to_four_blocks_keep_order_and_distinct_sources(self):
        for n in (2,3,4):
            p=Project(blocks=[Block(title=f'Матч {i}') for i in range(n)])
            plans=[block_plan(10+i*12,b.title) for i,b in enumerate(p.blocks)]
            merged=combine(p,plans)
            self.assertEqual(merged.duration,7*n);self.assertEqual(len(merged.sections),n)
            self.assertEqual([l.start for l in merged.lines],[v for i in range(n) for v in (i*7,i*7+3)])
            self.assertEqual([c.start for c in merged.cards if c.title=='СМЕНА МАТЧА'],[i*7 for i in range(1,n)])
            self.assertTrue(all(a[1]<=b[0] for a,b in zip(merged.keep,merged.keep[1:])))
            self.assertEqual([c.line for c in merged.cards if c.title=='ПРОГНОЗ'],[i*2+1 for i in range(n)])

    def test_saved_global_edits_roundtrip_and_local_invalidation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);media=root/'game.mp4';media.touch()
            p=Project(host=str(media),blocks=[Block(title=str(i)) for i in range(3)],whole_episode=True)
            plans=[block_plan(i*12,b.title,media) for i,b in enumerate(p.blocks)]
            merged=combine(p,plans);merged.inserts[1].source_in=2;merged.cards[3].text='Новый выбор'
            store_episode(p,merged);p.save(root/'test.hockeyproj')
            loaded=Project.load(root/'test.hockeyproj');restored=saved_episode(loaded)
            self.assertIsNotNone(restored);self.assertEqual(restored.inserts[1].source_in,2)
            self.assertEqual(saved_plan(loaded,1).inserts[0].source_in,2)
            loaded.blocks[2].script+=' Изменение'
            self.assertIsNone(saved_episode(loaded));self.assertIsNotNone(saved_plan(loaded,1))
            self.assertIsNone(saved_plan(loaded,2))
            invalid=copy.deepcopy(merged);invalid.inserts[0].end=8
            with self.assertRaises(ValueError):validate_plan(invalid)

    def test_old_project_keeps_manual_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=Project(blocks=[Block(title='СКА — Лада')]);plan=block_plan(0,'СКА — Лада')
            store_plan(p,0,plan);p.save(root/'old.hockeyproj')
            data=json.loads((root/'old.hockeyproj').read_text());data['version']=4
            data.pop('episode_plan');data.pop('episode_key');data.pop('whole_episode');data['blocks'][0].pop('uid')
            (root/'old.hockeyproj').write_text(json.dumps(data))
            old=Project.load(root/'old.hockeyproj');self.assertIsNotNone(saved_plan(old,0))
            self.assertFalse(old.whole_episode)

    def test_padding_is_not_repeated_and_reversed_blocks_rejected(self):
        p=Project(blocks=[Block(),Block()])
        a=Plan(0,8,[(0,8)],[Line('a',.2,7.8)],[],[],[],8)
        b=Plan(7.8,16,[(0,8.2)],[Line('b',.3,8)],[],[],[],8.2)
        merged=combine(p,[a,b]);self.assertEqual(merged.duration,16)
        self.assertEqual(merged.keep,[(0,8),(8,16)])
        with self.assertRaises(ValueError):combine(p,[b,a])

    def test_adjacent_games_join_but_blocks_do_not(self):
        p=Plan(0,12,[(0,12)],[],[Insert('x',1,3,0,'a'),Insert('x',3.2,5,0,'b'),Insert('x',7,9,0,'c')],[],[],12)
        items=list(game_transitions(p));self.assertAlmostEqual(items[0][1],.2)
        self.assertTrue(items[0][3]);self.assertTrue(items[1][2]);self.assertFalse(items[1][3])
        p.sections=[{'start':3.2}];self.assertFalse(list(game_transitions(p))[0][3])

    def test_large_forecast_and_smaller_team_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'card.png';x,y=card_image(Card(0,5,'ПРОГНОЗ','Лада\nФора (+2)'),p)
            with Image.open(p) as im:self.assertGreater(im.width,650);self.assertLess(im.height,285)
            self.assertGreater(y,400)
            x,y=card_image(Card(0,5,'РАЗБОР МАТЧА','СКА — Лада'),p)
            with Image.open(p) as im:self.assertLess(im.width,930);self.assertLess(im.height,215)

    def test_bounded_alignment_retains_location(self):
        rng=np.random.default_rng(31);q=rng.normal(size=(60,13)).astype('f');q/=np.linalg.norm(q,axis=1,keepdims=True)
        source=np.vstack([q[::-1],q,q[::-1]])
        path,_=bounded_dtw(source,q,limit=2700)
        self.assertLess(abs(path[0]-60),3);self.assertLess(abs(path[-1]-119),3)

    def test_episode_engine_advances_search_floor_and_restores_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            host=Path(tmp)/'host';host.touch()
            p=Project(host=str(host),blocks=[Block(title=str(i),script='Длинный текст для проверки последовательного поиска.') for i in range(3)])
            plans=[block_plan(i*12,b.title) for i,b in enumerate(p.blocks)];floors=[]
            def analyze(engine,source_floor=0):floors.append(source_floor);return plans[engine.index]
            with patch('hockey_editor.episode.Engine.analyze',analyze):
                result=EpisodeEngine(p,0,Path(tmp)/'cache',threading.Event()).analyze()
            self.assertEqual(floors,[0,7,19]);self.assertEqual(len(result.sections),3)
            with patch('hockey_editor.episode.Engine.analyze',side_effect=AssertionError('Should restore')):
                self.assertEqual(EpisodeEngine(p,0,Path(tmp)/'cache',threading.Event()).analyze().duration,21)

    def test_real_combined_export_continuity_and_divider(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);host=d/'host.mp4';game=d/'game.mp4';music=d/'bed.wav'
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=20','-f','lavfi','-i','sine=f=240:r=48000:d=20','-t','20','-c:v','libx264','-c:a','aac',host])
            run(['-y','-f','lavfi','-i','color=c=red:s=320x180:r=30:d=6','-c:v','libx264',game])
            run(['-y','-f','lavfi','-i','sine=f=600:r=48000:d=3',music])
            p=Project(host=str(host),music=str(music),blocks=[Block(title='СКА — Лада',script='Достаточно длинный сценарий первого разбора.'),Block(title='ЦСКА — Торпедо',script='Достаточно длинный сценарий второго разбора.')])
            p.settings.zoom=False;p.settings.auto_rotate=False
            a=Plan(1,9,[(0,8)],[Line('Первая речь',0,8)],[Insert(str(game),2,4,0,'a',source_max=6),Insert(str(game),4.2,6,1,'b',source_max=6)],[],[],8,0)
            b=Plan(12,20,[(0,8)],[Line('Вторая речь',0,8)],[],[Card(5,8,'ПРОГНОЗ','Торпедо +1,5')],[],8,0)
            merged=combine(p,[a,b]);engine=EpisodeEngine(p,0,d/'cache',threading.Event());engine.render(merged,d/'out.mp4',draft=True)
            self.assertAlmostEqual(probe(d/'out.mp4')['duration'],16,delta=.08)
            for t in (3.97,4.03,4.17,4.23):
                run(['-y','-ss',t,'-i',d/'out.mp4','-frames:v','1',d/'frame.png'])
                with Image.open(d/'frame.png') as im:
                    r,g,blue=im.convert('RGB').getpixel((320,180));self.assertGreater(r,200);self.assertLess(blue,40)
            run(['-y','-ss',8.4,'-i',d/'out.mp4','-frames:v','1',d/'frame.png'])
            with Image.open(d/'frame.png') as im:self.assertLess(im.convert('RGB').getpixel((20,20))[2],80)
            run(['-y','-i',d/'out.mp4','-vn','-ac','1','-c:a','pcm_s16le',d/'audio.wav'])
            from scipy.io import wavfile
            sr,wav=wavfile.read(d/'audio.wav')
            for t in (7.95,8,8.05):self.assertGreater(np.sqrt(np.mean(wav[int(t*sr):int((t+.04)*sr)].astype(float)**2)),100)

    def test_automatic_alignment_excludes_repeated_outro(self):
        from hockey_editor.alignment import synthesize,split_script
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);cancel=threading.Event()
            blocks=[Block(title='СКА — Лада',script='СКА — Лада. Петербург выиграл в овертайме. Лада создавала много моментов. Мой выбор — Лада с форой плюс два.'),
                    Block(title='ЦСКА — Торпедо',script='ЦСКА — Торпедо. Нижний Новгород начал сезон уверенно. Жду упорную борьбу до конца. Мой выбор — Торпедо с форой плюс полторы шайбы.')]
            texts=['Добрый день, сегодня разберём два матча.']+sum([split_script(b.script) for b in blocks],[])+[
                'Повторю прогнозы. Мой выбор — Лада с форой плюс два. Мой выбор — Торпедо с форой плюс полторы шайбы. До встречи.']
            anchors=synthesize(texts,d/'voice.wav',cancel)
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30','-i',d/'voice.wav','-shortest','-c:v','libx264','-c:a','aac',d/'host.mp4'])
            p=Project(host=str(d/'host.mp4'),blocks=blocks,whole_episode=True);p.settings.auto_rotate=False
            plan=EpisodeEngine(p,0,d/'cache',cancel).analyze()
            self.assertEqual(len(plan.sections),2)
            self.assertAlmostEqual(plan.sections[0]['source_start'],anchors[1],delta=.5)
            self.assertAlmostEqual(plan.sections[1]['source_start'],anchors[5],delta=.5)
            self.assertLess(plan.sections[-1]['source_end'],anchors[-1]+.4)
            # The boundary uses the beginning of the next spoken section, not
            # the previous section's analysis padding over the next first word.
            first_end=plan.sections[0]['source_start']+plan.sections[0]['keep'][-1][1]
            self.assertAlmostEqual(first_end,anchors[5],delta=.15)
