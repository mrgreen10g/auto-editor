"""Level-aware pause detection and conservative processing of quiet speech."""
from pathlib import Path
import tempfile,wave
import numpy as np
from .media import run,audio_stream

REVISION='voice-safety-v2'

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
    # Handling clicks and low room noise should not retain a long recording head.
    # Actual recognized words are protected downstream, even when very quiet.
    head_threshold=max(-75.,min(-35.,reference-18.))
    active_head=rms>=10**(head_threshold/20)
    onset=next((i for i in range(max(0,min(len(active_head)-10,3000)))
                if np.count_nonzero(active_head[i:i+10])>=8),None)
    if onset is not None and onset>=25:
        from .speech_cleanup import merge_ranges
        spans=merge_ranges([(0.,max(0.,onset*.02-.15)),*spans])
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

def voice_filters(settings,gain_db=0.):
    # Normalize before suppression: a fixed -40 dB floor on quiet raw voice
    # can remove syllables. Never learn an adaptive noise profile from speech.
    result=f'highpass=f=70,volume={float(gain_db):.6f}dB,aresample=48000'
    if settings.denoise:
        # afftdn buffers two 12.5 ms blocks. Flush the tail and remove its
        # 25 ms latency so audio remains aligned with camera frames.
        result+=f',apad=pad_dur=0.025,afftdn=nr={settings.noise_reduction}:nf=-55:tn=0,atrim=start=0.025,asetpts=PTS-STARTPTS'
    return result


def measured_gain(paths,cache,cancel):
    """Gated full-recording measurement; constant gain from the first sample.

    Peak constraint preserves dynamics without loudnorm's adaptive fallback.
    """
    import hashlib,json,math,re
    from .processing_cache import read_json,write_json
    measurements=[]
    for path in dict.fromkeys(str(p) for p in paths):
        p=Path(path);st=p.stat()
        key=hashlib.sha256(repr((str(p.resolve()),st.st_size,st.st_mtime_ns,'gain-v1')).encode()).hexdigest()
        target=Path(cache)/('voice-level-'+key[:24]+'.json');stats=read_json(target,{})
        if not stats:
            output=run(['-i',p,'-map',audio_stream(p),'-vn','-af','highpass=f=70,loudnorm=I=-16:TP=-2:LRA=50:print_format=json','-f','null','-'],cancel)
            blocks=re.findall(r'\{\s*"input_i".*?\}',output,re.S)
            if not blocks:raise ValueError('Не удалось измерить громкость голоса.')
            stats=json.loads(blocks[-1]);write_json(target,stats)
        level=float(stats['input_i']);peak=float(stats['input_tp'])
        if math.isfinite(level) and math.isfinite(peak):measurements.append((level,peak))
    if not measurements:return 0.
    level=10*math.log10(sum(10**(v/10) for v,_ in measurements)/len(measurements))
    return max(-30.,min(24.,-16-level,-2-max(p for _,p in measurements)))
