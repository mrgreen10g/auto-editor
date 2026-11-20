"""Conservative script-backed retakes; never deduplicate distant recap speech."""
import copy
import re
from difflib import SequenceMatcher


def similarity_word(a,b):
    return SequenceMatcher(None,a,b,autojunk=False).ratio()

def remove_retakes(blocks,segments):
    from .alignment import split_script
    from .ru_speech import tokens
    words=[w for s in segments for w in s.get('words',[])]
    sentences=[tokens(t) for b in blocks for t in split_script(b.script)]
    texts=[]
    for block in blocks:
        local=[tokens(t) for t in split_script(block.script)]
        for i in range(len(local)):
            # The presenter can restart a whole thought (up to three sentences).
            # Repeated authored sentences, including recap, remain protected.
            if sentences.count(local[i])!=1:continue
            for size in range(1,min(3 if block.language=='ru' else 1,len(local)-i)+1):
                target=[t for row in local[i:i+size] for t in row]
                if 6<=len(target)<=100:texts.append(target)
    source=[tokens(w['word']) for w in words]
    segment_starts={s['words'][0]['start'] for s in segments if s.get('words')}
    cuts=[]
    for target in texts:
        if len(target)<6 or texts.count(target)>1:continue
        prefix=target[:4]
        anchor=target[1:] if target[0] in {'в','а','и','но'} else target
        starts=[]
        for i in range(len(words)-3):
            # A restart is a sentence/segment boundary or follows a real pause.
            boundary=i==0 or words[i]['start'] in segment_starts or re.search(r'[.!?…]$',words[i-1]['word'].strip()) or words[i]['start']-words[i-1]['end']>=.25
            flat=[t for row in source[i:i+4] for t in row]
            hits=sum(a==b for a,b in zip(flat[:4],prefix))
            short=flat[:3]==prefix[:3] and i+3<len(words) and words[i+3]['start']-words[i+2]['end']>=.6
            content=flat[1:] if flat and flat[0] in {'в','а','и','но'} else flat
            restart_gap=(i>0 and words[i]['start']-words[i-1]['end']>=1.) or (i+2<len(words) and words[i+2]['start']-words[i+1]['end']>=1.)
            partial=boundary and restart_gap and len(content)>=2 and all(len(t)>=5 for t in anchor[:2]) and content[0]==anchor[0] and similarity_word(content[1],anchor[1])>=.8
            if hits==4 or (boundary and hits>=3) or (boundary and short) or partial:starts.append(i)
        for a,b in zip(starts,starts[1:]):
            if not 1<=words[b]['start']-words[a]['start']<=60:continue
            first=[t for row in source[a:b] for t in row]
            allowance=max(3,min(14,round(len(target)*.3)))
            later=[t for row in source[b:b+len(target)+allowance+5] for t in row]
            # Require a complete, better matching replacement, not a repeated
            # slogan or the speaker merely continuing the original sentence.
            critical={'не','нет','без','ноль','один','одна','одно','два','две','три','четыре','пять','шесть','семь','восемь','девять','десять','одинна','двенад','тринад','четырн','пятнад','шестна','семнад','восемн','девятн','двадца','тридца','сорок','пятьде','шестьд','семьде','восемь','девяно','сто','полови'}
            # Extra spoken linking words must not truncate the replacement
            # before its final phrase. Choose among COMPLETE candidates first.
            options=[]
            for n in range(max(4,len(target)-3),min(len(later),len(target)+allowance)+1):
                if [t for t in target if t in critical]!=[t for t in later[:n] if t in critical]:continue
                if SequenceMatcher(None,target[-4:],later[max(0,n-4):n],autojunk=False).ratio()<.75:continue
                options.append((SequenceMatcher(None,target,later[:n],autojunk=False).ratio(),n))
            # Only a long-pause, incomplete start may use a lexical fallback.
            # Critical numbers and negations must still match the replacement.
            if not options and words[b]['start']-words[b-1]['end']>=1. and len(first)<.8*len(target):
                for n in range(max(6,len(target)-1),min(len(later),len(target)+allowance)+1):
                    candidate=later[:n]
                    if [t for t in target if t in critical]!=[t for t in candidate if t in critical]:continue
                    score=SequenceMatcher(None,target,candidate,autojunk=False).ratio()
                    tail=SequenceMatcher(None,target[-5:],candidate[-6:],autojunk=False)
                    if score>=.66 and sum(m.size for m in tail.get_matching_blocks())>=2:options.append((score,n))
            best,n=max(options,default=(0,0))
            if not n:continue
            earlier=SequenceMatcher(None,target,first,autojunk=False).ratio()
            if best<(.66 if words[b]['start']-words[b-1]['end']>=1. and len(first)<.8*len(target) else .85) or best+.001<earlier or len(first)>len(target)+8:continue
            correction=bool(re.search(r'\b(?:нет|точнее|заново|оговорился|поправлюсь)\b',' '.join(w['word'].lower().strip(',.!?') for w in words[a:b])))
            if words[b]['start']-words[b-1]['end']<.08 and not correction:continue
            if not correction and best-earlier<.05 and words[b]['start']-words[b-1]['end']<.18:continue
            lo=max(0,words[a]['start']-.06)
            if a:lo=max(lo,words[a-1]['end'])
            hi=max(lo,words[b]['start']-.08)
            if hi-lo>=.3:cuts.append((lo,hi,len(target),best))
    # Overlapping detections can refer to sentence one and sentence two of
    # the SAME restarted thought. Unioning them would erase the successful
    # first sentence. Prefer the complete thought and reject competing cuts.
    selected=[]
    for lo,hi,length,quality in sorted(cuts,key=lambda c:(-c[2],-c[3],c[0])):
        if not any(lo<b and hi>a for a,b in selected):selected.append((lo,hi))
    cuts=[]
    for lo,hi in sorted(selected):
        if cuts and lo-cuts[-1][1]<=.06:cuts[-1]=(cuts[-1][0],max(hi,cuts[-1][1]))
        else:cuts.append((lo,hi))
    result=[]
    for segment in segments:
        kept=[copy.deepcopy(w) for w in segment.get('words',[]) if not any(a<=w['start']<b for a,b in cuts)]
        if kept:result.append(dict(segment,words=kept,start=kept[0]['start'],end=kept[-1]['end'],text=' '.join(w['word'] for w in kept)))
    return result,cuts


def merge_ranges(ranges):
    result=[]
    for a,b in sorted(ranges):
        if b<=a:continue
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result


def subtract_ranges(keep,cuts):
    for lo,hi in merge_ranges(cuts):
        output=[]
        for a,b in keep:
            if hi<=a or lo>=b:output.append((a,b));continue
            if a<lo:output.append((a,lo))
            if hi<b:output.append((hi,b))
        keep=output
    return keep


def acoustic_cleanup(segments,regions,duration):
    """Constrain stretched ASR words; short quiet words remain protected.

    This changes edit intervals only, never audio samples or gain.
    """
    result=copy.deepcopy(segments)
    for segment in result:
        for word in segment.get('words',[]):
            a,b=word['start'],word['end']
            if b-a<=1.5:continue
            intersect=[(max(a,x),min(b,y)) for x,y in regions if x<b and y>a]
            if intersect and (intersect[0][0]-a>=.8 or any(y-x>=.8 for (_,x),(y,_) in zip(intersect,intersect[1:]))):
                last=intersect[-1]
                if last[1]>=b-.25 and last[1]-last[0]>.08:word['start']=max(a,last[0])
            # Preserve half a second for unvoiced consonants preceding VAD.
            if b-word['start']>1.5 and any(b<=x<=b+.6 for x,y in regions) and intersect and b-intersect[-1][1]>=1.:
                word['start']=max(a,b-.5)
        words=segment.get('words',[])
        if words:segment['start']=words[0]['start'];segment['end']=words[-1]['end']
    protected=[tuple(r) for r in regions]
    for s in result:protected.extend((max(0,w['start']-.12),min(duration,w['end']+.12)) for w in s.get('words',[]))
    spans=merge_ranges(protected);gaps=[];cursor=0.
    for a,b in spans:
        if a-cursor>=.9:gaps.append((cursor,a))
        cursor=max(cursor,b)
    if duration-cursor>=.9:gaps.append((cursor,duration))
    return result,[(a+.08,b-.08) for a,b in gaps if b-a>=1.]


def acoustic_evidence(project,cache,cancel,log):
    from pathlib import Path
    import wave,json
    import numpy as np
    from .speech_cache import prepared_audio
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    folder=Path(cache)/'ru-speech';folder.mkdir(parents=True,exist_ok=True)
    audio=prepared_audio(project,folder,cancel,log)
    stat=audio.stat();key=[stat.st_size,stat.st_mtime_ns,'vad-cleanup-v1']
    path=folder/'speech-activity.json';saved=json.loads(path.read_text()) if path.exists() else {}
    if saved.get('key')==key:return saved['regions'],saved['duration']
    with wave.open(str(audio),'rb') as src:
        rate=src.getframerate();x=np.frombuffer(src.readframes(src.getnframes()),dtype='<i2').astype(np.float32)/32768.
    if rate!=16000:raise ValueError('Неверная частота звука для поиска пауз.')
    if cancel.is_set():
        from .media import Cancelled
        raise Cancelled('Отменено.')
    regions=get_speech_timestamps(x,VadOptions(threshold=.3,min_silence_duration_ms=800,speech_pad_ms=180))
    regions=[(r['start']/rate,r['end']/rate) for r in regions];duration=len(x)/rate
    path.write_text(json.dumps(dict(key=key,regions=regions,duration=duration)))
    return regions,duration
