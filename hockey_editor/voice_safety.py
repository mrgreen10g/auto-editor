"""Level-aware pause detection and conservative processing of quiet speech."""
from pathlib import Path
import tempfile,wave
import numpy as np
from .media import run,audio_stream

REVISION='voice-safety-v1'

def quiet_spans(samples,rate):
    if samples.ndim==1:samples=samples[:,None]
    size=max(1,round(rate*.02));count=len(samples)//size
    if not count:return [],-55.
    frames=samples[:count*size].astype(np.float64).reshape(count,size,-1)
    rms=np.sqrt(np.max(np.mean(frames*frames,axis=1),axis=1))
    active=rms[rms>1e-6]
    reference=20*np.log10(np.quantile(active,.9)) if len(active) else -60.
    threshold=max(-85.,min(-45.,reference-25.))
    # Peak gate is deliberately stricter than RMS: quiet consonants survive.
    quiet=np.max(np.abs(frames),axis=(1,2))<10**(threshold/20)
    edges=np.diff(np.r_[False,quiet,False].astype(int));spans=[]
    for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
        if (b-a)*size/rate>=.5:spans.append((a*size/rate,b*size/rate))
    return spans,float(threshold)

def detect(path,start,end,cache,cancel):
    with tempfile.TemporaryDirectory(prefix='voice-',dir=cache) as folder:
        target=Path(folder)/'audio.wav'
        run(['-y','-ss',start,'-t',end-start,'-i',path,'-map',audio_stream(path),'-vn','-ac','2','-ar','8000','-c:a','pcm_s16le',target],cancel)
        with wave.open(str(target),'rb') as src:
            rate=src.getframerate();channels=src.getnchannels()
            samples=np.frombuffer(src.readframes(src.getnframes()),dtype='<i2').reshape(-1,channels)/32768.
        return quiet_spans(samples,rate)

def protect_spoken(spans,lines,source_start):
    from .speech_cleanup import subtract_ranges
    protected=[]
    for line in lines:
        if line.words:
            protected.extend((line.start+w['start']-source_start-.08,line.start+w['end']-source_start+.08) for w in line.words)
        elif line.text.strip():
            # Legacy phrase-only timing cannot certify an internal pause.
            protected.append((line.start-source_start-.08,line.end-source_start+.08))
    return [(a,b) for a,b in subtract_ranges(spans,protected) if b-a>=.5]

def voice_filters(settings):
    # Normalize before suppression: a fixed -40 dB floor on quiet raw voice
    # can remove syllables. Never learn an adaptive noise profile from speech.
    result='highpass=f=70,loudnorm=I=-16:TP=-2:LRA=9,aresample=48000'
    if settings.denoise:result+=f',afftdn=nr={settings.noise_reduction}:nf=-55:tn=0'
    return result
