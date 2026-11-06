import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from hockey_editor.media import Cancelled
from hockey_editor.speech_cache import recognize


class VocabularyCacheTests(unittest.TestCase):
    @staticmethod
    def segment(seek,start,text):
        return NS(seek=seek,start=start,end=start+1,text=text,
                  words=[NS(word=text,start=start,end=start+1,probability=.9)])

    def test_vocabulary_survives_resume_without_duplicate_initial_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'raw.json';cancel=threading.Event();calls=[]
            def first(audio,**kw):
                calls.append(kw)
                def values():
                    yield self.segment(0,1,'first')
                    yield self.segment(3000,30,'unfinished')
                    raise Cancelled('interrupted')
                return values(),None
            with self.assertRaises(Cancelled):
                recognize(NS(transcribe=first),'a',path,'uz','names',cancel,lambda _:None,hotwords='names')
            def resumed(audio,**kw):
                calls.append(kw);return iter([self.segment(3000,30,'second')]),None
            result=recognize(NS(transcribe=resumed),'a',path,'uz','names',cancel,lambda _:None,hotwords='names')
            self.assertEqual([s['text'] for s in result],['first','second'])
            self.assertEqual(result[-1]['start'],30)
            self.assertEqual(calls[-1]['clip_timestamps'],'30.0')
            self.assertTrue(all(c['hotwords']=='names' and c['initial_prompt'] is None for c in calls))
            self.assertEqual(recognize(None,'a',path,'uz','names',cancel,lambda _:None,hotwords='names'),result)

    def test_changed_vocabulary_does_not_reuse_incompatible_cache(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'raw.json';cancel=threading.Event();calls=[]
            def transcribe(audio,**kw):
                calls.append(kw);return iter([self.segment(0,1,kw['hotwords'])]),None
            model=NS(transcribe=transcribe)
            for vocabulary in ('old','new'):
                result=recognize(model,'a',path,'uz',vocabulary,cancel,lambda _:None,hotwords=vocabulary)
                self.assertEqual(result[0]['text'],vocabulary)
            self.assertEqual(len(calls),2)
            self.assertNotIn('clip_timestamps',calls[1])

    def test_default_path_still_reuses_old_cache(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'raw.json';rows=[dict(text='old',start=0,end=1,words=[])]
            path.write_text(json.dumps(dict(version=1,seek=0,rows=rows,complete=True)))
            self.assertEqual(recognize(None,'a',path,'ru','names',threading.Event(),lambda _:None),rows)
