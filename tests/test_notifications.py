import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from hockey_editor import notifications as n

def config():return dict(enabled=True,auto_timing=True,token='123:secret',chat_id='1234',events=list(n.EVENTS))

class NotificationTests(unittest.TestCase):
    def test_buttons_target_the_matching_mobile_page(self):
        settings=config();settings.update(mini_enabled=True,mini_url='https://server.test.ts.net')
        for page in ('process','cards','clips','export','review'):
            with patch.object(n,'api') as api:
                n.send(dict(settings,_mini_page=page),'hello')
                button=api.call_args.args[2]['reply_markup']['inline_keyboard'][0][0]
                self.assertEqual(button['web_app']['url'],settings['mini_url']+'?view='+page)

    def test_tls_bundle_keeps_verification_enabled(self):
        import ssl
        context=n.tls_context()
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()['x509_ca'],0)

    def test_network_failure_categories_and_secret_redaction(self):
        import ssl,socket
        certificate=ssl.SSLCertVerificationError('123:secret');certificate.verify_code=20
        for error,label in [(certificate,'TLS'),(socket.gaierror(11001,'123:secret'),'DNS'),(TimeoutError('123:secret'),'Тайм-аут')]:
            with self.subTest(label=label),patch.object(n,'getproxies',return_value={'https':'https://user:123:secret@proxy'}):
                message=str(n.network_error(n.URLError(error)))
                self.assertIn(label,message);self.assertIn('прокси',message);self.assertNotIn('secret',message)

    def test_http_token_failure_distinct_from_network(self):
        from urllib.error import HTTPError
        with patch.object(n,'urlopen',side_effect=HTTPError('https://host/123:secret',401,'secret',{},None)):
            with self.assertRaises(n.DeliveryError) as caught:n.api('123:secret','getMe',{})
            self.assertIn('401',str(caught.exception));self.assertIn('токен',str(caught.exception));self.assertNotIn('secret',str(caught.exception))

    def test_secret_not_plaintext_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'protect',side_effect=lambda b,decrypt=False:b[::-1]):
            path=Path(d)/'settings.json';n.save(config(),path)
            self.assertNotIn('123:secret',path.read_text());self.assertNotIn('token',json.loads(path.read_text()))
            self.assertEqual(n.load(path)['token'],'123:secret')

    def test_bad_secret_disables_notifications(self):
        with tempfile.TemporaryDirectory() as d,patch.object(n,'protect',side_effect=ValueError):
            path=Path(d)/'settings.json';path.write_text(json.dumps(dict(enabled=True,secret='eA==')))
            self.assertFalse(n.load(path)['enabled'])

    def test_disabled_no_network_and_duplicate_events(self):
        with patch.object(n,'load',return_value=config()),patch.object(n,'send') as send:
            notifier=n.Notifier();notifier.config['enabled']=False;notifier.emit('job','cards','hello');self.assertEqual(send.call_count,0)
            notifier.config['enabled']=True
            notifier.emit('job','cards','hello');notifier.emit('job','cards','hello');notifier.queue.join()
            self.assertEqual(send.call_count,1)
            notifier.emit('job2','cards','hello');notifier.queue.join();self.assertEqual(send.call_count,2)

    def test_retry_bounded_and_failure_nonblocking(self):
        with patch.object(n,'load',return_value=config()),patch.object(n,'send',side_effect=n.DeliveryError('network',True,0)) as send:
            report=Mock();notifier=n.Notifier(report);notifier.emit('job','error','safe error');notifier.queue.join()
            self.assertEqual(send.call_count,3);report.assert_called_once()

    def test_network_errors_do_not_expose_token(self):
        from urllib.error import URLError
        with patch.object(n,'urlopen',side_effect=URLError('https://api.telegram.org/bot123:secret')):
            with self.assertRaises(n.DeliveryError) as caught:n.send(config(),'hello')
            self.assertNotIn('secret',str(caught.exception))

    def test_auto_transition_gates_and_once(self):
        app=SimpleNamespace(project=SimpleNamespace(blocks=[object()],matches=[],settings=SimpleNamespace(use_manual_clips=False)),selected_indices=lambda:[0],cancel=threading.Event(),notifier=SimpleNamespace(config=config(),emit=Mock()),start=Mock())
        with patch('hockey_editor.goals.unresolved',return_value=[]),patch('hockey_editor.event_search.needs_search',return_value=False):
            n.clips_finished(app,[]);n.continue_timing(app);n.continue_timing(app);app.start.assert_called_once_with(False)
            app.start.reset_mock();n.clips_finished(app,['error']);n.continue_timing(app);app.start.assert_not_called()
            n.clips_finished(app,[]);app.cancel.set();n.continue_timing(app);app.start.assert_not_called();app.cancel.clear()
            app.notifier.config['auto_timing']=False;n.clips_finished(app,[]);n.continue_timing(app);app.start.assert_not_called()
        for pending,incomplete in [([object()],False),([],True)]:
            app.notifier.config['auto_timing']=True
            with patch('hockey_editor.goals.unresolved',return_value=pending),patch('hockey_editor.event_search.needs_search',return_value=incomplete):
                n.clips_finished(app,[]);n.continue_timing(app);app.start.assert_not_called()

    @unittest.skipUnless(n.os.name=='nt','Windows DPAPI')
    def test_windows_secret(self):
        data=b'test-not-a-real-bot-token';cipher=n.protect(data)
        self.assertNotEqual(cipher,data);self.assertEqual(n.protect(cipher,True),data)

