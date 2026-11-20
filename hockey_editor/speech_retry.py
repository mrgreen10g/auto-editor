"""Recheck only acoustic/ASR disagreements that can conceal a restart."""
import json,hashlib,wave
from pathlib import Path
from difflib import SequenceMatcher
import numpy as np
from .speech_cleanup import merge_ranges

def windows(segments,regions,duration):
 words=[w for s in segments for w in s.get('words',[])];suspect=[]
 for a,b in zip(words,words[1:]):
  if b['start']-a['end']>2 and sum(max(0,min(b['start']-.6,y)-max(a['end']+.6,x)) for x,y in regions)>.4:
   suspect.append((max(0,a['end']-5),min(duration,b['start']+12)))
 for w in words:
  if w['end']-w['start']>1.5:suspect.append((max(0,w['start']-8),min(duration,w['end']+7)))
 return merge_ranges(suspect)

def improve(project,segments,regions,duration,cache,cancel,log):
 from .ru_speech import model_path,recording_key,tokens
 from .speech_cache import prepared_audio,with_model
 selected=windows(segments,regions,duration)
 if not selected:return segments
 folder=Path(cache)/'ru-speech';folder.mkdir(parents=True,exist_ok=True)
 key=hashlib.sha256(json.dumps([recording_key(project),selected,'retry-pauses-v4']).encode()).hexdigest()
 target=folder/(key+'.retakes.json')
 if target.exists():return json.loads(target.read_text(encoding='utf-8'))
 audio=prepared_audio(project,folder,cancel,log)
 with wave.open(str(audio),'rb') as src:x=np.frombuffer(src.readframes(src.getnframes()),dtype='<i2').astype(np.float32)/32768.
 current=[w for s in segments for w in s.get('words',[])]
 def work(model):
  nonlocal current
  for index,(a,b) in enumerate(selected):
   if cancel.is_set():
    from .media import Cancelled
    raise Cancelled('Отменено.')
   log(f'Перепроверяю повтор после паузы {index+1}/{len(selected)}: {a:.1f}–{b:.1f} с.')
   rows,_=model.transcribe(x[round(a*16000):round(b*16000)],language='ru',word_timestamps=True,vad_filter=True,condition_on_previous_text=False,beam_size=5)
   replacement=[dict(word=w.word,start=a+w.start,end=a+w.end,probability=w.probability) for s in rows for w in s.words or [] if w.end>w.start]
   lo=a+2 if a else 0;hi=b-2 if b<duration else duration
   old=[w for w in current if lo<=w['start']<hi];new=[w for w in replacement if lo<=w['start']<hi]
   ta=tokens(' '.join(w['word'] for w in old));tb=tokens(' '.join(w['word'] for w in new))
   if not ta or not tb:continue
   matched=sum(m.size for m in SequenceMatcher(None,ta,tb,autojunk=False).get_matching_blocks())
   if matched/max(1,len(ta))<.65 or len(tb)<len(ta)+2:continue
   current=[w for w in current if not lo<=w['start']<hi]+new
  current.sort(key=lambda w:w['start'])
  return [dict(text=' '.join(w['word'] for w in current),start=current[0]['start'],end=current[-1]['end'],words=current)] if current else segments
 result=with_model(model_path(cancel,log),work,log)
 target.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
 return result
