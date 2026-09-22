"""Protect intro promotions using the spoken first pair after a transition cue."""
import re
from difflib import SequenceMatcher


def intro_floor(words,language='ru',limit=150):
    early=[w for w in words if w['start']<limit];floor=0.;promo=False
    for i,w in enumerate(early):
        text=' '.join(v['word'].strip().lower() for v in early[i:i+6]).replace('ё','е');text=re.sub(r'[^\w\s\'’]','',text)
        cue=re.match(r'(?:переходим\s+к\s+разбор\w*|начинаем\s+разбор\w*|boshladik|boshlaymiz|tahlilga\s+o.tamiz)\b',text)
        if cue:return max(floor,early[min(len(early)-1,i+len(cue.group().split())-1)]['end'])
        if re.search(r'телеграм|telegram',w['word'],re.I):promo=True;floor=max(floor,w['end'])
        if promo and re.search(r'описани|tavsif|havola|izoh',w['word'],re.I):floor=max(floor,w['end'])
    return floor


def first_analysis_start(blocks,segments):
    if not blocks or blocks[0].kind!='intro':return None
    first=next((b for b in blocks if b.kind=='analysis'),None)
    if first is None:return None
    words=[w for s in segments for w in s.get('words',[])];floor=intro_floor(words)
    from .ru_speech import tokens
    from .graphics import block_teams
    targets=[tokens(n) for n in block_teams(first.title) if n]
    if len(targets)!=2 or floor<=0:return None
    for i,w in enumerate(words):
        if not floor-.01<=w['start']<=min(floor+65,180):continue
        if not any(any(SequenceMatcher(None,t,n).ratio()>=.65 for n in target) for target in targets for t in tokens(w['word'])):continue
        hay=tokens(' '.join(v['word'] for v in words[i:i+18]));positions=[]
        for target in targets:
            choices=[]
            for j in range(len(hay)-len(target)+1):
                scores=[SequenceMatcher(None,a,b).ratio() for a,b in zip(target,hay[j:j+len(target)])]
                if min(scores)>=.65:choices.append((sum(scores)/len(scores),j))
            positions.append(max(choices) if choices else None)
        if all(positions) and min(p[0] for p in positions)>=.75 and 0<abs(positions[0][1]-positions[1][1])<=max(len(t) for t in targets)+3:return w['start']
    return None


def slice_segments(segments,lo,hi):
    result=[]
    for s in segments:
        words=[dict(w,end=min(w['end'],hi)) for w in s.get('words',[]) if lo<=w['start']<hi]
        if words:result.append(dict(start=words[0]['start'],end=words[-1]['end'],text=' '.join(w['word'] for w in words),words=words))
    return result
