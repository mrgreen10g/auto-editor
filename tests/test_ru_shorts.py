import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from hockey_editor.model import Project,Block
from hockey_editor.profiles import apply_profile
from hockey_editor.shorts import parse_ru_script,finish_cards,promo_line_ranges,panel_intervals
from hockey_editor.timeline import Line,Card,Insert,Plan,placements,game_transitions
from hockey_editor.episode import assembly_project,EpisodeEngine
from hockey_editor.editing import validate_plan

class RuShortsTests(unittest.TestCase):
    def test_hook_rival_is_not_the_main_fixture(self):
        text='«Трактор» выиграл у «Сочи» 4:1.\n«Трактор» играл с «Амуром».\nСколько «Трактор» забрасывал «Амуру»?\nОсновной прогноз — индивидуальный тотал «Трактора» меньше 2.5.'
        a,blocks,z=parse_ru_script(text)
        self.assertEqual(blocks[0].title,'Трактор — Амур')
        self.assertEqual(blocks[0].script,text)
        p=Project(blocks=blocks,intro=a,outro=z);apply_profile(p,'ru_hockey_shorts')
        self.assertEqual(assembly_project(p).blocks,blocks)
        self.assertEqual((p.settings.width,p.settings.height),(1080,1920))
        self.assertTrue(all(b.language=='ru' for b in [a,*blocks,z]))
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host.mov';host.touch();p.host=str(host)
            EpisodeEngine(p,0,Path(d)/'cache',threading.Event()).validate_all()
            p.save(Path(d)/'project.hockeyproj')
            saved=Project.load(Path(d)/'project.hockeyproj')
            self.assertEqual(saved.profile,'ru_hockey_shorts');self.assertEqual(saved.blocks[0].title,blocks[0].title)

    def test_replacing_telegram_invalidates_cached_analysis(self):
        from hockey_editor.editing import project_edit_key
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.touch()
            tg=Path(d)/'tg';tg.write_bytes(b'first')
            p=Project(host=str(host),profile='ru_hockey_shorts',assets={'telegram':str(tg)})
            before=project_edit_key(p,0)
            tg.write_bytes(b'replacement promo')
            self.assertNotEqual(before,project_edit_key(p,0))

    def test_separate_team_paragraphs_exclude_past_opponents(self):
        text='Трактор сейчас в хорошей форме.\nПоследняя игра — 2:1 в Минске.\nНо списывать Амур здесь нельзя.\nПосле поражения от Сочи Амур обыграл Ладу.\nЕсли Амур сыграет дисциплинированно, будет сложно.\nОсновной прогноз — победа Трактора с учетом овертайма.'
        self.assertEqual(parse_ru_script(text)[1][0].title,'Трактор — Амур')

    def test_optional_pair_heading_is_normalized_for_alignment(self):
        blocks=parse_ru_script('Матч: Трактор—Амур\nМой прогноз — победа Трактора.')[1]
        self.assertEqual(blocks[0].script.splitlines()[0],blocks[0].title)
        self.assertNotIn('Матч:',blocks[0].script)

    def test_any_number_of_explicit_fixtures(self):
        text='Привет, сегодня несколько встреч.\nТрактор — Амур\nМой прогноз — победа Трактора.\nСКА — ЦСКА\nМой прогноз — победа СКА.\nЛада — Сочи\nМой прогноз — тотал меньше 5.5.'
        a,b,z=parse_ru_script(text)
        self.assertEqual(len(b),3);self.assertIn('Привет',a.script);self.assertEqual(z.script,'')

    def test_ambiguous_script_requires_pair_instead_of_guess(self):
        with self.assertRaisesRegex(ValueError,'однозначно'):parse_ru_script('Сегодня будет интересный матч. Основной прогноз — тотал больше 5.5.')

    def test_ru_cards_include_grouped_stats_pick_score_and_middle_promo(self):
        block=Block(title='Трактор — Амур',language='ru')
        texts=['Трактор забрасывал по матчам:','Одну.','Ноль.','Две.',
               'Дополнительные ставки публикую в телеграм-канале.','Ссылка находится в описании.',
               'Основной прогноз — индивидуальный тотал Трактора меньше 2.5.',
               'Сейчас дают примерно 1.82.','По счёту жду 2:1 или 3:1.']
        block.script='\n'.join(texts);lines=[Line(t,i*3,(i+1)*3) for i,t in enumerate(texts)]
        p=Project(profile='ru_hockey_shorts',blocks=[block],assets={'telegram':'tg.mp4'})
        clips,cards,_=placements(block,lines,{},27,shorts=True)
        clips=[Insert('game',10,20,0,'game',source_max=20)]
        cards,clips=finish_cards(p,block,lines,cards,clips,27)
        tg=next(c for c in cards if c.title=='ТЕЛЕГРАМ')
        self.assertEqual((tg.start,tg.end,tg.line),(12,18,-1))
        self.assertTrue(all(c.end<=12 or c.start>=18 for c in clips))
        self.assertTrue(any('1 · 0 · 2' in c.text for c in cards))
        self.assertTrue({'ПРОГНОЗ','ОЖИДАЕМЫЙ СЧЁТ','КОЭФФИЦИЕНТ ИЗ РАЗБОРА'}<={c.title for c in cards})
        validate_plan(Plan(0,27,[(0,27)],lines,clips,cards,[],27),check_files=False)

    def test_only_telegram_changes_to_fullscreen(self):
        from hockey_editor.shorts_graphics import asset_filter
        with patch('hockey_editor.media.probe',return_value={'duration':10}):
            tg=Card(0,3,'ТЕЛЕГРАМ','tg',asset='tg')
            sub=Card(0,3,'ПОДПИСКА','sub',asset='sub')
            self.assertIn('scale=720:1280',asset_filter(tg)[0])
            self.assertIn('scale=720:404',asset_filter(sub)[0])
        plan=Plan(0,3,[(0,3)],[],[],[sub],[],3)
        self.assertEqual(panel_intervals(plan),[(0,3)])

    def test_promo_requires_asset_and_not_youtube_subscription(self):
        lines=[Line('Канал интересный. Подписывайтесь!',0,3)]
        self.assertEqual(promo_line_ranges(lines),[])
        with self.assertRaisesRegex(ValueError,'Telegram'):
            finish_cards(Project(),Block(),[Line('Мой телеграм-канал.',0,3)],[],[],3)

    def test_uz_promo_survives_unrecognized_service_name(self):
        from hockey_editor.shorts import promo_spans
        block=Block(script='Aytgancha, prognozlarim bor. Telegram kanaliga joylayman. Havola tavsifda.',language='uz')
        p=Project(blocks=[block]);p.intro.script=p.outro.script=''
        words=[];t=0
        for phrase in ['Aytgancha, prognozlarim bor.','Ularni kanaliga joylayman.','Havola tavsifda.']:
            for token in phrase.split():
                words.append(dict(word=token,start=t,end=t+.4));t+=.5
        spans=promo_spans(p,[dict(words=words,start=0,end=t,text='')],[(0,0),(0,t),(t,t)],[])
        self.assertEqual(spans,[(0,t-.1)])

    def test_fullscreen_promo_does_not_move_presenter_or_bridge_game(self):
        plan=Plan(0,8,[(0,8)],[],[Insert('a',1,3,0,'a'),Insert('b',3.2,5,0,'b')],[Card(3,3.2,'ТЕЛЕГРАМ','tg',asset='tg')],[],8)
        self.assertEqual(panel_intervals(plan),[(1,3),(3.2,5)])
        self.assertEqual([v[1] for v in game_transitions(plan)],[0,0])

if __name__=='__main__':unittest.main()
