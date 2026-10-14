import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from hockey_editor.review_translation import cache_key, translate, installed


class TranslationTests(unittest.TestCase):
    def test_exact_cache_is_used_without_model_or_network(self):
        source = 'Mening tanlovim total 2,5 dan kam.'
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)/'translations'; folder.mkdir()
            (folder/(cache_key(source)+'.json')).write_text(json.dumps({'source':source,'translation':'Мой выбор — тотал меньше 2,5.'}),encoding='utf-8')
            with patch('hockey_editor.review_translation.ensure_model', side_effect=AssertionError('no download')):
                self.assertEqual(translate([source, ''], d, threading.Event(), lambda s:None), ['Мой выбор — тотал меньше 2,5.', 'Нет текста для перевода.'])

    def test_cancellation_precedes_download(self):
        cancel = threading.Event(); cancel.set()
        with tempfile.TemporaryDirectory() as d, patch('hockey_editor.review_translation.ensure_model', side_effect=AssertionError('no download')):
            with self.assertRaises(InterruptedError): translate(['Salom'], d, cancel, lambda s:None)

    def test_source_changes_invalidate_cache(self):
        self.assertNotEqual(cache_key('2,5 dan kam'),cache_key('2,5 dan ko‘p'))
        self.assertNotEqual(cache_key('Arsenal'),cache_key('Chelsea'))

    def test_missing_model_is_not_reported_installed(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(installed(Path(d)))
