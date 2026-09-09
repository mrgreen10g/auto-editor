import tempfile
import threading
import unittest
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from hockey_editor.model import Block, MatchSource, EventRequest, Project
from hockey_editor.goals import Candidate, propose
from hockey_editor.event_rules import requests_for
from hockey_editor.gameplay import gameplay_candidates
from hockey_editor.card_text import summarize_card
from hockey_editor.orientation import choose_rotation
from hockey_editor.timeline import Card, Line, placements
from hockey_editor.graphics import card_image


class AutomationTests(unittest.TestCase):
    def test_missing_score_uses_same_match_gameplay(self):
        source=MatchSource('match.mp4','Северсталь','Лада')
        event=EventRequest(source.id,'Лада уступила 0:1.',score=[1,0],requested_teams=['Лада','Северсталь'])
        c=Candidate('broll-0',None,None,6,2,10,.8,kind='play')
        propose([event],{source.id:{'signature':'s','candidates':[vars(c)]}},[source],True)
        self.assertEqual(event.source_id,source.id)
        self.assertTrue(event.selection.accepted)
        self.assertEqual(event.selection.context_label,'Кадры матча')

    def test_missing_match_prefers_related_archive_and_avoids_repeat(self):
        unrelated=MatchSource('one.mp4','СКА','Динамо')
        related=MatchSource('two.mp4','Лада','Салават Юлаев')
        sources=[unrelated,related]
        scans={m.id:{'signature':m.id,'candidates':[vars(Candidate(f'broll-{i}',None,None,6+i*15,2+i*15,10+i*15,.8,kind='play')) for i in range(2)]} for m in sources}
        events=[EventRequest('', 'Лада уступила Северстали.',requested_teams=['Лада','Северсталь']) for _ in range(2)]
        propose(events,scans,sources,True)
        self.assertTrue(all(e.source_id==related.id and e.selection.accepted for e in events))
        self.assertTrue(all(e.selection.context_label.startswith('Архивные кадры') for e in events))
        self.assertNotEqual(events[0].selection.candidate_id,events[1].selection.candidate_id)

    def test_brief_reference_is_not_ignored(self):
        primary=MatchSource('one.mp4','СКА','Лада')
        extra=MatchSource('two.mp4','Лада','Салават Юлаев')
        block=Block(title='СКА — Лада',match_ids=[primary.id,extra.id],script='Лада также встречалась с Салаватом Юлаевым в предсезонке. Команда хорошо двигалась и создавала моменты.')
        events=requests_for(block,[primary,extra])
        self.assertTrue(events)
        self.assertEqual(events[0].source_id,extra.id)
        self.assertEqual(events[0].kind,'play')

    def test_moving_ice_without_scoreboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[]
            for i in range(12):
                image=Image.new('RGB',(320,180),'#e6eef1');draw=ImageDraw.Draw(image)
                draw.line((0,90,320,90),fill='#4280b3',width=3)
                draw.rectangle((20+i*12,55,55+i*12,105),fill='#14283b')
                path=Path(tmp)/f'{i}.jpg';image.save(path);files.append(path)
            choices=gameplay_candidates(files,24,threading.Event())
            self.assertTrue(choices)
            self.assertTrue(all(c.kind=='play' and c.score is None and c.end<=24 for c in choices))

    def test_conditions_are_short_and_injuries_verbatim(self):
        text='А если снова получим плотный матч с разницей в одну шайбу или дополнительное время — ставка выигрывает.'
        short=summarize_card('УСЛОВИЯ ПРОГНОЗА',text)
        self.assertEqual(short,'Разница в 1 шайбу или дополнительное время → выигрыш')
        injury='СКА потерял Захара Бардакова, получившего повреждение именно в первом матче с «Ладой».'
        self.assertEqual(summarize_card('СОСТАВ КОМАНДЫ',injury),injury)
        self.assertEqual(summarize_card('ПРОГНОЗ','Но мой выбор — «Лада» с форой плюс два.'),'Лада\nФора (+2)')
        self.assertIn('36 — 32',summarize_card('СТАТИСТИКА','«Лада» перебросала СКА 36:32.'))

    def test_manual_card_edit_overrides_summary(self):
        block=Block(script='Вступление. Мой выбор — Лада с форой плюс два.',card_overrides={'1':'Мой собственный текст'})
        _,cards,_=placements(block,[Line('Вступление.',0,3),Line('Мой выбор — Лада с форой плюс два.',3,7)],{},7)
        self.assertEqual(cards[-1].text,'Мой собственный текст')

    def test_orientation_requires_consistent_evidence(self):
        self.assertEqual(choose_rotation([{0:.2,180:2.4}]*3),(180,True))
        self.assertEqual(choose_rotation([{0:2,180:2.1}]*3),(0,False))
        self.assertEqual(choose_rotation([{90:2.4},{90:2.4},{90:2.4}]),(90,True))

    def test_logo_roundtrip_and_distinct_match_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);logo=folder/'logo.png'
            Image.new('RGBA',(24,16),'#ee3355').save(logo)
            project=Project(team_logos={'Лада':str(logo)})
            project.save(folder/'project.hockeyproj')
            self.assertEqual(Project.load(folder/'project.hockeyproj').team_logos['Лада'],str(logo))
            card_image(Card(0,5,'РАЗБОР МАТЧА','СКА — Лада'),folder/'match.png',project.team_logos)
            card_image(Card(5,10,'СТАТИСТИКА','Броски: 36 — 32'),folder/'stats.png')
            with Image.open(folder/'match.png') as m, Image.open(folder/'stats.png') as s:
                self.assertGreater(m.width,s.width)
