"""Match spoken forecasts by words and meaning, independently of ASR segments."""
import re
from .uzbek import norm

def compact(text):return re.sub(r'[^a-z0-9]','',norm(text))

def features(text):
    t=norm(text)
    # ASR commonly separates a decimal into two tokens ("3 ,5") and
    # contracts yarim+dan. Normalize only number/market forms, not prose.
    t=re.sub(r'(\d)\s*([,.])\s*(\d)',r'\1\2\3',t)
    t=re.sub(r"\b(bir|ikki|uch)\s*(?:yarim|yarm|yam)(?:t?i?dan(?:an)?|tana|danan|dan)?\b",r'\1 yarim',t)
    t=re.sub(r'\btanan\b','dan',t)
    c=compact(t)
    chance='x2' if re.search(r'x(?:2|ikki)|[ei]ks?ik{1,2}i|sikki|2x',c) else '1x' if re.search(r"\b1\s*x\b|\bbir\s*(?:iks|eks)\b",t) else '12' if re.search(r"\b12(?=\s+(?:va|variant)\b|$)",t) else None
    double=chance is not None or bool(re.search(r'yutqaz[ai]?m',c))
    winner=bool(re.search(r'[gq]alab',c)) and not double
    cue=bool(re.search(r'tanlo|talno|variy?a|qildik|qilardik|qilaqold',c))
    phonetic_total=bool(cue and re.search(r"\bko'l\b",t) and ("ko'p" in t or re.search(r'\bkam\b',t)))
    total='total' in t or bool(re.search(r'g[ou]i?l',c) or ('umumiy' in c and ("ko'p" in t or 'son' in c)) or phonetic_total)
    ordinal=next((n for pattern,n in ((r'\bbirinchi',0),(r'\b(?:ikkinchi|ikinchi|kinchi|ekin(?:chi|ji))',1),(r'\buch(?:i|ri)nchi',2),(r'\b(?:tortinchi|to.rt.inchi)',3),(r'\boxirgi',-1)) if re.search(pattern,t)),None)
    if ordinal is None:
        ordinal=next((n for n,word in enumerate(['beshinchi','oltinchi','yettinchi','sakkizinchi',"to'qqizinchi", "o'ninchi"],4) if word in t),None)
    if ordinal is None:
        numeric=re.search(r'\b(\d+)\s*[- ]?(?:inchi|chi)\b',t)
        if numeric:ordinal=int(numeric[1])-1
    value=re.search(r"\b(\d+(?:[,.]\d+)?)\s*(?:ta)?dan\s+(?:ko'p|kam)\b",t)
    if value:value=float(value[1].replace(',','.'))
    else:
        value=next((n+.5 for word,n in [('bir',1),('ikki',2),('uch',3),('to.rt',4)] if re.search(r'\b'+word+r'\s+(?:yarim|butun\s+besh)',t)),None)
    direction='under' if re.search(r'\bkam\b',t) else 'over' if "ko'p" in t else None
    return dict(chance=chance,double=double,winner=winner,total=total,cue=cue,ordinal=ordinal,value=value,direction=direction)

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

def active_name_hits(team,words):
    """Ignore names explicitly rejected with emas, including fuzzy multiword hits."""
    from .uz_speech import name_hits
    result=[]
    for start,end,strength in name_hits(team,words):
        context=norm(' '.join(w['word'] for w in words[start:min(len(words),end+3)]))
        if re.search(r"\bemas\b",context):continue
        result.append((start,end,strength))
    return result


def score(candidate,owner,reference,index,owners,recap=True):
    from .uz_speech import name_hits
    from .graphics import block_teams
    f=candidate['features'];expected=features(reference)
    ordinal=f['ordinal'];ordinal=len(owners)-1 if ordinal==-1 else ordinal
    strengths=[max([h[2] for team in block_teams(b.title) for h in active_name_hits(team,candidate['words'])]+[0.]) for b in owners]
    own=strengths[index]>=.78 or (ordinal==index and strengths[index]>=.74)
    # Weak phonetic resemblance to another club cannot overrule an explicit
    # episode ordinal. Clear foreign names still reject a different owner.
    others=any(v>=.9 for k,v in enumerate(strengths) if k!=index)
    if others and not own:return None
    # Inside one already identified match, "my second choice" is the episode
    # ordinal, not index zero of this single-owner search.
    if ordinal is not None and ordinal!=index and (recap or len(owners)>1):return None
    if recap and len(owners)>1:
        ordinals={features(w['word'])['ordinal'] for w in candidate['words']}-{None}
        ordinals={len(owners)-1 if n==-1 else n for n in ordinals}
        if len(ordinals)>1 or not (own or ordinal is not None):return None
    if not (f['cue'] or own or ordinal is not None):return None
    if not recap and not f['cue']:return None
    if expected['value'] is not None and f['value'] is not None and expected['value']!=f['value']:return None
    if expected['direction'] and f['direction'] and expected['direction']!=f['direction']:return None
    # An explicit different market must not be silently turned into the scripted bet.
    if f['chance'] and expected['chance'] and f['chance']!=expected['chance']:return None
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
    if not recap and re.match(r'\s*(?:tanlo|talno)',norm(candidate['text'])):strength+=4
    strength-=.035*(candidate['end']-candidate['start'])
    review=bool(re.search(r'\b2\s*x\b',norm(candidate['text']))) or matched<len(required) or (expected['value'] is not None and f['value'] is None) or (recap and strengths[index]<.85)
    numeric=[w for w in candidate['words'] if re.search(r'\d',w['word'])]
    if numeric and min(w.get('probability',1.) for w in numeric)<.55:review=True
    return strength,review

def match_forecasts(segments,lo,hi,owners,references,recap=True,partial=False):
    candidates=windows(segments,lo,hi)
    # A single ASR sentence may reject one market and then announce another.
    # Start a separate candidate at the explicit personal choice, keeping its
    # own words and times instead of inheriting the rejected first number.
    for unit in clauses(segments,lo,hi):
        for k,w in enumerate(unit):
            if not re.search(r'\b(?:tanlo|talno)[vy]?(?:im|yim|v|y)',norm(w['word'])):continue
            selected=unit[k:]
            if selected[-1]['end']-selected[0]['start']>24:continue
            text=' '.join(w['word'].strip() for w in selected)
            candidates.append(dict(start=selected[0]['start'],end=selected[-1]['end'],text=text,words=selected,features=features(text)))
    if recap and len(owners)>1:
        # ASR may put several fixture recaps in one sentence. Split by ownership.
        from .graphics import block_teams
        for words in clauses(segments,lo,hi):
            tagged=[]
            for k,owner in enumerate(owners):
                for team in block_teams(owner.title):
                    tagged.extend((a,z,k) for a,z,strength in active_name_hits(team,words) if strength>=.88)
            tagged.sort();starts=[];last=None
            for a,z,k in tagged:
                if k!=last:starts.append(a);last=k
            if len(starts)<2:continue
            starts[0]=0
            for a,z in zip(starts,starts[1:]+[len(words)]):
                selected=words[a:z]
                if not selected:continue
                text=' '.join(w['word'] for w in selected)
                candidates.append(dict(start=selected[0]['start'],end=selected[-1]['end'],text=text,words=selected,features=features(text)))
    if not recap:
        # One analysis has its own known fixture; ordinals describe episode position.
        for c in candidates:
            c['features']['ordinal']=None
            t=norm(c['text'])
            if c['start']>=lo+(hi-lo)*.5 and re.search(r'kutilmoqda|yutqaz[ai]?m',t) and not re.search(r'olmagan|olmayman|yoqmagan',t):c['features']['cue']=True
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
                    if longer['start']>c['start'] or not c['end']<longer['end']<=c['end']+10:continue
                    tail=[w for w in longer['words'] if w['start']>=c['start']]
                    f=features(' '.join(w['word'] for w in tail))
                    if f['value'] is None or f['value']==expected['value']:continue
                    from .uz_speech import name_hits
                    from .graphics import block_teams
                    foreign=any(name_hits(team,longer['words']) for k,b in enumerate(owners) if k!=index for team in block_teams(b.title))
                    if not foreign and f['ordinal'] in (None,index):conflict=True;break
                if conflict:continue
            value,review=scored
            reason='Число или условие ставки распознано неуверенно. Проверьте только эту плашку.' if review else ''
            choices.append((value,{**c,'needs_review':review,'forecast_id':owner.uid,'review_reason':reason}))
        if not choices and not partial:
            raise ValueError('Не удалось связать '+('повтор прогноза' if recap else 'прогноз')+' «'+owner.title+'» с распознанной речью. Проверьте фразу ставки и границы раздела; количество разборов само по себе не является ошибкой.')
        scored_choices.append(choices)
    if len(owners)>8:
        # Sparse interval scheduling per owner avoids 2**N states. Ambiguous
        # collisions go to review instead of exponential memory consumption.
        chosen={};used=[]
        for index in sorted(range(len(owners)),key=lambda i:len(scored_choices[i])):
            feasible=[(v,c) for v,c in scored_choices[index] if all(c['end']<=a+.001 or c['start']>=b-.001 for a,b in used)]
            if not feasible:
                if partial:continue
                raise ValueError('Повторы требуют ручного распределения интервалов.')
            _,c=max(feasible,key=lambda pair:pair[0]);chosen[index]=c;used.append((c['start'],c['end']))
        return [chosen.get(i) for i in range(len(owners))]
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
    if not states.get(full) and partial:
        available=[(mask,max(rows,key=lambda row:row[0])) for mask,rows in states.items() if rows]
        _,best=max(available,key=lambda item:(item[0].bit_count(),item[1][0]))
        return [best[2].get(i) for i in range(len(owners))]
    if not states.get(full):
        raise ValueError('Не удалось разнести повторы ставок по времени без пересечений. Проверьте речь в итогах и выбранные границы.')
    chosen=max(states[full],key=lambda s:s[0])[2]
    return [chosen[i] for i in range(len(owners))]


def missing_forecast(segments,lo,hi,owner,occupied=()):
    """One explicitly uncertain placeholder; never downgrade unrelated cards."""
    words=[w for s in segments for w in s['words'] if lo<=w['start']<hi]
    free=[w for w in words if all(w['end']<=a or w['start']>=b for a,b in occupied)]
    if not free:return None
    from .graphics import block_teams
    named=[h for team in block_teams(owner.title) for h in active_name_hits(team,free)]
    cues=[i for i,w in enumerate(free) if re.search(r'tanlo|talno',norm(w['word']))]
    index=cues[-1] if cues else named[0][0] if named else max(0,len(free)-8)
    selected=[free[index]]
    for w in free[index+1:]:
        if w['start']-selected[-1]['end']>1 or w['end']-selected[0]['start']>5:break
        selected.append(w)
    a,z=selected[0]['start'],min(hi,selected[-1]['end'])
    if z-a<.15:return None
    return dict(start=a,end=z,text=' '.join(w['word'] for w in selected),words=selected,
                needs_review=True,forecast_id=owner.uid,
                review_reason='Не удалось уверенно распознать эту ставку: '+owner.title+'. Проверьте текст и время только этой плашки.')
