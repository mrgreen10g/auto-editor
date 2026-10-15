import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('corpus_audit', Path(__file__).parents[1]/'scripts/audit_uz_corpus.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CorpusAuditTests(unittest.TestCase):
    def test_duplicate_audio_and_script_components_stay_in_one_split(self):
        rows = []
        for name, audio, script in [('a','audio1','text1'),('b','audio1','text2'),('c','audio3','text2')]:
            rows.extend([dict(episode=name,path='unused',type='.wav',sha256=audio),
                         dict(episode=name,path='unused',type='.txt',sha256=script)])
        with patch.object(module.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='{"format":{"duration":"12"},"streams":[]}', stderr='')):
            result = module.audit(rows)
        self.assertEqual(len({x['split'] for x in result}), 1)
        self.assertTrue(all(x['paired'] for x in result))
        self.assertTrue(all(x['reference_status'] == 'scenario_not_verified_transcript' for x in result))
        self.assertFalse(any(x['training_eligible'] for x in result))

    def test_decode_failure_is_not_accepted(self):
        with patch.object(module.subprocess, 'run', return_value=SimpleNamespace(
                returncode=1, stdout='', stderr='broken audio')):
            result = module.audit([dict(episode='a',path='unused',type='.wav',sha256='x')])
        self.assertFalse(result[0]['audio'][0]['decode_ok'])
        self.assertFalse(result[0]['paired'])

    def test_same_date_variants_stay_together(self):
        rows = []
        for name in ['12.10', '12.10(2)', '13.10', '14.10', '15.10']:
            rows.extend([dict(episode=name,path='unused',type='.wav',sha256=name+'a'),
                         dict(episode=name,path='unused',type='.txt',sha256=name+'s')])
        with patch.object(module.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout='{"format":{"duration":"12"}}', stderr='')):
            result = {x['episode']: x for x in module.audit(rows)}
        self.assertEqual(result['12.10']['split'], result['12.10(2)']['split'])
