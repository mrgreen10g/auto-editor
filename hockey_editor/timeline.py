"""Frame-exact cuts and automatic semantic placements."""
import re, math
from dataclasses import dataclass, asdict

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

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls,d):
        d=dict(d)
        for k,t in [('lines',Line),('inserts',Insert),('cards',Card)]:d[k]=[t(**x) for x in d[k]]
        return cls(**d)

def frame(t,fps=30): return round(t*fps)/fps

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
    warnings=[];matched=[]
    for clip in block.clips:
        found=[i for i,l in enumerate(lines) if norm(clip.phrase) in norm(l.text)]
        if not found:
            warnings.append(f'Не найдена фраза «{clip.phrase}»: вставка пропущена.');continue
        if len(found)>1:
            warnings.append(f'Фраза «{clip.phrase}» встречается несколько раз: выбрано первое совпадение.')
        matched.append((found[0],clip))
    matched.sort(key=lambda x:x[0]);used=set();inserts=[]
    for number,(idx,clip) in enumerate(matched):
        if idx in used:
            warnings.append(f'Две вставки к одной фразе: «{clip.phrase}» пропущена.');continue
        used.add(idx)
        l=lines[idx];start=l.start
        if number==0 and idx>1 and clip.kind!='play':start=max(lines[idx-1].start,l.start-3)
        end=l.end
        if number+1<len(matched):end=min(end,lines[matched[number+1][0]].start)
        length=clip_meta[clip.path]['duration']
        start=max(start,min(5,duration))  # The introduction belongs to the presenter.
        if clip.kind=='play':
            gap,maximum={'low':(15,3.5),'normal':(8,5),'high':(3,7)}[frequency]
            if inserts and start-inserts[-1].end<gap: continue
            end=min(end,start+maximum)
        if end-start>length:start=end-length
        if end-start<.25:
            warnings.append(f'Слишком короткая фраза для «{clip.phrase}».');continue
        goal=clip.goal_time if clip.goal_time is not None else length*.58
        if goal>=length:raise ValueError(f'Положение события за пределами клипа: {clip.path}')
        source_in=max(0,min(goal-((l.start+l.end)/2-start),length-(end-start)))
        inserts.append(Insert(clip.origin_path or clip.path,frame(start),frame(end),source_in+clip.origin_start,
                              clip.phrase,clip.context_label,clip.origin_start,clip.origin_start+length))
    from .card_text import summarize_card
    cards=[Card(0,min(5,duration),'РАЗБОР МАТЧА',block.title)]
    for i,l in enumerate(lines):
        if any(c.start<l.end and c.end>l.start for c in inserts):continue
        t=norm(l.text);title='';body=l.text
        if i==0:continue
        if any(w in t for w in ('броск','переброс')):title='СТАТИСТИКА'
        elif any(w in t for w in ('выиграл','обыграл','уступил','победы в')) and re.search(r'\d',t):title='РЕЗУЛЬТАТ ВСТРЕЧИ'
        elif any(w in t for w in ('повреждени','травм')):title='СОСТАВ КОМАНДЫ'
        elif re.search(r'\b1[.,]\d{2}\b',t):title='КОЭФФИЦИЕНТ ИЗ РАЗБОРА'
        elif 'мой выбор' in t or 'форой плюс' in t:title='ПРОГНОЗ'
        elif 'возврат' in t or 'ставка выигрывает' in t:title='УСЛОВИЯ ПРОГНОЗА'
        elif 'по счёту жду' in l.text.lower() or 'по счету жду' in t:title='ОЖИДАЕМЫЙ СЧЁТ'
        if title: body=summarize_card(title,l.text)
        if str(i) in block.card_overrides:
            body=block.card_overrides[str(i)];title=title or 'ИНФОРМАЦИЯ'
        if title and body.strip() and l.end>5:cards.append(Card(max(5,l.start),l.end,title,body,i))
    return inserts,cards,warnings

def zoom_windows(duration,inserts):
    gaps=[];cur=0
    for c in sorted(inserts,key=lambda c:c.start):
        if c.start>cur:gaps.append((cur,c.start))
        cur=max(cur,c.end)
    if cur<duration:gaps.append((cur,duration))
    windows=[]
    for lo,hi in gaps:
        t=lo+1
        while t+7.4<hi-.2:
            windows.append((t,t+5,t+5.4,t+7.4))
            t+=11.4
    return windows
