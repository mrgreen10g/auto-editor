import copy
import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hockey_editor.event_rules import requests_for
from hockey_editor.event_search import needs_search, record_completion, search_key
from hockey_editor.goals import Candidate, propose, unresolved, montage_block
from hockey_editor.gui import App
from hockey_editor.match_ui import MatchMixin
from hockey_editor.model import Block, EventRequest, MatchSource, Project


def app_for(project, scope='Все разборы'):
    app = MagicMock()
    app.project = project
    app.index = 0
    app.busy = False
    app.plan = None
    app.page = 'review'
    app.scope.get.return_value = scope
    app.use_manual.get.return_value = project.settings.use_manual_clips
    app.selected_indices.return_value = list(range(len(project.blocks)))
    app.cancel = threading.Event()
    app.jobs = queue.Queue()
    app.scans = {}
    app.log_lines = []
    app.match_job.side_effect = lambda stage, work: work()
    return app


class EventSearchTests(unittest.TestCase):
    def test_discussion_of_choice_does_not_end_analysis(self):
        source = MatchSource('game.mp4', 'Boston Bruins', 'New York Rangers')
        block = Block(title='Рейнджерс — Тампа-Бэй', match_ids=[source.id], script='''
И начну с матча, где мой выбор стал даже интереснее.
Рейнджерс открыли чемпионат в Бостоне.
И проиграли 0:3.
Основной прогноз — победа Тампы-Бэй.
По счёту жду 2:3.''')
        events = requests_for(block, [source])
        result = next(e for e in events if e.kind == 'result')
        self.assertEqual(result.source_id, source.id)
        self.assertEqual(result.score, [3, 0])
        self.assertFalse(any('прогноз' in e.phrase or 'жду' in e.phrase for e in events))
        candidate = Candidate('goal-0', [3, 0], [2, 0], 15, 8, 20, .9)
        play = Candidate('broll-0', None, None, 30, 26, 34, .9, kind='play')
        block.events = propose(events, {source.id: {'signature': 'test',
                               'candidates': [vars(candidate), vars(play)]}}, [source])
        self.assertFalse(unresolved(block))
        self.assertEqual(result.selection.candidate_id, 'goal-0')
        app = app_for(Project(blocks=[block], matches=[source]))
        App.primary_action(app)
        app.search_matches.assert_not_called()
        app.start.assert_called_once_with(False)

    def test_actual_choice_ends_archival_requests(self):
        source = MatchSource('game.mp4', 'СКА', 'Лада')
        for declaration in ['Мой выбор — победа СКА.', 'Но мой выбор: победа СКА.',
                            'Мой выбор это победа СКА.', 'Основной прогноз — победа СКА.']:
            block = Block(title='СКА — Лада', match_ids=[source.id], script=
                          'СКА обыграл Ладу 3:1.\n'+declaration+'\nСКА выиграл 5:0.')
            self.assertEqual([e.score for e in requests_for(block, [source])], [[3, 1]])

    def test_empty_completed_search_reaches_timing_in_all_profiles(self):
        for profile in ['ru_hockey', 'uz_hockey', 'uz_football', 'uz_combat']:
            with self.subTest(profile=profile):
                uz = profile.startswith('uz_')
                sport = profile.split('_')[1]
                source = MatchSource('game.mp4', 'СКА', 'Лада', sport=sport)
                block = Block(title='СКА — Лада', language='uz' if uz else 'ru',
                              sport=sport, match_ids=[source.id], script=
                              'Telegram kanaliga obuna bo‘ling. Keyingi videoda ko‘rishguncha.' if uz
                              else 'Мой выбор — победа СКА. Всем спасибо за внимание и до встречи.')
                project = Project(profile=profile, blocks=[block], matches=[source])
                self.assertEqual(requests_for(block, project.matches), [])
                self.assertTrue(needs_search(block, project.matches, False))
                app = app_for(project)
                with patch('hockey_editor.match_ui.GoalScanner') as scanner:
                    MatchMixin.search_episode_matches(app)
                    scanner.assert_not_called()
                kind, value = app.jobs.get_nowait()
                self.assertEqual(kind, 'episode_goals')
                MatchMixin.handle_match_job(app, kind, value)
                self.assertFalse(needs_search(block, project.matches, False))
                self.assertEqual(montage_block(project,0,'.',threading.Event()).clips, [])
                App.primary_action(app)
                app.search_matches.assert_not_called()
                app.start.assert_called_once_with(False)

    def test_single_block_empty_search_also_advances(self):
        source = MatchSource('game.mp4', 'СКА', 'Лада')
        block = Block(title='СКА — Лада', match_ids=[source.id],
                      script='Мой выбор — победа СКА. Спасибо за внимание, до новых встреч.')
        app = app_for(Project(blocks=[block], matches=[source]), 'Текущий разбор')
        MatchMixin.search_matches(app)
        App.primary_action(app)
        app.search_matches.assert_not_called()
        app.start.assert_called_once_with(False)

    def test_completion_survives_save_and_expires_with_material_changes(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d)/'match.mp4';file.write_bytes(b'video')
            source = MatchSource(str(file), 'СКА', 'Лада')
            block = Block(title='СКА — Лада', match_ids=[source.id], script='Мой выбор — победа СКА.')
            p = Project(blocks=[block], matches=[source])
            record_completion(block, p.matches, False, {})
            from hockey_editor.editing import project_edit_key
            key=project_edit_key(p,0)
            before=block.event_search_key;block.event_search_key=''
            self.assertEqual(project_edit_key(p,0),key)
            block.event_search_key=before
            path = Path(d)/'saved.hockeyproj';p.save(path)
            q = Project.load(path)
            self.assertFalse(needs_search(q.blocks[0], q.matches, False))
            for field, value in [('script', 'СКА обыграл Ладу 3:1.'), ('title', 'Лада — СКА'),
                                 ('language', 'uz'), ('match_ids', [source.id, 'new'])]:
                changed = copy.deepcopy(q.blocks[0]);setattr(changed, field, value)
                self.assertTrue(needs_search(changed, q.matches, False))
            self.assertTrue(needs_search(q.blocks[0], q.matches, True))
            q.matches[0].score_box = [0, 0, .5, .5]
            self.assertTrue(needs_search(q.blocks[0], q.matches, False))
            file.write_bytes(b'changed recording')
            self.assertTrue(needs_search(block, p.matches, False))

    def test_scan_failure_is_not_empty_success(self):
        source = MatchSource('game.mp4', 'СКА', 'Лада')
        block = Block(title='СКА — Лада', match_ids=[source.id], script='СКА обыграл Ладу 3:1.')
        record_completion(block, [source], False, {})
        self.assertEqual(block.event_search_key, '')
        self.assertTrue(needs_search(block, [source], False))
        block.events = propose(requests_for(block, [source]), {})
        self.assertTrue(unresolved(block))
        app = app_for(Project(blocks=[block], matches=[source]))
        App.primary_action(app)
        app.edit_event.assert_called_once()
        app.start.assert_not_called()

    def test_equivalent_paths_keep_search_status(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'nested').mkdir()
            file=folder/'match.mp4';file.write_bytes(b'video')
            source=MatchSource(str(folder/'nested'/'..'/'match.mp4'),'СКА','Лада')
            block=Block(match_ids=[source.id],script='Мой выбор — победа СКА.')
            key=search_key(block,[source],False)
            source.path=str(file.resolve())
            self.assertEqual(search_key(block,[source],False),key)
            if os.name=='nt':
                source.path=source.path.upper().replace('\\','/')
                self.assertEqual(search_key(block,[source],False),key)

    def test_pending_block_does_not_replace_other_blocks(self):
        source = MatchSource('game.mp4', 'СКА', 'Лада')
        empty = Block(match_ids=[source.id], script='Мой выбор — победа СКА. Спасибо за внимание, до новых встреч.')
        done = Block(match_ids=[source.id], events=[EventRequest(source.id, 'Оставить ведущего', skipped=True)])
        p = Project(blocks=[empty, done], matches=[source]);saved = copy.deepcopy(done)
        app = app_for(p)
        MatchMixin.search_episode_matches(app)
        MatchMixin.handle_match_job(app, *app.jobs.get_nowait())
        self.assertEqual(done, saved)
        App.primary_action(app)
        app.start.assert_called_once_with(False)


if __name__ == '__main__':
    unittest.main()
