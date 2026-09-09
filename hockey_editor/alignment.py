"""Offline subsequence forced alignment; no network calls or neural weights."""
from pathlib import Path
import ctypes as C, threading, re
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from scipy.fft import dct
from math import gcd
from .timeline import Line
from .media import Cancelled

SR=16000
HOP=640
_lock=threading.Lock()

def split_script(text):
    result=[]
    for line in text.splitlines():
        line=line.strip()
        if line:
            result.extend(re.split(r'(?<=[.!?])\s+(?=[А-ЯЁA-Z«])',line))
    if not result: raise ValueError('Сценарий пуст.')
    return result

def spoken(text):
    from num2words import num2words
    text=text.replace('СКА','ска').replace('ЦСКА','цэ эс ка')
    def ordinal(m):
        try:return num2words(int(m[1]),lang='ru',to='ordinal')
        except Exception:return m[0]
    text=re.sub(r'(\d+)-(?:й|я|е|го|м)\b',ordinal,text)
    text=re.sub(r'(\d+):(\d+)',lambda m:num2words(int(m[1]),lang='ru')+' '+num2words(int(m[2]),lang='ru'),text)
    text=re.sub(r'(\d+)[.,](\d{2})\b',lambda m:num2words(int(m[1]),lang='ru')+' '+num2words(int(m[2]),lang='ru'),text)
    text=re.sub(r'\d+',lambda m:num2words(int(m[0]),lang='ru'),text)
    return text

def synthesize(texts,target,cancel):
    import espeakng_loader
    with _lock:
        lib=C.CDLL(espeakng_loader.get_library_path())
        lib.espeak_Initialize.argtypes=[C.c_int,C.c_int,C.c_char_p,C.c_int]
        lib.espeak_Initialize.restype=C.c_int
        sr=lib.espeak_Initialize(2,0,espeakng_loader.get_data_path().encode('utf-8'),0)
        if sr<=0:raise RuntimeError('Не удалось запустить локальное сопоставление речи.')
        lib.espeak_SetVoiceByName.argtypes=[C.c_char_p]
        if lib.espeak_SetVoiceByName(b'ru')!=0:raise RuntimeError('Русский голос для анализа не найден в сборке.')
        lib.espeak_SetParameter(1,185,0)
        chunks=[]
        @C.CFUNCTYPE(C.c_int,C.POINTER(C.c_short),C.c_int,C.c_void_p)
        def callback(wav,n,events):
            if wav and n:chunks.append(np.ctypeslib.as_array(wav,shape=(n,)).copy())
            return 0
        lib.espeak_SetSynthCallback(callback)
        lib.espeak_Synth.argtypes=[C.c_void_p,C.c_size_t,C.c_uint,C.c_int,C.c_uint,C.c_uint,C.c_void_p,C.c_void_p]
        audio=[];starts=[];pos=0
        try:
            for text in texts:
                if cancel.is_set():raise Cancelled()
                chunks.clear();data=spoken(text).encode('utf-8')+b'\0';buf=C.create_string_buffer(data)
                if lib.espeak_Synth(buf,len(data),0,1,0,1,None,None):raise RuntimeError('Ошибка подготовки текста для анализа.')
                lib.espeak_Synchronize()
                if not chunks:raise ValueError('Не удалось обработать строку сценария: '+text)
                x=np.concatenate(chunks);active=np.flatnonzero(np.abs(x)>80)
                if len(active):x=x[:min(len(x),active[-1]+int(.16*sr))]
                starts.append(pos/sr);audio.append(x);pos+=len(x)
            wavfile.write(target,sr,np.concatenate(audio))
        finally:lib.espeak_Terminate()
    return starts

def features(path):
    sr,x=wavfile.read(path);x=x.astype(np.float64)/32768
    if x.ndim>1:x=x.mean(axis=1)
    if sr!=SR:
        g=gcd(sr,SR);x=resample_poly(x,SR//g,sr//g)
    if not len(x):raise ValueError('Аудиодорожка пуста.')
    x=np.r_[x[0],x[1:]-.97*x[:-1]]
    win=1600;nfft=2048
    frames=np.lib.stride_tricks.sliding_window_view(np.pad(x,(win//2,win//2)),win)[::HOP]
    mel=lambda f:2595*np.log10(1+f/700)
    hz=lambda m:700*(10**(m/2595)-1)
    edges=hz(np.linspace(mel(100),mel(7500),42));freq=np.fft.rfftfreq(nfft,1/SR)
    bank=np.array([np.maximum(0,np.minimum((freq-edges[i])/(edges[i+1]-edges[i]),(edges[i+2]-freq)/(edges[i+2]-edges[i+1]))) for i in range(40)])
    output=[]
    # Bounded batches prevent spectrograms from exhausting a 16 GB machine.
    for start in range(0,len(frames),500):
        spec=abs(np.fft.rfft(frames[start:start+500]*np.hamming(win),n=nfft))**2
        logs=np.log(np.maximum(spec@bank.T,1e-12))
        output.append(dct(logs,type=2,axis=1,norm='ortho')[:,1:14])
    return np.concatenate(output)

def normalized(feat,variant):
    x=feat-feat.mean(axis=0)
    if variant:x/=x.std(axis=0)+1e-5
    return np.ascontiguousarray(x/(np.linalg.norm(x,axis=1,keepdims=True)+1e-10),dtype=np.float32)

def subsequence_dtw(a,b,cancel=None,progress=None,free=True):
    """Align all of b inside a. Exact row recurrence using prefix minima.

    The free first column skips source audio before the matching block;
    minimum last-column cost chooses the end. Backtracking retains absolute
    source frame numbers, including when the recording contains other blocks.
    """
    n,m=len(a),len(b)
    if n*m>200_000_000:
        raise ValueError('Для этой версии запись слишком длинная. Используйте запись до 15 минут и сценарий одного разбора.')
    back=np.zeros((n,m),dtype=np.uint8)
    prev=np.full(m+1,np.inf);prev[0]=0
    best=np.inf;last=0
    for i in range(n):
        if i%50==0:
            if cancel and cancel.is_set():raise Cancelled()
            if progress:progress(i/n)
        # einsum avoids launching a large BLAS thread pool for each small row.
        cost=np.maximum(0,1-np.einsum('ij,j->i',b,a[i]))
        horizontal=cost.astype(np.float64)*1.08
        diag=prev[:-1]+cost;up=prev[1:]+horizontal
        base=np.minimum(diag,up)
        cumulative=np.cumsum(horizontal)
        adjusted=base-cumulative
        prefixes=np.minimum.accumulate(adjusted)
        cur=np.r_[0. if free else np.inf,prefixes+cumulative]
        back[i]=np.where(adjusted<=prefixes, np.where(diag<=up,0,1),2)
        if (free and cur[-1]<best) or (not free and i==n-1):best=cur[-1];last=i
        prev=cur
    if not np.isfinite(best):raise ValueError('Не удалось сопоставить сценарий и речь.')
    i=last;j=m-1;tot=np.zeros(m);counts=np.zeros(m)
    while i>=0 and j>=0:
        tot[j]+=i;counts[j]+=1
        step=back[i,j]
        if step==0:i-=1;j-=1
        elif step==1:i-=1
        else:j-=1
    if np.any(counts==0):raise ValueError('Сценарий не удалось полностью сопоставить с записью.')
    return tot/counts, float(best/(last-i+m))

def speech_regions(audio,reference_duration):
    sr,x=wavfile.read(audio)
    if x.ndim>1:x=x.mean(axis=1)
    x=x.astype(float)/32768
    hop=max(1,round(sr*.02));count=len(x)//hop
    active=np.max(np.abs(x[:count*hop].reshape(-1,hop)),axis=1)>.01778
    changes=np.flatnonzero(np.diff(np.r_[True,active,True]))
    pauses=[(a*hop/sr,b*hop/sr) for a,b in zip(changes[::2],changes[1::2]) if (b-a)*hop/sr>=1.2]
    segments=[];cur=0.
    for lo,hi in pauses:
        if lo-cur>.4:segments.append((max(0,cur-.1),min(len(x)/sr,lo+.12)))
        cur=hi
    if len(x)/sr-cur>.4:segments.append((max(0,cur-.1),len(x)/sr))
    candidates=[]
    for i in range(len(segments)):
        for j in range(i,min(i+3,len(segments))):
            lo,hi=segments[i][0],segments[j][1]
            if .65*reference_duration <= hi-lo <= 2.1*reference_duration:candidates.append((lo,hi))
    return candidates


def align(audio,script,cache,cancel,log):
    texts=split_script(script)
    log('Подготовка локального сравнения текста и голоса…')
    reference=Path(cache)/'reference.wav'
    anchors=synthesize(texts,reference,cancel)
    full=features(audio);b=features(reference)
    candidates=speech_regions(audio,len(b)*HOP/SR)
    best=None
    # Pauses delimit candidate blocks. Match the complete script to each block;
    # this prevents unconstrained subsequence DTW from compressing long passages
    # into a phonetically similar short fragment elsewhere in the recording.
    for k,(lo,hi) in enumerate(candidates):
        log(f'Проверяю участок записи {k+1} из {len(candidates)}…')
        start=max(0,int(lo*SR/HOP));stop=min(len(full),int(hi*SR/HOP)+1)
        a=full[start:stop]
        path,score=subsequence_dtw(normalized(a,0),normalized(b,0),cancel,free=False)
        if best is None or score<best[0]:best=(score,start,a,path)
    if best is None:
        log('Ищу разбор в непрерывной записи…')
        a=full;start=0
        path,score=subsequence_dtw(normalized(a,0),normalized(b,0),cancel)
        free=True
    else:
        score,start,a,path=best
        free=False
    bounds=[np.interp(anchors,np.arange(len(path))*HOP/SR,(path+start)*HOP/SR)]
    ends=[(path[-1]+start)*HOP/SR];quality=[score]
    log('Проверяю устойчивость таймингов вторым вариантом анализа…')
    other,score=subsequence_dtw(normalized(a,1),normalized(b,1),cancel,free=free)
    bounds.append(np.interp(anchors,np.arange(len(other))*HOP/SR,(other+start)*HOP/SR))
    ends.append((other[-1]+start)*HOP/SR);quality.append(score)
    starts=(bounds[0]+bounds[1])/2
    endpoint=min(len(full)*HOP/SR,(ends[0]+ends[1])/2+.10)
    lines=[Line(t,float(starts[i]),float(starts[i+1] if i+1<len(texts) else endpoint),
                float(abs(bounds[0][i]-bounds[1][i]))) for i,t in enumerate(texts)]
    disagreements=[i for i,l in enumerate(lines) if l.agreement>.8 or l.end-l.start<.25]
    if any(l.agreement>3 for l in lines) or len(disagreements)>max(3,len(lines)//4):
        raise ValueError('Не удалось надежно совместить сценарий с записью. Проверьте соответствие текста речи и отсутствие повторных дублей. Неточная разметка не будет отправлена на экспорт.')
    warnings=[]
    if disagreements:warnings.append('Проверьте фразы с неустойчивой разметкой: '+', '.join(str(i+1) for i in disagreements))
    if max(quality)>.65:warnings.append('Слабое совпадение текста и голоса. Проверьте сценарий и предпросмотр перед экспортом.')
    return lines,warnings
