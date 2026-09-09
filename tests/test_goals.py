import json
import tempfile
import threading
import unittest
from pathlib import Path
from hockey_editor.model import Project, Block, MatchSource, EventRequest, EventSelection
from hockey_editor.goals import Observation, Candidate, detect_candidates, propose, source_signature, montage_block
from hockey_editor.event_rules import requests_for, team_position
from hockey_editor.score_ocr import score_text, clock_text


class GoalTests(unittest.TestCase):
    def test_live_increment_freeze_and_replay(self):
        obs = [Observation(t, (0, 0) if t < 10 else (1, 0), .96, max(2, 8-t), '1ST', ice=.7) for t in range(0, 18, 2)]
        candidates = detect_candidates(obs, 18)
        goals = [c for c in candidates if c.kind == 'goal']
        self.assertEqual([c.score for c in goals], [[1, 0]])
        self.assertEqual(goals[0].time, 6)
        self.assertGreater(goals[0].confidence, .85)
        obs += [Observation(t, (0, 0), .96, 5) for t in (18, 20)]
        obs += [Observation(t, (1, 0), .96, 2) for t in (22, 24)]
        goals = [c for c in detect_candidates(obs, 26) if c.kind == 'goal']
        self.assertEqual(len(goals), 1)
        self.assertLess(goals[0].confidence, .85)

    def test_score_gap_needs_review(self):
        obs = [Observation(t, (0, 0) if t < 10 else (2, 0), .99, 0) for t in range(0, 18, 2)]
        self.assertLess(detect_candidates(obs, 18)[0].confidence, .85)

    def test_banner_needs_review(self):
        obs = [Observation(0, (3, 3), .99), Observation(2, (3, 3), .99), Observation(4, None, goal_banner=True, banner_side=0)]
        candidate = detect_candidates(obs, 15)[0]
        self.assertEqual(candidate.score, [4, 3]); self.assertLess(candidate.confidence, .85)

    def test_score_and_clock_parsers(self):
        self.assertEqual(score_text('1 I 1'), (1, 1))
        self.assertEqual(score_text('2:3'), (2, 3))
        self.assertIsNone(score_text('17:29')); self.assertIsNone(score_text('212'))
        self.assertEqual(clock_text('3RD 04:52'), 292)

    def test_region_discovery_excludes_clock_subcrops(self):
        import numpy as np
        from hockey_editor.score_ocr import ScoreReader
        reader = ScoreReader(ocr=lambda *a, **k: ([], None))
        score = [.1, .9, .18, .96]
        clock = [.5, .9, .65, .96]
        reader.tokens = lambda image, top, bottom: [(score, '0|0', .99), (clock, '00:08', .99)] if top > .5 else []
        reader.visual_candidates = lambda image: [([.5, .9, .55, .96], .99)]*8 + [(score, .9)]
        result = reader.locate([np.zeros((720,1280,3), dtype='uint8')]*3, threading.Event(), lambda _:None)
        self.assertEqual(result, score)
        self.assertEqual(reader.clock_box, clock)
        self.assertEqual(reader.location_debug[0][1], 3)

    def test_static_clock_not_play(self):
        obs = [Observation(t, (0, 0), .99, 2, ice=.8) for t in range(0, 20, 2)]
        self.assertEqual(detect_candidates(obs, 20), [])

    def test_script_assigns_sources_and_score_order(self):
        a = MatchSource('a.mp4', 'СКА', 'Лада')
        b = MatchSource('b.mp4', 'СКА', 'Динамо Москва')
        c = MatchSource('c.mp4', 'Северсталь', 'Лада')
        block = Block(title='СКА — Лада', match_ids=[a.id, b.id, c.id], script='''СКА выиграл 4:3 в овертайме.
«Лада» вела 2:1 после первого периода.
В третьем снова вышла вперёд — 3:2.
И СКА смог сравнять только на 56-й минуте.
А затем уже Матвей Короткий решил встречу в овертайме.
После этого СКА обыграл московское «Динамо» 5:3.
Но «Лада» уступила «Северстали» всего 0:1.
По счёту жду 3:2 или 4:2 в пользу СКА.''')
        events = requests_for(block, [a, b, c])
        self.assertEqual([e.score for e in events], [[1, 2], [2, 3], [3, 3], [4, 3], [5, 3], [1, 0]])
        self.assertEqual([e.source_id for e in events], [a.id]*4+[b.id, c.id])
        self.assertIsNone(team_position('СКА', 'ЦСКА выиграл'))

    def test_missing_source_requests_archive(self):
        source = MatchSource('a.mp4', 'СКА', 'Лада')
        block = Block(title='СКА — Лада', match_ids=[source.id], script='СКА обыграл московское «Динамо» 5:3. Атака действительно работает.')
        events = requests_for(block, [source])
        self.assertTrue(events)
        self.assertTrue(all(not e.skipped and not e.source_id for e in events))
        self.assertEqual(events[0].requested_teams, ['СКА', 'Динамо'])

    def test_candidate_cannot_cross_sources(self):
        event = EventRequest('one', 'Сравнял счёт', score=[3, 3])
        candidate = Candidate('c', [3, 3], [2, 3], 10, 3, 15, .99)
        propose([event], {'two': {'signature': 'x', 'candidates': [vars(candidate)]}})
        self.assertIsNone(event.selection)

    def test_project_roundtrip_and_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); video = folder/'game.mp4'; video.write_bytes(b'video')
            source = MatchSource(str(video), 'СКА', 'Лада')
            signature = source_signature(source)
            selection = EventSelection('c', 1, 9, 6, signature, True)
            block = Block(match_ids=[source.id], events=[EventRequest(source.id, 'гол', selection=selection)])
            project = Project(matches=[source], blocks=[block, Block(match_ids=[source.id])])
            project.save(folder/'project.hockeyproj')
            loaded = Project.load(folder/'project.hockeyproj')
            self.assertEqual(loaded.blocks[0].events[0].selection, selection)
            self.assertEqual(loaded.blocks[1].match_ids[0], loaded.matches[0].id)
            video.write_bytes(b'changed video')
            self.assertNotEqual(signature, source_signature(source))

    def test_unreviewed_event_blocks_montage(self):
        project = Project(blocks=[Block(events=[EventRequest('one', 'гол')])])
        with self.assertRaisesRegex(ValueError, 'Проверьте'):
            montage_block(project, 0, '.', threading.Event())

    def test_legacy_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'v1.hockeyproj'
            path.write_text(json.dumps({'version': 1, 'host': '', 'blocks': [{'title': 'Test', 'script': ''}]}))
            project = Project.load(path)
            self.assertEqual(project.version, 3); self.assertEqual(project.matches, [])
