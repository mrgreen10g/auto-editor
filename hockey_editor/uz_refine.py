"""Bounded second pass: retain the original unless a retry is demonstrably better."""
import re,wave
from .uzbek import norm
from .media import Cancelled


def quality(words):
    probabilities=[w.get('probability',1.) for w in words]
    return sum(probabilities)/max(1,len(probabilities))


def preferable(original,retry,profile):
    from .combat_cards import coverage,numbers,classify
    a,b=original.get('text',''),retry.get('text','')
    if not b or coverage(a,b)<.72 or not .65<=len(b.split())/max(1,len(a.split()))<=1.6:return False
    if classify(a)[0]=='ПРОГНОЗ' and classify(b)[0]!='ПРОГНОЗ':return False
    # Never silently replace a clearly heard numeric value.
    if numbers(a)!=numbers(b):
        numeric=[w for w in original.get('words',[]) if numbers(w['word'])]
        if not numeric or all(w.get('probability',1.)>=.65 for w in numeric):return False
    return quality(retry.get('words',[]))>=quality(original.get('words',[]))+.05


def refine(model,audio,segments,project,cancel,log):
    import numpy as np
    from .uz_speech import recognition_prompt
    from .combat import spoken_segments
    # Smaller clauses prevent a retry from dropping the middle of a long
    # monologue. Baseline recognition is preserved for every rejected retry.
    baseline=spoken_segments(segments);result=[];budget=120.
    with wave.open(str(audio),'rb') as wav:
        rate=wav.getframerate();samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    for s in baseline:
        if cancel.is_set():raise Cancelled('Отменено.')
        span=s['end']-s['start'];t=norm(s['text'])
        important=bool(re.search(r'rekord|statistik|g.alab|mag.lub|nokaut|yosh|foiz|tanlo|santimetr|zarba',t))
        if not important or quality(s['words'])>=.80 or not 1<=span<=20 or span>budget:
            result.append(s);continue
        budget-=span;lo=max(0,s['start']-.2);hi=min(len(samples)/rate,s['end']+.2)
        log(f'Уточняю факты в речи {s["start"]:.1f}–{s["end"]:.1f} с…')
        found,_=model.transcribe(samples[int(lo*rate):int(hi*rate)],language='uz',word_timestamps=True,beam_size=5,vad_filter=False,condition_on_previous_text=False,initial_prompt=recognition_prompt(project))
        words=[]
        for segment in found:
            words.extend(dict(word=w.word,start=max(s['start'],lo+w.start),end=min(s['end'],lo+w.end),probability=w.probability) for w in segment.words if lo+w.end>s['start'] and lo+w.start<s['end'])
        words=[w for w in words if w['end']>w['start']]
        retry=dict(start=s['start'],end=s['end'],words=words,text=' '.join(w['word'] for w in words))
        result.append(retry if preferable(s,retry,project.profile) else s)
    return result
