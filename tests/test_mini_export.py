import tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from test_mini_app import app_fixture
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_export import filename,folder
from hockey_editor.mini_server import RemoteError

class ExportTests(unittest.TestCase):
    def test_paths_and_names(self):
        self.assertEqual(filename('Выпуск'), 'Выпуск.mp4')
        for value in ('../video','a/b.mp4','C:\\file','CON.mp4','x?y','..',''):
            with self.assertRaises(RemoteError):filename(value)
        for value in ('relative','//server/share','\\\\server\\share'):
            with self.assertRaises(RemoteError):folder(value)
    def test_lifecycle_and_duplicate_start(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=app_fixture(root);app.plan.review_items[0]['status']='confirmed';app.cancel=threading.Event()
            def start(*args,**kw):app.busy=True
            app.start=Mock(side_effect=start);bridge=Bridge(app)
            data=dict(revision=bridge.revision(),request='request-1234',folder=d,name='Выпуск')
            result=bridge.export.start(data);bridge.export.start(data)
            app.start.assert_called_once_with(True,target=str(root/'Выпуск.mp4'),remote=True)
            with self.assertRaises(RemoteError):bridge.export.start(dict(data,request='another-request'))
            with self.assertRaises(RemoteError):bridge.export.cancel({'job':'wrong'})
            bridge.export.cancel({'job':result['job']['id']});self.assertTrue(app.cancel.is_set())
            bridge.export.event('cancelled',None);bridge.export.event('done',None)
            self.assertEqual(bridge.export.job['status'],'cancelled')
            app.busy=False;data.update(revision=bridge.revision(),request='second-request');bridge.export.start(data)
            bridge.export.event('review_required',None);bridge.export.event('done',None)
            self.assertEqual(bridge.export.job['status'],'review')
    def test_pending_stale_collision_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));app.start=Mock();bridge=Bridge(app)
            data=dict(revision=bridge.revision(),request='request-1234',folder=d,name='result.mp4')
            with self.assertRaises(RemoteError):bridge.export.start(data)
            app.plan.review_items[0]['status']='confirmed'
            with self.assertRaises(RemoteError):bridge.export.start(data)
            data['revision']=bridge.revision();Path(d,'result.mp4').touch()
            with self.assertRaises(RemoteError):bridge.export.start(data)
            app.start.assert_not_called();Path(d,'result.mp4').unlink()
            app.start.side_effect=ValueError('bad material')
            with self.assertRaises(RemoteError):bridge.export.start(data)
            self.assertEqual(bridge.export.job['status'],'error')
    def test_folders_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'Матчи').mkdir();app=app_fixture(root);bridge=Bridge(app)
            listing=bridge.export.browse({'path':d})
            self.assertEqual([x['name'] for x in listing['folders']],['Матчи'])
            self.assertGreater(listing['free'],0)
