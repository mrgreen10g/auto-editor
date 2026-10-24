import tempfile,threading,unittest,json,sys
from pathlib import Path
from unittest.mock import patch,Mock
from hockey_editor.translation_quality import issue,translate_piece
from hockey_editor import notifications as n
from hockey_editor.mobile_inputs import Inputs
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_server import RemoteError
from test_mini_app import app_fixture
from test_folder_import import setup,SCRIPT

class MobileUpdateTests(unittest.TestCase):
    def test_notifications_replace_only_same_episode_after_delivery(self):
        config=dict(enabled=True,token='123:secret',chat_id='1234',events=list(n.EVENTS))
        with tempfile.TemporaryDirectory() as d,patch.object(n,'location',return_value=Path(d)/'telegram.json'),patch.object(n,'load',return_value=config),patch.object(n,'send',side_effect=[{'message_id':1},{'message_id':2},{'message_id':3}]),patch.object(n,'api') as api:
            notifier=n.Notifier();notifier.emit('a','started','one',scope='episode1');notifier.queue.join()
            notifier.emit('b','cards','two',scope='episode2');notifier.queue.join();api.assert_not_called()
            notifier.emit('c','render','three',scope='episode1');notifier.queue.join()
            api.assert_called_once_with('123:secret','deleteMessage',{'chat_id':'1234','message_id':1})
            self.assertNotIn('secret',(Path(d)/'telegram-messages.json').read_text())

    def test_bad_translation_and_valid_sports_content(self):
        self.assertTrue(issue('Xorazm 0:0 hisobida durang oynagan.','Аллах — Прощающий, Милосердный.'))
        self.assertTrue(issue('Hisob 2:2.','Счёт 2:0.'))
        self.assertFalse(issue('Hisob 2:2.','Счёт 2:2.'))
        self.assertTrue(issue('Arsenal hujum qiladi.','Команда забьёт гол и победит. '*8))

    def test_translation_retries_instead_of_returning_hallucination(self):
        tokenizer=Mock();tokenizer.encode.return_value.tokens=['<2ru>','sentence'];tokenizer.token_to_id.return_value=1
        tokenizer.decode.side_effect=['Аллах прощающий','Команда играет дома.']
        model=Mock();model.translate_batch.return_value=[Mock(hypotheses=[['translated']])]
        self.assertEqual(translate_piece('Jamoa uyda oynaydi.',model,tokenizer,threading.Event()),'Команда играет дома.')
        self.assertEqual(model.translate_batch.call_count,2)
        tokenizer.encode.assert_called_with('<2ru> Jamoa uyda oynaydi.',add_special_tokens=False)

    def test_import_server_folder_keeps_original_files_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);material=root/'materials';material.mkdir();host,script=setup(material)
            bridge=Bridge(app_fixture(root));inputs=Inputs(bridge,root/'catalog.json')
            payload=dict(folder=str(material),profile='ru_hockey',host=str(host),script=str(script))
            result=inputs.server_import(payload);draft=inputs.load(result['id'])
            self.assertEqual(len(draft['blocks']),2)
            self.assertEqual(next(f['path'] for f in draft['files'] if f['role']=='host'),str(host.resolve()))
            self.assertEqual(len([f for f in draft['files'] if f['role']=='match']),2)
            self.assertEqual(inputs.server_import(payload)['id'],result['id'])
            self.assertEqual(inputs.load(result['id']),draft)
            self.assertEqual(host.read_bytes(),b'host')
            self.assertTrue(inputs.summary(draft)['can_create'])
            bridge.app.restore_plan=Mock();bridge.app.status.set=Mock()
            inputs.activate(dict(id=result['id'],revision=bridge.revision()))
            sources={m.id:m.path for m in bridge.app.project.matches}
            for block in bridge.app.project.blocks:
                expected=[f['path'] for f in draft['files'] if f['role']=='match' and f['block']==block.uid]
                self.assertEqual([sources[ident] for ident in block.match_ids],expected)

    def test_short_folder_does_not_use_long_presenter(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);material=root/'materials';material.mkdir();host,script=setup(material)
            (material/'shorts'/'text.txt').write_text(SCRIPT,encoding='utf-8')
            inputs=Inputs(Bridge(app_fixture(root)),root/'catalog.json')
            found=inputs.server_files(dict(folder=str(material),profile='ru_hockey_shorts'))
            self.assertEqual(found['hosts'],[str((material/'shorts'/'host.mp4').resolve())])
            with self.assertRaises(ValueError):inputs.server_import(dict(folder=str(material),profile='ru_hockey_shorts',host=str(host),script=str(script)))

    @unittest.skipUnless(sys.platform=='win32','Windows preview player')
    def test_preview_speed_keeps_position_and_resume_state(self):
        from hockey_editor.preview import PreviewPlayer
        p=PreviewPlayer(Mock());p.path=Path('video.mp4');p.position=12.;p.playing=True;p.seek=Mock()
        p.set_speed(1.5);p.seek.assert_called_once_with(12.,True);self.assertEqual(p.speed,1.5)
        with self.assertRaises(ValueError):p.set_speed(0)
