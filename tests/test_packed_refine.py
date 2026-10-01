import tempfile,unittest,threading,wave
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from hockey_editor.media import Cancelled
from hockey_editor.uz_refine import refine,pack_retries
from test_uz_speech import segment


class PackedRefineTests(unittest.TestCase):
    def test_short_clauses_share_decoder_and_map_back_to_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio=Path(tmp)/'voice.wav';rate=16000
            with wave.open(str(audio),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(np.zeros(40*rate,dtype='<i2').tobytes())
            baseline=[segment(3,5,'total bir yarimdan ko‘p'),segment(25,27,'total uch yarimdan kam')]
            for s in baseline:
                for w in s['words']:w['probability']=.6
            samples=np.zeros(40*rate,dtype=np.float32)
            _,slots=next(pack_retries([(i,s,None) for i,s in enumerate(baseline)],samples,rate))
            words=[]
            for slot in slots:
                for w in slot['original']['words']:
                    words.append(NS(word=w['word'],start=w['start']-slot['offset'],end=w['end']-slot['offset'],probability=.99))
            calls=[]
            def transcribe(buffer,**kwargs):calls.append(len(buffer));return [NS(words=words)],None
            p=NS(profile='uz_football')
            with patch('hockey_editor.uz_speech.recognition_prompt',return_value='names'):
                result=refine(NS(transcribe=transcribe),audio,baseline,p,threading.Event(),lambda _:None)
                again=refine(NS(transcribe=transcribe),audio,baseline,p,threading.Event(),lambda _:None)
            self.assertEqual(len(calls),1);self.assertLess(calls[0],28*rate)
            self.assertEqual(again,result)
            for actual,expected in zip(result,baseline):
                self.assertAlmostEqual(actual['words'][0]['start'],expected['start'])
                self.assertAlmostEqual(actual['words'][-1]['end'],expected['end'])
                self.assertEqual(actual['words'][0]['probability'],.99)

    def test_packs_are_bounded_and_no_phrase_split(self):
        samples=np.zeros(2000,dtype=np.float32);rate=10
        items=[(i,segment(i*25+1,i*25+19,'total kam'),None) for i in range(6)]
        packs=list(pack_retries(items,samples,rate))
        self.assertEqual(sum(len(slots) for _,slots in packs),6)
        self.assertTrue(all(len(buffer)<=28*rate for buffer,_ in packs))

    def test_uncertain_cross_boundary_or_missing_retry_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio=Path(tmp)/'voice.wav'
            with wave.open(str(audio),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(bytes(16000*2*10))
            original=segment(2,5,'total 2,5 dan kam')
            for word in original['words']:word['probability']=.6
            model=NS(transcribe=lambda *a,**k:([NS(words=[NS(word='wrong',start=0,end=8,probability=.99)])],None))
            with patch('hockey_editor.uz_speech.recognition_prompt',return_value=''):
                result=refine(model,audio,[original],NS(profile='uz_football'),threading.Event(),lambda _:None)
            self.assertEqual(result[0]['text'].strip(),original['text'])
