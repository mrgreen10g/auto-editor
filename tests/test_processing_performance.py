import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import numpy as np
from hockey_editor.media import Cancelled
from hockey_editor.processing_cache import read_json, write_json
from hockey_editor.scan_cache import observations
from hockey_editor.speech_cache import recognize, cpu_threads
from hockey_editor.score_ocr import ScoreReader
from hockey_editor.goals import Observation, detect_candidates


class ProcessingPerformanceTests(unittest.TestCase):
    def test_ocr_reuses_exact_pixels_but_not_one_changed_pixel(self):
        calls=[]
        def ocr(image, **kw):
            calls.append(image.copy())
            return [('1:0', .99)], None
        reader=ScoreReader(ocr)
        frame=np.zeros((12,32,3),dtype=np.uint8)
        self.assertEqual(reader.text(frame), reader.text(frame.copy()))
        self.assertEqual(len(calls),1)
        frame[3,5,0]=1
        reader.text(frame)
        self.assertEqual(len(calls),2)

    def test_uncertain_ocr_is_retried(self):
        calls=[]
        def ocr(image,**kw):
            calls.append(1);return [('0:0',.4)],None
        reader=ScoreReader(ocr)
        image=np.zeros((10,10,3),dtype=np.uint8)
        reader.text(image);reader.text(image)
        self.assertEqual(len(calls),2)

    def test_ocr_cache_is_bounded(self):
        reader=ScoreReader(lambda *a,**k: ([('0:0',.99)],None))
        for i in range(600):
            reader.text(np.array([i],dtype=np.int32))
        self.assertEqual(len(reader._text_cache),512)

    def test_cancelled_score_pass_resumes_without_losing_score_or_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cancel=threading.Event();calls=[]
            def read(image,t):
                calls.append(t)
                if t==6:cancel.set()
                return Observation(t,(0,0) if t<10 else (1,0),.99,max(2,8-t),'1ST',ice=.7)
            reader=NS(box=[0,0,1,1],read=read)
            with patch('hockey_editor.goals.read_image',return_value=None):
                with self.assertRaises(Cancelled):
                    observations(reader,list(range(9)),root,cancel,lambda _:None)
                cancel.clear()
                result=observations(reader,list(range(9)),root,cancel,lambda _:None)
            self.assertEqual(calls,list(range(0,18,2)))
            baseline=[read(None,t) for t in range(0,18,2)]
            self.assertEqual(result,baseline)
            self.assertEqual(detect_candidates(result,18),detect_candidates(baseline,18))

    def test_changed_score_region_invalidates_partial_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader=NS(box=[0,0,1,1],read=lambda image,t:Observation(t,(0,0),.99))
            with patch('hockey_editor.goals.read_image',return_value=None):
                observations(reader,[1,2],tmp,threading.Event(),lambda _:None)
                reader.box=[.1,0,1,1];calls=[]
                reader.read=lambda image,t:(calls.append(t) or Observation(t,(1,0),.99))
                result=observations(reader,[1,2],tmp,threading.Event(),lambda _:None)
                self.assertEqual(calls,[0,2])
                self.assertEqual(result[0].score,(1,0))

    @staticmethod
    def segment(seek,start,text):
        w=NS(word=text,start=start,end=start+1,probability=.95)
        return NS(seek=seek,start=start,end=start+1,text=text,words=[w])

    def test_speech_resume_keeps_whole_windows_and_absolute_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint=Path(tmp)/'raw.json';cancel=threading.Event();options=[]
            segments=[self.segment(0,0,'one'),self.segment(0,2,'two'),
                      self.segment(3000,30,'three'),self.segment(3000,32,'four'),self.segment(6000,60,'five')]
            def transcribe(audio,**kw):
                options.append(kw)
                def values():
                    for s in segments[:3]:yield s
                    raise Cancelled('stop in incomplete window')
                return values(),None
            with self.assertRaises(Cancelled):
                recognize(NS(transcribe=transcribe),'audio.wav',checkpoint,'ru','names',cancel,lambda _:None)
            saved=read_json(checkpoint)
            self.assertEqual(saved['seek'],3000)
            self.assertEqual([s['text'] for s in saved['rows']],['one','two'])
            def resume(audio,**kw):options.append(kw);return iter(segments[2:]),None
            result=recognize(NS(transcribe=resume),'audio.wav',checkpoint,'ru','names',cancel,lambda _:None)
            self.assertEqual([s['text'] for s in result],['one','two','three','four','five'])
            self.assertEqual(result[-1]['words'][0]['start'],60)
            self.assertEqual(options[-1]['clip_timestamps'],'30.0')
            self.assertIsNone(options[-1]['initial_prompt'])
            with patch.object(NS(),'unused',create=True):
                self.assertEqual(recognize(None,'audio.wav',checkpoint,'ru','names',cancel,lambda _:None),result)

    def test_cancel_during_first_window_does_not_save_partial_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            cancel=threading.Event();p=Path(tmp)/'raw.json'
            def iterator():
                yield self.segment(0,0,'start')
                cancel.set()
                yield self.segment(0,2,'unfinished')
            with self.assertRaises(Cancelled):
                recognize(NS(transcribe=lambda *a,**k:(iterator(),None)),'a',p,'uz',None,cancel,lambda _:None)
            self.assertFalse(p.exists())

    def test_cpu_budget_leaves_room_for_windows(self):
        for count,expected in [(1,1),(2,1),(4,3),(8,6),(32,6)]:
            with self.subTest(cpu=count),patch('os.cpu_count',return_value=count):
                self.assertEqual(cpu_threads(),expected)

    def test_atomic_checkpoint_corruption_does_not_block_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'stage.json';p.write_text('{incomplete')
            self.assertIsNone(read_json(p))
            write_json(p,{'complete':True})
            self.assertEqual(read_json(p),{'complete':True})

    def test_gpu_failure_releases_model_and_retries_on_cpu(self):
        from hockey_editor.speech_cache import with_model
        created=[];calls=[]
        class Model:
            def __init__(self,*args,**kwargs):
                self.device=kwargs['device'];created.append(self.device)
        def work(model):
            calls.append(model.device)
            if model.device=='cuda':raise RuntimeError('missing runtime or insufficient VRAM')
            return ['recognized']
        with patch.dict('sys.modules',{'faster_whisper':NS(WhisperModel=Model)}),patch('hockey_editor.speech_cache.preferred_device',return_value=('cuda','float16')):
            self.assertEqual(with_model('model',work,lambda _:None),['recognized'])
        self.assertEqual(created,['cuda','cpu'])
        self.assertEqual(calls,created)

    def test_cancellation_does_not_trigger_gpu_retry(self):
        from hockey_editor.speech_cache import with_model
        class Model:
            def __init__(self,*a,**k):pass
        def work(model):raise Cancelled('stop')
        with patch.dict('sys.modules',{'faster_whisper':NS(WhisperModel=Model)}),patch('hockey_editor.speech_cache.preferred_device',return_value=('cuda','float16')):
            with self.assertRaises(Cancelled):with_model('model',work,lambda _:None)

    def test_probe_cache_invalidates_replaced_file(self):
        from hockey_editor.media import probe,_probe_cached
        _probe_cached.cache_clear()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'video';p.write_bytes(b'old')
            output=NS(stderr='Duration: 00:00:10.00\nVideo: h264, 320x180\nAudio: aac')
            with patch('hockey_editor.media.subprocess.run',return_value=output) as process,patch('hockey_editor.media.ffmpeg',return_value='ffmpeg'):
                first=probe(p);first['duration']=200
                self.assertEqual(probe(p)['duration'],10)
                self.assertEqual(process.call_count,1)
                p.write_bytes(b'new content')
                probe(p)
                self.assertEqual(process.call_count,2)
