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
    from .ru_speech import speech_word_units
    words=speech_word_units([w for s in segments for w in s.get('words',[])]);floor=intro_floor(words)
    from .ru_speech import tokens
    from .graphics import block_teams
    targets=[tokens(n) for n in block_teams(first.title) if n]
    if floor<=0:return script_analysis_start(blocks,segments)
    if len(targets)!=2:return None
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
    candidate=script_analysis_start(blocks,segments)
    return candidate if candidate is not None and candidate>=floor-.01 else None


def slice_segments(segments,lo,hi):
    result=[]
    for s in segments:
        words=[dict(w,end=min(w['end'],hi)) for w in s.get('words',[]) if lo<=w['start']<hi]
        if words:result.append(dict(start=words[0]['start'],end=words[-1]['end'],text=' '.join(w['word'] for w in words),words=words))
    return result


def recap_cue(text):
    value=text.strip().lower().strip('#* ').replace('ё','е')
    return bool(re.match(r'(?:итоги(?:\s+выпуска)?[.:]?\s*$|итак[, :]|подвед[её]м\s+итог|подытожим|напомню.{0,25}(?:выбор|ставк|прогноз)|повтор(?:ю|им).{0,25}(?:выбор|ставк|прогноз)|(?:коротко|в\s+итоге|на\s+сегодня).{0,35}(?:выбор|ставк|прогноз)|теперь\s+к\s+итогам)',value))


def script_analysis_start(blocks,segments):
    """Use the first analysis body as an anchor when intro has no stock CTA.

    Require a strong body match *and* a preceding introductory script match.
    Pair names repeated in the intro alone never trigger this boundary.
    """
    from .alignment import split_script
    from .ru_speech import tokens
    from .framing import prepared_script
    first=next((b for b in blocks if b.kind=='analysis'),None)
    if first is None:return None
    body=[t for t in split_script(first.script) if t.strip('. ')!=first.title.strip('. ')]
    if not body:return None
    target=tokens(' '.join(body[:2]))[:24]
    if len(target)<6:return None
    from .ru_speech import speech_word_units
    words=speech_word_units([w for s in segments for w in s.get('words',[])]);flat=[];owners=[]
    for i,w in enumerate(words):
        ts=tokens(w['word']);flat+=ts;owners += [i]*len(ts)
    intro=tokens(prepared_script(blocks[0]));matches=[]
    for i in range(len(flat)):
        if words[owners[i]]['start']>180:break
        if flat[i:i+2]!=target[:2]:continue
        score=SequenceMatcher(None,target,flat[i:i+len(target)],autojunk=False).ratio()
        prefix=flat[:i]
        covered=sum(n for _,_,n in SequenceMatcher(None,intro,prefix,autojunk=False).get_matching_blocks())/max(1,len(intro))
        if score>=.8 and covered>=.6:matches.append((score,i))
    if not matches:return None
    _,i=max(matches)
    # Include a separately spoken pair directly before the body anchor.
    from .graphics import block_teams
    from .event_rules import team_position
    start=owners[i];names=block_teams(first.title)
    for j in range(max(0,start-10),start):
        phrase=' '.join(w['word'] for w in words[j:start])
        if words[start]['start']-words[j]['start']<=6 and all(team_position(n,phrase,names) is not None for n in names):
            start=j;break
    return words[start]['start']
