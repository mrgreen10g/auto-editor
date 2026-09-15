"""Match spoken forecasts by words and meaning, independently of ASR segments."""
import re
from .uzbek import norm

def compact(text):return re.sub(r'[^a-z0-9]','',norm(text))

def features(text):
    t=norm(text);c=compact(text)
    double=bool(re.search(r'x(?:2|ikki)|[ei]ks?ik{1,2}i|sikki',c))
    winner=bool(re.search(r'[gq]alab',c)) and not double
    cue=bool(re.search(r'tanlo|varia|qildik|qilaqold',c))
    phonetic_total=bool(cue and re.search(r"\bko'l\b",t) and ("ko'p" in t or re.search(r'\bkam\b',t)))
    total=bool(re.search(r'g[ou]i?l',c) or ('umumiy' in c and ("ko'p" in t or 'son' in c)) or phonetic_total)
    ordinal=next((n for pattern,n in ((r'\bbirinchi',0),(r'\b(?:ikkinchi|ikinchi|kinchi|ekin(?:chi|ji))',1),(r'\buch(?:i|ri)nchi',2),(r'\b(?:tortinchi|to.rt.inchi)',3),(r'\boxirgi',-1)) if re.search(pattern,t)),None)
    value=re.search(r"\b(\d+(?:[,.]\d+)?)\s*(?:ta)?dan\s+(?:ko'p|kam)\b",t)
    if value:value=float(value[1].replace(',','.'))
    else:
        value=next((n+.5 for word,n in [('bir',1),('ikki',2),('uch',3),('to.rt',4)] if re.search(r'\b'+word+r'\s+yarim',t)),None)
    direction='under' if re.search(r'\bkam\b',t) else 'over' if "ko'p" in t else None
    return dict(double=double,winner=winner,total=total,cue=cue,ordinal=ordinal,value=value,direction=direction)

def clauses(segments,lo,hi):
    words=[dict(w) for s in segments for w in s['words'] if lo<=w['start']<hi]
    result=[];current=[]
    for word in words:
        ordinal=features(word['word'])['ordinal']
        if current and ((ordinal is not None and len(current)>2) or word['start']-current[-1]['end']>1.6):
            result.append(current);current=[]
        current.append(word)
        if re.search(r'[.!?;][”"»\s]*$',word['word']):result.append(current);current=[]
    if current:result.append(current)
    return result

def windows(segments,lo,hi):
    units=clauses(segments,lo,hi);result=[]
    for i in range(len(units)):
        words=[]
        for j in range(i,min(len(units),i+3)):
            if j>i and units[j][0]['start']-units[j-1][-1]['end']>1.6:break
            words+=units[j]
            if words[-1]['end']-words[0]['start']>34:break
            text=' '.join(w['word'].strip() for w in words)
            result.append({'start':words[0]['start'],'end':words[-1]['end'],'text':text,'words':words[:],'features':features(text)})
    return result

def score(candidate,owner,reference,index,owners,recap=True):
    from .uz_speech import name_hits
    from .graphics import block_teams
    f=candidate['features'];expected=features(reference)
    team_hits=[bool(any(h[2]>=.78 for team in block_teams(b.title) for h in name_hits(team,candidate['words']))) for b in owners]
    own=team_hits[index];others=any(v for k,v in enumerate(team_hits) if k!=index)
    ordinal=f['ordinal'];ordinal=len(owners)-1 if ordinal==-1 else ordinal
    if others and not own:return None
    if ordinal is not None and ordinal!=index:return None
    if recap and len(owners)>1:
        ordinals={features(w['word'])['ordinal'] for w in candidate['words']}-{None}
        ordinals={len(owners)-1 if n==-1 else n for n in ordinals}
        if len(ordinals)>1 or not (own or ordinal is not None):return None
    if not (f['cue'] or own or ordinal is not None):return None
    if not recap and not f['cue']:return None
    if expected['value'] is not None and f['value'] is not None and expected['value']!=f['value']:return None
    if expected['direction'] and f['direction'] and expected['direction']!=f['direction']:return None
    # An explicit different market must not be silently turned into the scripted bet.
    if f['double'] and expected['winner']:return None
    if f['winner'] and expected['double'] and not f['double']:return None
    if f['double'] and not expected['double']:return None
    if f['winner'] and not expected['winner']:return None
    required=[key for key in ('double','winner','total') if expected[key]]
    matched=sum(bool(f[key]) for key in required)
    if not required or not matched:return None
    strength=matched*6+(4 if own and recap else 0)+(2 if ordinal is not None else 0)+(1 if f['cue'] else 0)
    if not recap and re.search(r'varia|qildik|qila qold',norm(candidate['text'])):strength+=3
    if others:strength-=9
    strength-=.035*(candidate['end']-candidate['start'])
    review=matched<len(required) or (expected['value'] is not None and f['value'] is None)
    return strength,review

def match_forecasts(segments,lo,hi,owners,references,recap=True):
    candidates=windows(segments,lo,hi)
    if not recap:
        # One analysis has its own known fixture; ordinals describe episode position.
        for c in candidates:c['features']['ordinal']=None
    scored_choices=[]
    for index,owner in enumerate(owners):
        choices=[]
        for c in candidates:
            scored=score(c,owner,references[owner.uid],index,owners,recap)
            if scored is None:continue
            expected=features(references[owner.uid])
            if scored[1] and expected['value'] is not None:
                # A split compound bet must not hide a contradictory second half.
                conflict=False
                for longer in candidates:
                    if longer['start']!=c['start'] or not c['end']<longer['end']<=c['end']+10:continue
                    f=longer['features']
                    if f['value'] is None or f['value']==expected['value']:continue
                    from .uz_speech import name_hits
                    from .graphics import block_teams
                    foreign=any(name_hits(team,longer['words']) for k,b in enumerate(owners) if k!=index for team in block_teams(b.title))
                    if not foreign and f['ordinal'] in (None,index):conflict=True;break
                if conflict:continue
            value,review=scored
            choices.append((value,{**c,'needs_review':review,'forecast_id':owner.uid}))
        if not choices:
            raise ValueError('Не удалось связать '+('повтор прогноза' if recap else 'прогноз')+' «'+owner.title+'» с распознанной речью. Проверьте фразу ставки и границы раздела; количество разборов само по себе не является ошибкой.')
        scored_choices.append(choices)
    # One disjoint spoken interval per fixture, in any spoken order.
    states={0:[(0.,-1.,{})]};full=(1<<len(owners))-1
    for mask in range(full+1):
        frontier=[];best=float('-inf')
        for state in sorted(states.get(mask,[]),key=lambda s:(s[1],-s[0])):
            if state[0]>best:frontier.append(state);best=state[0]
        states[mask]=frontier
        for index,choices in enumerate(scored_choices):
            if mask&(1<<index):continue
            for value,c in choices:
                eligible=[s for s in frontier if s[1]<=c['start']+.001]
                if not eligible:continue
                previous=max(eligible,key=lambda s:s[0])
                states.setdefault(mask|(1<<index),[]).append((previous[0]+value,c['end'],{**previous[2],index:c}))
    if not states.get(full):
        raise ValueError('Не удалось разнести повторы ставок по времени без пересечений. Проверьте речь в итогах и выбранные границы.')
    chosen=max(states[full],key=lambda s:s[0])[2]
    return [chosen[i] for i in range(len(owners))]
