import copy,tempfile,unittest
from pathlib import Path
from dataclasses import asdict
from PIL import Image,ImageChops
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.timeline import Plan,Line,Card,keep_ranges
from hockey_editor.framing import split_full_script
from hockey_editor.team_names import ru_identity
from hockey_editor.event_rules import suggested_names,requests_for
from hockey_editor.graphics import block_teams
from hockey_editor.ru_speech import tokens,align_episode
from hockey_editor.speech_boundaries import first_analysis_start
from hockey_editor.speech_cleanup import remove_retakes,subtract_ranges
from hockey_editor.review import attach,pending,remove_old_subtitles,describe_card
from hockey_editor.preferences import save_preset,apply_preset,presets,remember_folder,restore_folder
from hockey_editor.logos import assign
from hockey_editor.live_cards import base_key,base_plan,LiveCards


def segment(text,start=0,step=.4):
    words=[dict(word=w,start=start+i*step,end=start+(i+1)*step-.05) for i,w in enumerate(text.split())]
    return dict(text=text,start=words[0]['start'],end=words[-1]['end'],words=words)


class WorkflowTests(unittest.TestCase):
    def test_nhl_all_clubs_unique_and_russian_aliases(self):
        from hockey_editor.nhl import NHL,CODES
        self.assertEqual(len(NHL),32)
        for club,code in zip(NHL,CODES):
            self.assertEqual(ru_identity(club),club)
            self.assertEqual(ru_identity(code),club)
        for alias,expected in [('Нью-Джерси','New Jersey Devils'),('Рейнджерс','New York Rangers'),('Айлендерс','New York Islanders'),('Монреаль','Montreal Canadiens'),('Тампа-Бэй','Tampa Bay Lightning')]:self.assertEqual(ru_identity(alias),expected)
        self.assertIsNone(ru_identity('New York'));self.assertIsNone(ru_identity('Нью-Йорк'))
        self.assertEqual(tokens('Бостон'),tokens('Boston Bruins'))

    def test_hyphenated_city_not_fixture_separator(self):
        self.assertEqual(block_teams('Нью-Джерси — Сент-Луис'),['Нью-Джерси','Сент-Луис'])
        self.assertEqual(block_teams('СКА-ЦСКА'),['СКА','ЦСКА'])
        self.assertEqual(block_teams('Нью-Джерси'),['Нью-Джерси',''])

    def test_nhl_import_varied_recap_and_numbered_headings(self):
        for cue in ('Подведём итоги.','Напомню мои ставки.','Повторим три выбора.','Итоги'):
            text='Привет! Сегодня хоккей НХЛ.\n1. Boston Bruins — Montreal Canadiens\nБостон выиграл четыре матча. Мой прогноз — тотал больше 5.5.\nНью-Джерси — Сент-Луис\nКоманды играют уверенно. Мой выбор — победа гостей.\n'+cue+'\nПовтор ставок и подписка.'
            intro,blocks,outro=split_full_script(text)
            self.assertEqual(len(blocks),2);self.assertTrue(outro.startswith(cue));self.assertIn('НХЛ',intro)
            self.assertEqual(blocks[1][0],'Нью-Джерси — Сент-Луис')

    def test_nhl_historical_source_not_confused_with_current_fixture(self):
        a=MatchSource('a','Boston Bruins','Montreal Canadiens');b=MatchSource('b','Boston Bruins','New York Rangers')
        block=Block(title='Boston Bruins — Montreal Canadiens',script='Бостон обыграл Рейнджерс 3:2. Мой выбор — тотал больше пяти с половиной.',match_ids=[a.id,b.id])
        requests=requests_for(block,[a,b])
        self.assertEqual(requests[0].source_id,b.id)

    def test_intro_body_anchor_without_fixed_transition(self):
        intro=Block(kind='intro',script='Всем привет друзья сегодня Бостон и Монреаль встретятся вечером. Нас ждёт интересный хоккей.')
        analysis=Block(title='Boston Bruins — Montreal Canadiens',script='Boston Bruins — Montreal Canadiens\nХозяева набрали отличный ход и выиграли четыре последних матча подряд. Гости пока ищут свою игру.')
        speech=[segment(intro.script),segment('Бостон Монреаль. '+analysis.script.split('\n')[1],20)]
        boundary=first_analysis_start([intro,analysis],speech)
        self.assertEqual(boundary,20)

    def test_false_start_removed_corrected_take_and_recap_preserved(self):
        line='Сегодня хозяева играют очень уверенно и победили в четырёх матчах.'
        block=Block(script=line)
        bad=segment('Сегодня хозяева играют очень плохо нет.');good=segment(line,5)
        result,cuts=remove_retakes([block],[bad,good])
        self.assertEqual(len(cuts),1);self.assertEqual(result[0]['words'][0]['start'],5)
        # Same authored sentence twice, or distant repetition, isn't a retake.
        self.assertFalse(remove_retakes([block,Block(kind='outro',script=line)],[bad,good])[1])
        self.assertFalse(remove_retakes([block],[bad,segment(line,80)])[1])
        different=segment('Сегодня хозяева играют очень плохо и проигрывают.',5)
        self.assertFalse(remove_retakes([block],[bad,different])[1])

    def test_retakes_remap_silence_and_voice_together(self):
        keep=keep_ranges(20,[(8,12)])
        result=subtract_ranges(keep,[(1,4),(2,5)])
        self.assertEqual(result[0],(0,1));self.assertEqual(result[1][0],5)
        self.assertAlmostEqual(sum(b-a for a,b in result),12.2333333333,places=3)

    def test_uncertain_prose_is_not_a_card_for_any_speaker(self):
        for profile,language,sport in [('ru_hockey','ru','hockey'),('uz_football','uz','football'),('uz_combat','uz','combat')]:
            b=Block(language=language,sport=sport,script='Мы обсуждаем сегодняшнюю игру.',kind='intro')
            p=Project(profile=profile,blocks=[b]);plan=Plan(0,10,[(0,10)],[Line(b.script,0,10,1,'Неуверенно')],[],[],[],10)
            attach(plan,b,p)
            self.assertFalse(plan.cards);self.assertFalse(pending(plan));self.assertEqual(plan.lines[0].recognized,'')

    def test_old_subtitles_removed_but_custom_text_survives(self):
        text='Мы обсуждаем сегодняшнюю игру.'
        c=Card(0,5,'ИНФОРМАЦИЯ',text,0,review_id='x');p=Plan(0,5,[(0,5)],[Line(text,0,5,1,'Неуверенно')],[],[c],[],5)
        p.edit_baseline={'cards':[asdict(c)]};p.review_items=[dict(id='x',status='confirmed')]
        old=p.to_dict();old['cards'][0]['line']=-1
        self.assertTrue(remove_old_subtitles(old));self.assertFalse(old['cards']);self.assertFalse(remove_old_subtitles(old))
        authored=p.to_dict();authored['cards'][0]['text']='Мой текст'
        self.assertFalse(remove_old_subtitles(authored))

    def test_review_identifies_pair_role_and_position(self):
        p=Project();p.intro.uid='intro';plan=Plan(0,5,[(0,5)],[],[],[],[],5)
        kind,where=describe_card(Card(0,5,'РАЗБОР МАТЧА','Барыс — Локомотив'),dict(block_id='intro',start=0),p,plan)
        self.assertEqual(kind,'Представление пары');self.assertIn('Вступление',where);self.assertIn('внизу',where)

    def test_profile_presets_roundtrip_only_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'prefs.json';p=Project(host='host',music='music',logo_folder=folder);p.settings.noise_reduction=14
            save_preset(p,'Сильный',path);p.music='other';p.settings.noise_reduction=6
            apply_preset(p,'Сильный',path)
            self.assertEqual(p.music,'music');self.assertEqual(p.settings.noise_reduction,14);self.assertEqual(p.host,'host')
            self.assertFalse(presets('uz_combat',path));remember_folder(p,path)
            new=Project();restore_folder(new,path);self.assertEqual(new.logo_folder,folder)
            save=Path(folder)/'project.hockeyproj';p.save(save);loaded=Project.load(save);self.assertEqual(Path(loaded.logo_folder).resolve(),Path(folder).resolve())

    def test_logo_aliases_collisions_manual_and_combat(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('Boston Bruins.png','Монреаль.webp'):(root/name).touch()
            p=Project(logo_folder=folder,blocks=[Block(title='Бостон — Montreal Canadiens')])
            self.assertFalse(assign(p));self.assertEqual(Path(p.team_logos['Бостон']).name,'Boston Bruins.png')
            p.team_logos['Бостон']='manual';assign(p);self.assertEqual(p.team_logos['Бостон'],'manual')
            p.team_logos.clear();(root/'Boston Bruins.jpg').touch();self.assertTrue(assign(p));self.assertNotIn('Бостон',p.team_logos)
            p.profile='uz_combat';p.team_logos.clear();assign(p);self.assertFalse(p.team_logos)

    def test_live_cards_change_without_rebuilding_and_base_changes_invalidate(self):
        p=Plan(0,10,[(0,10)],[],[],[Card(1,5,'СТАТИСТИКА','4 победы')],[],10)
        key=base_key(p);edited=copy.deepcopy(p);edited.cards[0].start=3;edited.cards[0].text='5 побед'
        self.assertEqual(key,base_key(edited));self.assertFalse(base_plan(p).cards)
        edited.cards[0].asset='telegram.mov';self.assertNotEqual(key,base_key(edited))
        with tempfile.TemporaryDirectory() as folder:
            project=Project();project.settings.wobble=False;project.settings.animate_cards=False
            live=LiveCards(project,folder);frame=Image.new('RGB',(640,360),'black')
            before=live.compose(frame,0,p);during=live.compose(frame,2,p);after=live.compose(frame,6,p)
            self.assertIsNone(ImageChops.difference(frame,before).getbbox())
            self.assertIsNotNone(ImageChops.difference(frame,during).getbbox())
            self.assertIsNone(ImageChops.difference(frame,after).getbbox())

if __name__=='__main__':unittest.main()

class NewCaseTests(unittest.TestCase):
    def test_nhl_nicknames_and_vague_pick_followups(self):
        from hockey_editor.framing import forecast_text
        from hockey_editor.event_rules import team_position
        names={'Leafs':'Toronto Maple Leafs','Kraken':'Seattle Kraken','Devils':'New Jersey Devils','Oilers':'Edmonton Oilers','Golden Knights':'Vegas Golden Knights','Canucks':'Vancouver Canucks','Bruins':'Boston Bruins','Canadiens':'Montreal Canadiens'}
        for short,club in names.items():
            self.assertEqual(ru_identity(short),club)
            self.assertIsNotNone(team_position(club,'Сегодня '+short+' играют дома.'))
        b=Block(title='Сент-Луис — Чикаго',script='Основной прогноз — победа Сент-Луиса с учётом овертайма и буллитов. Но мой основной выбор именно с дополнительным временем.')
        self.assertEqual(forecast_text(b),'St. Louis Blues\nПобеда с ОТ и буллитами')

    def test_intro_list_is_four_separate_pairs_not_statistics_or_subtitles(self):
        from hockey_editor.framing import prepared_script,framing_cards
        titles=['Ванкувер — Эдмонтон','Сент-Луис — Чикаго','Сиэтл — Калгари','Рейнджерс — Нью-Джерси']
        p=Project(blocks=[Block(title=t) for t in titles])
        b=Block(kind='intro',script='Сегодня четыре матча предсезонки НХЛ. Разберём «Ванкувер» — «Эдмонтон», «Сент-Луис» — «Чикаго», «Сиэтл» — «Калгари» и «Рейнджерс» — «Нью-Джерси».')
        lines=[Line(t,i*3,i*3+3) for i,t in enumerate(prepared_script(b).splitlines())]
        cards,_=framing_cards(p,b,lines,len(lines)*3)
        self.assertEqual([c.text for c in cards],titles)
        self.assertEqual(len({c.start for c in cards}),4)

    def test_unmentioned_intro_fixture_does_not_create_pending_card(self):
        from hockey_editor.review import framing_draft
        p=Project(blocks=[Block(title='Бостон — Рейнджерс')]);b=Block(kind='intro',script='Всем привет, сегодня нас ждёт интересный хоккей.')
        cards,_=framing_draft(p,b,[Line(b.script,0,5)],5)
        self.assertFalse(cards)

    def test_combat_auto_selection_needs_motion_clock_and_correct_fighter(self):
        from hockey_editor.combat_scan import confident_action,DETECTOR_VERSION
        from hockey_editor.goals import propose,unresolved
        from hockey_editor.model import EventRequest
        obs=[[0,100,.95],[2,98,.96],[4,96,.94],[6,94,.96]]
        self.assertTrue(confident_action(.5,4,obs,[1.4]*14,[False]*14))
        self.assertFalse(confident_action(.5,4,[[t,100,q] for t,v,q in obs],[1.4]*14,[False]*14))
        self.assertFalse(confident_action(.5,4,obs,[.3]*14,[False]*14))
        self.assertFalse(confident_action(.5,4,obs,[1.4]*14,[False,False,True]+[False]*11))
        source=MatchSource('a','','',sport='combat',fighter='FIGHTER ALPHA')
        candidate=dict(id='combat-0',start=.5,end=4,time=2,confidence=.86,kind='play',score=None,before=None,note='Active round')
        scans={source.id:dict(signature='sig',fighter=source.fighter,detector_version=DETECTOR_VERSION,candidates=[candidate])}
        def event():return EventRequest(source.id,'Alpha zarba beradi','play',requested_teams=[source.fighter])
        e=event();propose([e],scans,[source]);self.assertTrue(e.selection.accepted)
        e=event();e.requested_teams=['FIGHTER BETA'];propose([e],scans,[source]);self.assertFalse(e.selection.accepted)
        candidate['confidence']=.7;e=event();propose([e],scans,[source]);self.assertFalse(e.selection.accepted)
        candidate['confidence']=.86;scans[source.id].pop('detector_version');e=event();propose([e],scans,[source]);self.assertFalse(e.selection.accepted)


class NHLRecognitionTests(unittest.TestCase):
    def test_split_asr_names_and_decimal_do_not_create_false_conflict(self):
        from hockey_editor.ru_speech import speech_word_units
        from hockey_editor.review import semantic_conflict
        heard='Рейнджерс Нью -Джерси, тотал меньше 6 ,5.'
        units=speech_word_units(segment(heard)['words'])
        self.assertIn('Нью -Джерси,',[w['word'] for w in units])
        self.assertIn('6 ,5.',[w['word'] for w in units])
        self.assertFalse(semantic_conflict('Тотал меньше 6,5',heard))
        self.assertTrue(semantic_conflict('Тотал меньше 6,5','тотал больше 6 ,5'))
        self.assertEqual(tokens('Сент -Луис'),tokens('St. Louis Blues'))
        self.assertEqual(tokens('Сеттал Калгарри'),tokens('Seattle Kraken Calgary Flames'))

    def test_season_record_is_stats_but_hypothetical_score_is_not_result(self):
        from hockey_editor.card_text import classify_card,summarize_card
        self.assertEqual(classify_card('Монреаль закончил регулярку 48–24–10.'),'СТАТИСТИКА')
        self.assertIn('48 — 24 — 10',summarize_card('СТАТИСТИКА','Монреаль закончил регулярку 48–24–10.'))
        self.assertFalse(classify_card('Требовать уверенных 4:1 я не собираюсь.'))
        self.assertEqual(classify_card('Если Торонто выиграет 4:3 — ставка всё равно проходит.'),'УСЛОВИЯ ПРОГНОЗА')
