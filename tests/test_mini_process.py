import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from test_mini_app import app_fixture
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_server import RemoteError
from hockey_editor.model import MatchSource,EventRequest,EventSelection

class ProcessTests(unittest.TestCase):
    def fixture(self,root):
        app=app_fixture(root);bridge=Bridge(app);app.mini=bridge
        app.notifier.config.update(auto_timing=True,mini_enabled=True)
        app.start=Mock();app.search_matches=Mock()
        return app,bridge

    def test_manual_timing_duplicate_stale_and_busy(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=self.fixture(Path(d));data=dict(stage='analyze',request='request-123',revision=b.revision())
            b.process.start(data);b.process.start(data);app.start.assert_called_once_with(False,remote=True)
            with self.assertRaises(RemoteError):b.process.start(dict(data,request='request-456',revision='stale'))
            app.busy=True
            with self.assertRaises(RemoteError):b.process.start(dict(data,request='request-456'))

    def test_pending_gate_then_last_approval_starts_only_once(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=self.fixture(Path(d));block=app.project.blocks[0]
            block.events=[EventRequest('', 'Первый'),EventRequest('', 'Второй')]
            self.assertFalse(b.process.status()['can_analyze'])
            b.action(dict(id='clip:'+block.uid+':0',revision=b.revision(),decision='deleted'))
            app.root.after.assert_not_called()
            b.action(dict(id='clip:'+block.uid+':1',revision=b.revision(),decision='deleted'))
            app.root.after.assert_called_once()
            b.process.maybe_auto();b.process.maybe_auto();app.start.assert_called_once_with(False,remote=True)

    def test_auto_rejects_cancel_error_material_change_and_undo(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=self.fixture(Path(d));p=b.process
            for reason in ('cancel','changed','error','disabled','pending'):
                app.cancel.clear();app.notifier.config['auto_timing']=True;app.project.blocks[0].events=[];p.failed_scope=None
                p.begin('goals');p.clips_finished(['failed'] if reason=='error' else [])
                if reason=='cancel':app.cancel.set()
                if reason=='changed':app.project.blocks[0].script+=' Новые материалы.'
                if reason=='disabled':app.notifier.config['auto_timing']=False
                if reason=='pending':app.project.blocks[0].events=[EventRequest('', 'Повторная проверка')]
                p.maybe_auto();app.start.assert_not_called()

    def test_search_requires_explicit_replacement_and_cancel_id(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=self.fixture(Path(d));source=MatchSource(app.project.host,'A','B');app.project.matches=[source]
            block=app.project.blocks[0];block.match_ids=[source.id];block.events=[EventRequest(source.id,'test',skipped=True)]
            data=dict(stage='goals',request='request-123',revision=b.revision())
            with self.assertRaises(RemoteError):b.process.start(data)
            b.process.start(dict(data,replace=True));app.search_matches.assert_called_once_with(remote=True,replace=True)
            b.process.begin('goals');app.busy=True
            with self.assertRaises(RemoteError):b.process.cancel({'job':'old'})
            b.process.cancel({'job':b.process.job['id']});self.assertTrue(app.cancel.is_set())

    def test_result_checkpoint_and_failed_save_blocks_auto(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=self.fixture(Path(d));app.stage='goals';b.process.begin('goals');b.process.clips_finished([])
            with patch.object(b,'checkpoint',side_effect=OSError('disk full')):b.process.event('done',None)
            self.assertEqual(b.process.job['status'],'error');self.assertIsNone(b.process.auto_scope)
            b.process.maybe_auto();app.start.assert_not_called()
            app.stage='analyze';b.process.begin('analyze');b.process.event('plan',app.plan);b.process.event('done',None)
            self.assertEqual(b.process.job['status'],'completed');self.assertTrue(app.project_path.exists())

    def test_setting_persists_without_erasing_bot_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            app,b=self.fixture(Path(d));app.notifier.config['token']='123:test'
            with patch('hockey_editor.notifications.save') as save:
                b.process.configure(dict(revision=b.revision(),auto_timing=False))
            self.assertEqual(save.call_args.args[0]['token'],'123:test')
            self.assertFalse(app.notifier.config['auto_timing'])
