"""Bounded second pass: retain the original unless a retry is demonstrably better."""
import re,wave,hashlib,json
from pathlib import Path
from .uzbek import norm
from .media import Cancelled


def quality(words):
    probabilities=[w.get('probability',1.) for w in words]
    return sum(probabilities)/max(1,len(probabilities))


def preferable(original,retry,profile):
    from .combat_cards import coverage,numbers,classify
    if profile=='uz_hockey':from .uz_hockey import classify
    elif profile=='uz_football':from .uzbek import classify
    a,b=original.get('text',''),retry.get('text','')
    if not b or coverage(a,b)<.72 or not .65<=len(b.split())/max(1,len(a.split()))<=1.6:return False
    if classify(a)[0]=='ПРОГНОЗ' and classify(b)[0]!='ПРОГНОЗ':return False
    # Never silently replace a clearly heard numeric value.
    if numbers(a)!=numbers(b):
        numeric=[w for w in original.get('words',[]) if numbers(w['word'])]
        if not numeric or all(w.get('probability',1.)>=.65 for w in numeric):return False
    return quality(retry.get('words',[]))>=quality(original.get('words',[]))+.05


def retry_candidates(baseline):
    """Keep the old eligibility/budget; change scheduling, not acceptance."""
    budget=120.
    for index,s in enumerate(baseline):
        span=s['end']-s['start'];t=norm(s['text'])
        important=bool(re.search(r'rekord|statistik|g.alab|mag.lub|nokaut|yosh|foiz|tanlo|talno|santimetr|zarba|shayba|total|fora|overtaym|bullit|murabbiy|darvozabon|tarkib|transfer|uchrashuv|o.yin|telegram|havola|tavsif',t))
        if not important or quality(s['words'])>=.80 or not 1<=span<=20 or span>budget:continue
        budget-=span
        yield index,s


def pack_retries(items,samples,rate,max_seconds=28.):
    """Put short retries in one decoder window with silent separators.

    Each slot retains an exact sample offset back to its original audio.
    No audio is removed from the episode: these buffers are only ASR retries.
    """
    import numpy as np
    buffers=[];slots=[];cursor=0;gap=round(.6*rate)
    for index,s,path in items:
        lo=max(0,int((s['start']-.2)*rate));hi=min(len(samples),int((s['end']+.2)*rate))
        clip=samples[lo:hi]
        if not len(clip):continue
        if slots and cursor+gap+len(clip)>round(max_seconds*rate):
            yield np.concatenate(buffers),slots
            buffers=[];slots=[];cursor=0
        if slots:
            buffers.append(np.zeros(gap,dtype=np.float32));cursor+=gap
        slots.append(dict(index=index,original=s,path=path,start=cursor/rate,
                          end=(cursor+len(clip))/rate,offset=lo/rate-cursor/rate))
        buffers.append(clip);cursor+=len(clip)
    if slots:yield np.concatenate(buffers),slots


def refine(model,audio,segments,project,cancel,log):
    import numpy as np
    from .uz_speech import recognition_prompt
    from .host_media import identity
    from .processing_cache import read_json,write_json
    from .combat import spoken_segments
    baseline=spoken_segments(segments);result=list(baseline)
    prompt=recognition_prompt(project);audio_key=identity(audio)
    cache=Path(audio).parent/'refined-clauses-v2'
    pending=[]
    for index,s in retry_candidates(baseline):
        if cancel.is_set():raise Cancelled('Отменено.')
        key=hashlib.sha256(json.dumps([audio_key,project.profile,prompt,s],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        path=cache/(key+'.json');cached=read_json(path)
        if cached is not None:result[index]=cached
        else:pending.append((index,s,path))
    if not pending:return result
    with wave.open(str(audio),'rb') as wav:
        rate=wav.getframerate();samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    calls=0
    for packed,slots in pack_retries(pending,samples,rate):
        if cancel.is_set():raise Cancelled('Отменено.')
        calls+=1
        log(f'Уточняю {len(slots)} коротких фраз одним проходом ({len(packed)/rate:.1f} с звука)…')
        found,_=model.transcribe(packed,language='uz',word_timestamps=True,beam_size=5,vad_filter=False,condition_on_previous_text=False,initial_prompt=prompt)
        words=[]
        for segment in found:
            if cancel.is_set():raise Cancelled('Отменено.')
            words.extend(segment.words or [])
        for slot in slots:
            original=slot['original'];offset=slot['offset']
            # A word crossing a separator is ambiguous. Do not assign it to
            # either phrase, and let the unchanged acceptance guard decide.
            selected=[dict(word=w.word,start=max(original['start'],offset+w.start),
                           end=min(original['end'],offset+w.end),probability=w.probability)
                      for w in words if w.start>=slot['start']-.001 and w.end<=slot['end']+.001
                      and offset+w.end>original['start'] and offset+w.start<original['end']]
            selected=[w for w in selected if w['end']>w['start']]
            retry=dict(start=original['start'],end=original['end'],words=selected,text=' '.join(w['word'] for w in selected))
            chosen=retry if preferable(original,retry,project.profile) else original
            write_json(slot['path'],chosen);result[slot['index']]=chosen
    log(f'Уточнение речи: {len(pending)} фраз, запусков декодера: {calls}.')
    return result
