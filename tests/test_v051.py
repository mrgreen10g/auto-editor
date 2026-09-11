"""Regressions from the first two-block user test."""
import unittest
from hockey_editor.model import Block,MatchSource,EventRequest,Clip
from hockey_editor.event_rules import requests_for
from hockey_editor.goals import propose,Candidate
from hockey_editor.timeline import Line,placements,zoom_windows,Insert
from hockey_editor.card_text import classify_card,summarize_card


class UserFeedbackTests(unittest.TestCase):
    def sources(self):
        return [MatchSource('auto','Автомобилист','Динамо Москва'),MatchSource('ska','СКА','Динамо Москва')]

    def test_short_results_keep_subject_and_scoreboard_order(self):
        sources=self.sources();block=Block(title='Динамо Москва — Адмирал',match_ids=[m.id for m in sources],script='''Да, команда Леонида Тамбиева проиграла два первых матча.
Сначала 1:2 «Автомобилисту».
Затем 3:5 СКА.''')
        events=requests_for(block,sources);results=[e for e in events if e.kind=='result']
        self.assertEqual([e.source_id for e in results],[m.id for m in sources])
        self.assertEqual([e.score for e in results],[[2,1],[5,3]])
        self.assertTrue(all(e.requested_teams[0]=='Динамо' for e in results))

    def test_tournament_list_requests_archive_and_keeps_all_scores(self):
        sources=self.sources();phrase='На Кубке Минска были победы над «Сибирью» 3:1, «Сочи» 5:3 и «Металлургом» 4:3.'
        block=Block(title='Динамо Москва — Адмирал',match_ids=[m.id for m in sources],script='Владивосток очень неплохо провёл лето.\n'+phrase)
        event=requests_for(block,sources)[-1];self.assertEqual(event.phrase,phrase)
        self.assertEqual(event.requested_teams,['Адмирал','Сибирь']);self.assertEqual(event.source_id,'')
        scans={m.id:{'signature':'s','candidates':[vars(Candidate('broll-0',None,None,5,1,9,.9,kind='play'))]} for m in sources}
        propose([event],scans,sources,True)
        self.assertIsNotNone(event.selection);self.assertTrue(event.selection.accepted)
        self.assertIn('Архив',event.selection.context_label)
        body=summarize_card(classify_card(phrase),phrase,'Адмирал')
        for value in ('Сибирь','3:1','Сочи','5:3','Металлург','4:3','Адмирал'):self.assertIn(value,body)

    def test_final_score_selects_last_matching_goal_not_earlier_event(self):
        s=self.sources()[0];event=EventRequest(s.id,'Сначала 1:2 «Автомобилисту».',kind='result',score=[2,1])
        candidates=[Candidate('first',[1,0],[0,0],10,5,14,.99),Candidate('final',[2,1],[1,1],80,75,85,.9),Candidate('earlier',[2,1],[1,1],50,45,55,.95)]
        propose([event],{s.id:{'signature':'s','candidates':[vars(c) for c in candidates]}},[s],True)
        self.assertEqual(event.selection.candidate_id,'final')

    def test_direct_results_bypass_density_and_preserve_stats_over_game(self):
        phrases=['Разбор','Общая форма команды','Сначала 1:2 «Автомобилисту».','Затем 3:5 СКА.','Броски: 37:20.']
        lines=[Line(text,i*4,(i+1)*4) for i,text in enumerate(phrases)]
        clips=[Clip('game',text,4,kind='play' if i==1 else 'result') for i,text in enumerate(phrases) if i in (1,2,3)]
        block=Block(title='Динамо Москва — Адмирал',clips=clips)
        for frequency in ('low','normal','high'):
            inserts,cards,_=placements(block,lines,{'game':{'duration':8}},20,frequency)
            self.assertTrue(all(any(c.label==text for c in inserts) for text in phrases[2:4]))
            self.assertTrue(any(c.line==4 and c.title=='СТАТИСТИКА' for c in cards))
            result=next(c for c in cards if c.line==2)
            self.assertIn('Динамо — Автомобилист',result.text);self.assertIn('1:2',result.text)

    def test_both_bet_conditions_are_always_cards_even_with_game(self):
        phrases=['Разбор','Если Владивосток не проигрывает либо уступает в одну шайбу — ставка проходит.','Поражение ровно в две — возврат.']
        block=Block(title='Динамо — Адмирал',clips=[Clip('game',phrases[1],3)])
        _,cards,_=placements(block,[Line(phrases[0],0,5),Line(phrases[1],5,11),Line(phrases[2],11,15)],{'game':{'duration':8}},15)
        conditions=[c for c in cards if c.title=='УСЛОВИЯ ПРОГНОЗА']
        self.assertEqual(len(conditions),2)
        self.assertIn('Не проиграть',conditions[0].text);self.assertIn('1 шайбу',conditions[0].text)
        self.assertIn('2 шайбы',conditions[1].text);self.assertIn('возврат',conditions[1].text)
        self.assertLess(len(conditions[0].text),len(phrases[1]))

    def test_statistics_counts_words_and_reflections(self):
        examples=[('Десять товарищеских матчей — семь побед.',('10','7')),
                  ('Две победы в двух матчах.',('2','матча')),
                  ('Евгений Аликин отразил 36 из 37 бросков.',('36','37'))]
        for phrase,values in examples:
            self.assertEqual(classify_card(phrase),'СТАТИСТИКА')
            body=summarize_card('СТАТИСТИКА',phrase)
            for v in values:self.assertIn(v,body)
        self.assertEqual(classify_card('И ещё интереснее статистика бросков.'),'')

    def test_short_presenter_spans_get_zooms_and_ten_seconds_are_not_static(self):
        for duration in (4.5,7,10,30):
            windows=zoom_windows(duration,[]);self.assertTrue(windows)
            self.assertLess(windows[0][0],1)
            self.assertLess(duration-windows[-1][-1],5.5)
            for a,b,c,d in windows:self.assertTrue(0<=a<b<c<d<=duration)
        clips=[Insert('game',6,11,0,'game'),Insert('game',17,21,0,'game')]
        windows=zoom_windows(28,clips);self.assertGreaterEqual(len(windows),3)
        for a,b,c,d in windows:self.assertFalse(any(a<v.end and d>v.start for v in clips))
