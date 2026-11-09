import unittest,tempfile
from pathlib import Path
import numpy as np
from hockey_editor.voice_safety import quiet_spans,protect_spoken,voice_filters
from hockey_editor.timeline import Line
from hockey_editor.model import Settings

class VoiceSafetyTests(unittest.TestCase):
 def test_quiet_speech_is_not_silence_and_real_pause_survives(self):
  rate=8000;t=np.arange(rate*2)/rate
  quiet=.003*np.sin(2*np.pi*220*t)
  signal=np.r_[quiet,np.zeros(rate),quiet*.5]
  for gain in (1,.1,10):
   spans,threshold=quiet_spans(signal*gain,rate)
   self.assertEqual(spans,[(2.,3.)]);self.assertLessEqual(threshold,-45)
 def test_opposite_phase_stereo_does_not_cancel_into_silence(self):
  rate=8000;t=np.arange(rate)/rate;x=.01*np.sin(2*np.pi*220*t)
  self.assertEqual(quiet_spans(np.column_stack([x,-x]),rate)[0],[])
 def test_recognized_words_protect_misclassified_quiet_syllables(self):
  line=Line('Quiet voice',10,14,words=[dict(word='Quiet',start=0,end=1),dict(word='voice',start=2,end=4)])
  spans=protect_spoken([(0,4)],[line],10)
  self.assertEqual(len(spans),1);self.assertAlmostEqual(spans[0][0],1.08);self.assertAlmostEqual(spans[0][1],1.92)
  self.assertEqual(protect_spoken([(0,4)],[Line('Legacy phrase',10,14)],10),[])
 def test_normalize_before_denoise_and_respect_disabled_setting(self):
  f=voice_filters(Settings());self.assertLess(f.index('loudnorm'),f.index('afftdn'));self.assertIn('nf=-55:tn=0',f)
  self.assertNotIn('afftdn',voice_filters(Settings(denoise=False)))
 def test_real_ffmpeg_keeps_quiet_modulated_voice_continuous(self):
  from scipy.io import wavfile
  from hockey_editor.media import run
  rate=48000;t=np.arange(rate*3)/rate
  signal=(.002*(1+.5*np.sin(2*np.pi*3*t))*np.sin(2*np.pi*440*t)).astype(np.float32)
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'quiet.wav';target=Path(d)/'processed.wav';wavfile.write(source,rate,signal)
   run(['-y','-i',source,'-af',voice_filters(Settings()),'-c:a','pcm_f32le',target])
   sr,out=wavfile.read(target);self.assertEqual(sr,rate);self.assertLess(abs(len(out)-len(signal)),100)
   baseline=Path(d)/'baseline.wav'
   run(['-y','-i',source,'-af',voice_filters(Settings(denoise=False)),'-c:a','pcm_f32le',baseline])
   _,reference=wavfile.read(baseline)
   self.assertGreater(np.corrcoef(reference[rate:-rate],out[rate:-rate])[0,1],.999)
   for i in range(rate,2*rate,rate//10):
    ratio=np.sqrt(np.mean(out[i:i+rate//10]**2)/np.mean(reference[i:i+rate//10]**2))
    self.assertGreater(ratio,.85)

 def test_noise_filter_preserves_broadband_timing(self):
  from scipy.io import wavfile
  from hockey_editor.media import run
  rate=48000;rng=np.random.default_rng(7)
  signal=(rng.standard_normal(rate*2)*.02).astype(np.float32)
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'source.wav';wavfile.write(source,rate,signal);results=[]
   for enabled in (False,True):
    target=Path(d)/f'{enabled}.wav'
    run(['-y','-i',source,'-af',voice_filters(Settings(denoise=enabled)),'-c:a','pcm_f32le',target])
    _,out=wavfile.read(target);results.append(out)
   self.assertEqual(len(results[0]),len(results[1]))
   self.assertGreater(np.corrcoef(results[0][rate//2:-rate//2],results[1][rate//2:-rate//2])[0,1],.999)
