import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from types import SimpleNamespace
from hockey_editor.model import Block,Project
from hockey_editor.timeline import Line,Card,Plan,placements
from hockey_editor.speech_boundaries import first_analysis_start,token_similarity
from hockey_editor.ru_speech import tokens,recording_key,recognition_prompt
from hockey_editor.nhl_players import PLAYERS,RUSSIAN,mentions,cards,normalize_speech
from hockey_editor.nhl_roster import ROSTERS
from hockey_editor.review import draft_alignment,preserve_edits
from hockey_editor.graphics import card_image
from test_uz_speech import segment


class NHLBoundaryPlayersTests(unittest.TestCase):
    def test_identity_tokens_are_not_fuzzy_team_matches(self):
        self.assertEqual(token_similarity(tokens('Тампа')[0],tokens('Бостон')[0]),0)
        self.assertEqual(token_similarity(tokens('Рейнджерс')[0],tokens('Rangers')[0]),1)
        self.assertEqual(tokens('Рейнджер с'),tokens('Рейнджерс'))

    def test_first_pair_after_promo_not_later_historical_match(self):
        intro=Block(kind='intro',script='Сегодня Рейнджерс и Тампа. Telegram. Переходим к разбору.')
        body=Block(title='Рейнджерс — Тампа-Бэй',script='Рейнджерс — Тампа-Бэй\nНачну с контекста этого матча и свежести команд.\nРейнджерс открыли чемпионат в Бостоне.')
        speech=[segment(0,4,'Сегодня Рейнджерс и Тампа.'),segment(4,8,'Telegram. Переходим к разбору.'),
                segment(8,10,'Рейнджер с Тампа Бэй.'),segment(10,16,'Начну с контекста этого матча и свежести команд.'),
                segment(35,40,'Rangers открыли чемпионат в Бостоне.')]
        self.assertEqual(first_analysis_start([intro,body],speech),8)
        result=draft_alignment([intro,body],speech,42,'uncertain')
        self.assertEqual(result[intro.uid][0][-1].end,8)
        self.assertEqual(result[body.uid][0][0].start,8)

    def test_body_anchor_precedes_late_repeated_pair(self):
        intro=Block(kind='intro',script='Сегодня хоккей и интересные матчи. Переходим к разбору.')
        body=Block(title='Рейнджерс — Тампа-Бэй',script='Начну с контекста этого матча и свежести команд.\nТампа хорошо играет в атаке.')
        speech=[segment(0,8,intro.script),segment(9,17,'Начну с контекста этого матча и свежести команд. Тампа хорошо играет в атаке.'),segment(45,48,'Рейнджерс Тампа Бэй.')]
        self.assertEqual(first_analysis_start([intro,body],speech),9)

    def test_catalog_full_names_aliases_and_no_ambiguous_identity(self):
        self.assertEqual(len(ROSTERS),32);self.assertGreaterEqual(len(PLAYERS),800)
        self.assertFalse(set(RUSSIAN)-set(PLAYERS))
        for a,b in [('Дорофеев','Дарафеев'),('Бьоркстранд','Бьюерк Странт'),('Хэйгел','Хейгл'),('Доминик Джеймс','Dominic James')]:
            self.assertEqual(tokens(a),tokens(b))
        self.assertEqual(tokens('Петтерссон'),tokens('Пейт Петерсон'))
        self.assertIsNone(mentions('Петтерссон')[0][3])
        self.assertEqual(mentions('Петтерссон')[0][2],'Петтерссон')
        self.assertEqual(mentions('официальный back-to-back'),[])
        self.assertNotIn('Kyle Connor',[x[3] for x in mentions('без Коннора Бедарда')])
        self.assertEqual(mentions('если ли будет победа'),[])

    def test_roster_lists_group_three_and_dont_duplicate_facts(self):
        block=Block(title='Рейнджерс — Тампа-Бэй',script='')
        names=['Дорофеев.','Бьоркстранд.','Толванен.','Велено.','Дурзи.','Петтерссон.']
        lines=[Line(t,i+6,i+7) for i,t in enumerate(names)]
        found=cards(block,lines,[])
        self.assertEqual(len(found),2);self.assertEqual((found[0].start,found[0].end),(6,9))
        self.assertEqual(len(found[0].text.splitlines()),3)
        self.assertIn('Петтерссон',found[1].text);self.assertNotIn('Маркус',found[1].text)
        fact=Line('Дилан Гюнтер забил 40 голов.',13,17)
        self.assertEqual(cards(block,[fact],[Card(13,17,'СТАТИСТИКА',fact.text,0)]),[])
        _,placed,_=placements(block,lines,{},20)
        self.assertEqual(sum(c.title=='ИГРОКИ NHL' for c in placed),2)
        with tempfile.TemporaryDirectory() as d:
            for i,c in enumerate(found):card_image(c,Path(d)/f'{i}.png')

    def test_no_player_subtitles_intro_or_forecast_duplication(self):
        lines=[Line('Джек Хьюз здоров.',6,9),Line('Джек Хьюз снова в составе.',10,13)]
        block=Block();self.assertEqual(len(cards(block,lines,[])),1)
        block.kind='intro';self.assertEqual(cards(block,lines,[]),[])
        block.kind='analysis';self.assertEqual(cards(block,[Line('Каждый матч интересен.',6,9)],[]),[])

    def test_name_prompt_has_no_script_claims_and_changes_cache(self):
        with tempfile.NamedTemporaryFile() as h:
            p=Project(host=h.name,blocks=[Block(script='Кучеров забил 70 голов и победил 5:0.')])
            prompt=recognition_prompt(p)
            self.assertIn('Nikita Kucherov',prompt)
            for word in ('70','5:0','победил'):self.assertNotIn(word,prompt)
            old=recording_key(p);p.blocks[0].script+=' Дорофеев.'
            self.assertNotEqual(recording_key(p),old)

    def test_confirmation_metadata_does_not_freeze_old_auto_timing(self):
        c=Card(1,4,'СТАТИСТИКА','stats',0,review_id='same')
        old=Plan(69,80,[(0,11)],[],[],[copy.deepcopy(c)],[],11)
        old.input_key='input';old.edit_baseline={'cards':[vars(copy.deepcopy(c))]}
        old.cards[0].line=-1
        fresh=Plan(28,80,[(0,52)],[],[],[Card(5,9,'СТАТИСТИКА','stats',0,review_id='same')],[],52)
        fresh.input_key='input'
        preserve_edits(old.to_dict(),fresh)
        self.assertEqual(fresh.cards[0].start,5)
        old.cards[0].start=2
        preserve_edits(old.to_dict(),fresh)
        self.assertEqual(fresh.cards[0].start,43)


if __name__=='__main__':unittest.main()
