import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_mini_process import ProcessTests
from hockey_editor.alignment import BoundaryReviewRequired, AlignmentError
from hockey_editor.engine import Engine
from hockey_editor.model import Project

class BoundaryTests(unittest.TestCase):
    def test_only_boundary_failure_requests_window(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=ProcessTests().fixture(Path(d))
            for event in ('error','boundary_required'):
                b.process.begin('analyze');b.process.event(event,'test')
                self.assertEqual(bool(b.process.job.get('boundary_required')),event=='boundary_required')
                self.assertIsNone(b.process.auto_scope)
            app.stage='boundary_required';b.process.event('done',None)
            self.assertEqual(b.process.job['status'],'review')

    def test_normal_analysis_never_requires_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=ProcessTests().fixture(Path(d));b.process.begin('analyze')
            b.process.event('plan',None);app.stage='analyze';b.process.event('done',None)
            self.assertEqual(b.process.job['status'],'completed')
            self.assertFalse(b.process.job.get('boundary_required'))

    def test_boundary_exception_does_not_restart_recognition(self):
        import threading
        with tempfile.TemporaryDirectory() as d:
            e=Engine(Project(profile='uz_football'),0,Path(d),threading.Event())
            with patch.object(e,'_analyze',side_effect=BoundaryReviewRequired('boundary')),patch('hockey_editor.ru_speech.prepare') as prepare:
                with self.assertRaises(BoundaryReviewRequired):e.analyze()
                prepare.assert_not_called()
