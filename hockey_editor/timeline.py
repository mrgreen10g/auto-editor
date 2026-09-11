"""Frame-exact cuts and automatic semantic placements."""
import re, math
from dataclasses import dataclass, asdict, field

@dataclass
class Line:
    text: str
    start: float
    end: float
    agreement: float = 0.0

@dataclass
class Insert:
    path: str
    start: float
    end: float
    source_in: float
    label: str
    context_label: str = ''
    source_min: float = 0.
    source_max: float | None = None

@dataclass
class Card:
    start: float
    end: float
    title: str
    text: str
    line: int = -1

@dataclass
class Plan:
    source_start: float
    source_end: float
    keep: list
    lines: list[Line]
    inserts: list[Insert]
    cards: list[Card]
    warnings: list[str]
    duration: float
    rotation: int | None = None
    sections: list = field(default_factory=list)

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,d):
        d=dict(d)
        for k,t in [('lines',Line),('inserts',Insert),('cards',Card)]:d[k]=[t(**x) for x in d[k]]
        return cls(**d)

def frame(t,fps=30): return round(t*fps)/fps

def format_time(seconds):
    ticks=round(float(seconds)*100)
    return f'{ticks//6000:02}:{ticks//100%60:02}.{ticks%100:02}'

def parse_time(text):
    parts=str(text).strip().replace(',','.').split(':')
    if not 1<=len(parts)<=3:raise ValueError('Введите время в формате ММ:СС.сс')
    values=[float(p) for p in parts]
    if not all(math.isfinite(v) and v>=0 for v in values):raise ValueError('Время должно быть положительным.')
    if len(values)>1 and any(v>=60 for v in values[1:]):raise ValueError('После двоеточия допустимы значения меньше 60.')
    if any(v!=int(v) for v in values[:-1]):raise ValueError('Доли секунды допустимы только в последнем поле.')
    return sum(v*60**(len(values)-i-1) for i,v in enumerate(values))

def game_transitions(plan):
    clips=sorted(plan.inserts,key=lambda c:c.start)
    links=[]
    for a,b in zip(clips,clips[1:]):
        gap=frame(b.start-a.end)
        same=not any(a.start<s['start']<=b.start for s in plan.sections)
        links.append(same and 0<=gap<=.35)
    for i,c in enumerate(clips):
        before=i>0 and links[i-1];after=i<len(links) and links[i]
        # Hold only a validated game frame across a very short gap, never pull
        # unverified source frames (crowd/celebration) past the selected bounds.
        tail=frame(clips[i+1].start-c.end) if after else 0
        yield c,tail,before,after

def keep_ranges(duration,silences,fps=30,enabled=True):
    total=round(duration*fps);cur=0;keep=[]
    if enabled:
        for a,b in silences:
            if b-a<.30:continue
            lo=max(cur,round((a+.12)*fps));hi=min(total,round((b-.10)*fps))
            if hi<=lo:continue
            if lo>cur:keep.append((cur/fps,lo/fps))
            cur=hi
    if cur<total:keep.append((cur/fps,total/fps))
    if not keep:raise ValueError('Не найден участок с речью.')
    return keep

def map_time(t,keep):
    out=0.
    for a,b in keep:
        if t<a:return out
        if t<=b:return out+t-a
        out+=b-a
    return out

def norm(text):return re.sub(r'\s+',' ',text.lower().replace('ё','е')).strip()

def placements(block,lines,clip_meta,duration,frequency='normal'):
    from .event_rules import explicit_reference,topic_for_phrase,suggested_names
    warnings=[];matched=[]
    for clip in block.clips:
        found=[i for i,l in enumerate(lines) if norm(clip.phrase) in norm(l.text)]
        if not found:
            warnings.append(f'Не найдена фраза «{clip.phrase}»: вставка пропущена.');continue
        if len(found)>1:
            warnings.append(f'Фраза «{clip.phrase}» встречается несколько раз: выбрано первое совпадение.')
        matched.append((found[0],clip))
    matched.sort(key=lambda x:x[0]);used=set();inserts=[];last_play_source=None
    early=[lines[i].start for i,c in matched if lines[i].start>0 and explicit_reference(c.phrase)]
    intro_end=min([5,duration]+early)
    for number,(idx,clip) in enumerate(matched):
        if idx in used:
            warnings.append(f'Две вставки к одной фразе: «{clip.phrase}» пропущена.');continue
        used.add(idx)
        l=lines[idx];start=l.start
        if number==0 and idx>1 and clip.kind!='play':start=max(lines[idx-1].start,l.start-3)
        end=l.end
        if number+1<len(matched):end=min(end,lines[matched[number+1][0]].start)
        length=clip_meta[clip.path]['duration']
        start=max(start,intro_end)  # The introduction belongs to the presenter.
        if clip.kind=='play' and not explicit_reference(clip.phrase):
            gap,maximum={'low':(15,3.5),'normal':(8,5),'high':(3,7)}[frequency]
            if inserts and start-inserts[-1].end<gap: continue
            source=clip.origin_path or clip.path
            flexible=clip.flexible_source or clip.context_label.startswith('Архив')
            # Spacing must not sample the same source every third event from an
            # otherwise balanced A/B/C sequence. Prefer a nearby alternate slot.
            if flexible and source==last_play_source and any(
                c.kind=='play' and (c.flexible_source or c.context_label.startswith('Архив'))
                and (c.origin_path or c.path)!=source and 0<lines[j].start-start<=8
                for j,c in matched[number+1:]):continue
            end=min(end,start+maximum)
        if end-start>length:start=end-length
        if end-start<.25:
            warnings.append(f'Слишком короткая фраза для «{clip.phrase}».');continue
        goal=clip.goal_time if clip.goal_time is not None else length*.58
        if goal>=length:raise ValueError(f'Положение события за пределами клипа: {clip.path}')
        source_in=max(0,min(goal-((l.start+l.end)/2-start),length-(end-start)))
        inserts.append(Insert(clip.origin_path or clip.path,frame(start),frame(end),source_in+clip.origin_start,
                              clip.phrase,clip.context_label,clip.origin_start,clip.origin_start+length))
        if clip.kind=='play':last_play_source=clip.origin_path or clip.path
    from .card_text import summarize_card,classify_card
    cards=[Card(0,intro_end,'РАЗБОР МАТЧА',block.title)] if intro_end>=.15 else []
    topic=next(iter(suggested_names(block.title)),'')
    for i,l in enumerate(lines):
        topic=topic_for_phrase(topic,l.text,block.title)
        if norm(l.text).rstrip('.')==norm(block.title):continue
        title=classify_card(l.text);body=summarize_card(title,l.text,topic) if title else l.text
        if str(i) in block.card_overrides:
            body=block.card_overrides[str(i)];title=title or 'ИНФОРМАЦИЯ'
        if title and body.strip() and l.end-l.start>=.15:
            cards.append(Card(l.start,l.end,title,body,i))
    return inserts,cards,warnings

def zoom_windows(duration,inserts):
    gaps=[];cur=0
    for c in sorted(inserts,key=lambda c:c.start):
        if c.start>cur:gaps.append((cur,c.start))
        cur=max(cur,c.end)
    if cur<duration:gaps.append((cur,duration))
    windows=[]
    for lo,hi in gaps:
        t=lo+.4
        # Complete a smooth 100→120→100 cycle even in shorter presenter shots.
        while hi-t>=3.6:
            span=min(5.8,hi-t-.15)
            up=span*.62;hold=span*.08
            windows.append((t,t+up,t+up+hold,t+span))
            t+=span+1.6
    return windows
