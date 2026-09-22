"""Recoverable speech drafts and durable review decisions in timeline coordinates.

Only speech ambiguity enters this module. File, decoder and plan validation errors
remain errors. Estimated intervals are always marked; they never claim ASR proof.
"""
import copy
import hashlib
import json
import re
from difflib import SequenceMatcher
from dataclasses import asdict, replace
import numpy as np
from .timeline import Line, Card, Plan, frame, map_time


def draft_alignment(blocks, segments, duration, reason):
    from .alignment import split_script
    from .framing import prepared_script
    from .ru_speech import tokens
    from .uzbek import norm, spoken_uz
    def tokenize(text, language):
        if language=='ru':return tokens(text)
        return re.findall(r"[a-z0-9']+",spoken_uz(norm(text)))
    language=blocks[0].language
    if blocks[0].language=='ru' and len(blocks)>1 and blocks[0].kind=='intro':
        from .speech_boundaries import first_analysis_start,slice_segments
        boundary=first_analysis_start(blocks,segments)
        if boundary:
            left=draft_alignment(blocks[:1],slice_segments(segments,0,boundary),boundary,reason)
            shifted=copy.deepcopy(slice_segments(segments,boundary,float('inf')))
            for item in shifted:
                item['start']-=boundary;item['end']-=boundary
                for w in item['words']:w['start']-=boundary;w['end']-=boundary
            right=draft_alignment(blocks[1:],shifted,duration-boundary,reason)
            for lines,_ in right.values():
                for line in lines:line.start+=boundary;line.end+=boundary
            return {**left,**right}
    words=[w for s in segments for w in s.get('words',[]) if w['end']>w['start']]
    rows=[];script=[];source=[];stamps=[]
    for block in blocks:
        clean=copy.copy(block);clean.asr_lines=[]
        for index,text in enumerate(split_script(prepared_script(clean))):
            ts=tokenize(text,language) or ['?'];lo=len(script);script.extend(ts)
            rows.append((block,index,text,lo,len(script)))
    for w in words:
        ts=tokenize(w['word'],language)
        for k,t in enumerate(ts):
            source.append(t);stamps.append((w['start']+(w['end']-w['start'])*k/len(ts),w['start']+(w['end']-w['start'])*(k+1)/len(ts)))
    mapping={}
    for a,b,n in SequenceMatcher(None,script,source,autojunk=False).get_matching_blocks():
        for k in range(n):mapping[a+k]=b+k
    # Reserve at least six frames per row. No speech is removed in this draft.
    if duration<=0:raise ValueError('Исходник не содержит времени для разметки.')
    gap=min(.2,duration/max(1,len(rows)))
    keys=sorted(mapping);times=[stamps[mapping[k]][0] for k in keys]
    starts=[]
    for i,(_,_,_,lo,hi) in enumerate(rows):
        guess=float(np.interp(lo,keys,times)) if keys else duration*lo/max(1,len(script))
        if i==0:guess=0.
        starts.append(min(duration-(len(rows)-i)*gap,max(starts[-1]+gap if starts else 0,guess)))
    starts.append(duration)
    result={b.uid:([],[]) for b in blocks}
    global_weak=len(mapping)<.55*max(1,len(script))
    for i,(b,index,text,lo,hi) in enumerate(rows):
        coverage=sum(k in mapping for k in range(lo,hi))/max(1,hi-lo)
        anchored=any(k in mapping for k in range(lo,min(hi,lo+2)))
        next_anchor=i+1==len(rows) or any(k in mapping for k in range(rows[i+1][3],min(rows[i+1][4],rows[i+1][3]+2)))
        uncertain=global_weak or coverage<.7 or not anchored or not next_anchor
        message=('Нет надёжного совпадения. '+reason) if uncertain else ''
        heard=' '.join(w['word'].strip() for w in words if starts[i]<=w['start']<starts[i+1])
        result[b.uid][0].append(Line(text,starts[i],starts[i+1],1. if uncertain else 0.,message,heard,f'{b.uid}:line:{index}'))
    for lines,warnings in result.values():warnings.append('Черновые тайминги: речь сохранена полностью; плашки требуют ручной проверки.')
    return result


def fallback_cards(project, block, lines, duration, reason):
    """Retain scripted overlays even when team/market/CTA matching is ambiguous."""
    from .framing import forecast_text, pair_matches, optional_subscription
    from .card_text import classify_card,summarize_card
    from .uzbek import classify,mentions,norm
    from .media import probe
    owners=[b for b in project.blocks if b.kind=='analysis']
    cards=[];seen=set()
    for i,line in enumerate(lines):
        low=norm(line.text);title,body=classify(line.text) if block.language=='uz' else (classify_card(line.text),'')
        if title and not body:body=summarize_card(title,line.text)
        pairs=[b for b in owners if (mentions(b.title,line.text) if block.language=='uz' else pair_matches(line.text,b))]
        if block.kind=='intro' and pairs:
            for b in pairs:
                cards.append(Card(line.start,line.end,'РАЗБОР МАТЧА',b.title,i,review_reason=reason));seen.add(b.uid)
            continue
        if block.kind=='outro' and pairs and ('комментари' not in low and 'izoh' not in low):
            for b in pairs:
                cards.append(Card(line.start,line.end,'ПРОГНОЗ',forecast_text(b) or line.text,i,forecast_id=b.uid,review_reason=reason));seen.add(b.uid)
            continue
        if 'телеграм' in low or 'telegram' in low:
            asset=project.assets.get('telegram','')
            cards.append(Card(line.start,line.end,'ТЕЛЕГРАМ','Telegram',i,asset,review_reason=reason));continue
        if re.search(r'подписывай|ставьте\s+лайк|obuna|layk',low):
            asset=project.assets.get('subscribe','')
            if asset:
                cards.append(Card(line.start,frame(line.start+probe(asset)['duration']),'ПОДПИСКА','Подписка',i,asset,review_reason=reason))
            else:cards.append(Card(line.start,line.end,'ИНФОРМАЦИЯ',line.text,i,review_reason='Нет анимации подписки. '+reason))
            continue
        if title:cards.append(Card(line.start,line.end,title,body or line.text,i,review_reason=reason))
    if block.kind in ('intro','outro'):
        for k,b in enumerate(owners):
            if b.uid in seen:continue
            # Keep every expected overlay, but never describe this slot as confirmed.
            start=max(0,min(duration-.2,duration*k/max(1,len(owners))))
            end=min(duration,start+max(.2,min(4,duration/max(1,len(owners)))))
            title='ПРОГНОЗ' if block.kind=='outro' else 'РАЗБОР МАТЧА'
            text=(forecast_text(b) or b.title+' — уточните прогноз') if block.kind=='outro' else b.title
            cards.append(Card(start,end,title,text,forecast_id=b.uid if block.kind=='outro' else '',review_reason='Фраза не найдена: предложено предварительное время. '+reason))
    return optional_subscription(cards,duration)


def input_key(project, block):
    from .host_media import identity
    data=[project.profile,[identity(p) for p in project.host_paths()],block.uid,block.script,project.recording_times]
    return hashlib.sha256(json.dumps(data,ensure_ascii=False).encode()).hexdigest()


def attach(plan, block, project):
    """Create stable, persistent tasks after all automatic overlay generation."""
    plan.input_key=input_key(project,block)
    counts={}
    from .framing import forecast_text
    if block.kind=='analysis' and not (block.sport=='combat' and not forecast_text(block)) and not any(c.title=='ПРОГНОЗ' for c in plan.cards):
        from .framing import forecast_text
        text=forecast_text(block) or block.title+' — уточните прогноз'
        a=max(0,plan.duration-5)
        plan.cards.append(Card(a,plan.duration,'ПРОГНОЗ',text,forecast_id=block.uid,review_reason='Основной прогноз не найден уверенно. Плашка сохранена для проверки.'))
    for i,line in enumerate(plan.lines):
        if not line.review_id:line.review_id=f'{block.uid}:line:{i}'
        annotation=block.speech_cards.get(str(i),{})
        if annotation.get('needs_review') and not line.review_reason:line.review_reason=annotation.get('review_reason','Слова или принадлежность плашки определены неуверенно.')
        if line.agreement>.8 and not line.review_reason:line.review_reason='Неуверенная привязка фразы к записи.'
        if line.review_reason and not any(c.line==i for c in plan.cards):
            plan.cards.append(Card(line.start,line.end,'ИНФОРМАЦИЯ',line.text or block.title,i,review_reason=line.review_reason))
    for card in plan.cards:
        if card.title=='ПРОГНОЗ' and block.kind=='analysis':card.forecast_id=block.uid
        line=plan.lines[card.line] if 0<=card.line<len(plan.lines) else None
        seed=f'{block.uid}:{card.title}:{card.forecast_id}:{line.review_id if line else card.text}'
        count=counts.get(seed,0);counts[seed]=count+1
        if not card.review_id:card.review_id=hashlib.sha256((seed+str(count)).encode()).hexdigest()[:20]
        reason=card.review_reason or (line.review_reason if line else '')
        if block.language=='uz' and line and not line.recognized:line.recognized=line.text
        if reason:
            card.review_reason=reason
            plan.review_items.append(dict(id=card.review_id,block_id=block.uid,start=card.start,end=card.end,
                reason=reason,script=script_context(block,card,line),recognized=line.recognized if line else '',status='pending'))
    plan.edit_baseline={'cards':[asdict(c) for c in plan.cards],'inserts':[asdict(c) for c in plan.inserts]}
    return plan


def pending(plan):return [x for x in plan.review_items if x['status']=='pending']


def source_time(plan,t):
    from .episode import source_time as convert
    return convert(plan,t)


def output_time(plan,t):return frame(map_time(t-plan.source_start,plan.keep))


def preserve_edits(previous,plan):
    """Rebase actual user deltas onto regenerated timing; don't overwrite new ASR.

    The media/script fingerprint must agree. Unplaceable edits stay in a pending
    task with their old values, rather than being silently discarded.
    """
    if not previous:return plan
    old=Plan.from_dict(copy.deepcopy(previous))
    if not old.input_key or old.input_key!=plan.input_key or not old.edit_baseline:return plan
    baseline={c['review_id']:c for c in old.edit_baseline.get('cards',[])}
    current={c.review_id:c for c in old.cards}
    deleted=set(baseline)-set(current)
    plan.cards=[c for c in plan.cards if c.review_id not in deleted]
    fresh={c.review_id:c for c in plan.cards}
    for ident,card in current.items():
        if ident in baseline and asdict(card)==baseline[ident]:continue
        changed=copy.deepcopy(card)
        changed.start=output_time(plan,source_time(old,card.start));changed.end=output_time(plan,source_time(old,card.end))
        if changed.end-changed.start<.15:
            changed.start=max(0,min(changed.start,plan.duration-.2));changed.end=min(plan.duration,changed.start+.2)
            changed.review_reason='Ручная правка попала в изменённую паузу. Проверьте время.'
        # Line is an ASR index, not a stable reference across realignment.
        changed.line=-1
        if ident in fresh:plan.cards[plan.cards.index(fresh[ident])]=changed
        else:
            if ':legacy:' in ident:
                equivalent=next((c for c in plan.cards if c.title==changed.title and (c.forecast_id==changed.forecast_id if changed.forecast_id else c.text==changed.text)),None)
                if equivalent:plan.cards.remove(equivalent)
            plan.cards.append(changed)
    # Preserve manual insert choices and trims using their source-time anchors.
    if old.edit_baseline.get('inserts')!=[asdict(c) for c in old.inserts]:
        inserts=[]
        for item in old.inserts:
            c=copy.deepcopy(item);c.start=output_time(plan,source_time(old,item.start));c.end=output_time(plan,source_time(old,item.end))
            if c.end-c.start>=.15:inserts.append(c)
        plan.inserts=inserts
    old_tasks={x['id']:x for x in old.review_items}
    ids={x['id'] for x in plan.review_items}
    for item in plan.review_items:
        prior=old_tasks.get(item['id'])
        if prior and prior['status']!='pending':item['status']=prior['status']
        if item['id'] in deleted:item['status']='deleted'
    for ident,item in old_tasks.items():
        if ident not in ids:plan.review_items.append(copy.deepcopy(item))
    return plan


def update_task_times(plan):
    cards={c.review_id:c for c in plan.cards}
    for item in plan.review_items:
        card=cards.get(item['id'])
        if card:item['start'],item['end']=card.start,card.end
        elif item['status']!='deleted':item['status']='deleted'


def resolve(plan,ident,status,*,text=None,start=None,end=None,owner=None):
    if status not in ('confirmed','deleted','pending'):raise ValueError('Неизвестное решение проверки.')
    result=copy.deepcopy(plan)
    task=next(x for x in result.review_items if x['id']==ident)
    card=next((c for c in result.cards if c.review_id==ident),None)
    if status=='deleted':
        if card:task['deleted_card']=asdict(card);result.cards.remove(card)
    else:
        if card is None and task.get('deleted_card'):
            card=Card(**task['deleted_card']);result.cards.append(card)
        if card is None:raise ValueError('Плашка удалена на дорожке; добавьте её заново при необходимости.')
        if text is not None:card.text=text
        if start is not None:card.start=frame(start)
        if end is not None:card.end=frame(end)
        if card.title=='ПРОГНОЗ' and owner=='':raise ValueError('Выберите матч для прогноза.')
        if owner is not None:card.forecast_id=owner
        # Explicit manual timing overrides the automatic Telegram-to-line lock.
        card.line=-1
        if owner and text is not None:
            for other in result.cards:
                if other.forecast_id==owner:other.text=text
    task['status']=status;update_task_times(result)
    from .editing import validate_plan
    validate_plan(result)
    return result


def framing_draft(project,block,lines,duration):
    from .framing import framing_cards
    from .alignment import SpeechIssue
    try:cards,warnings=framing_cards(project,block,lines,duration)
    except SpeechIssue as error:
        cards,warnings=fallback_cards(project,block,lines,duration,str(error))
    # The ASR path may succeed while omitting a scripted CTA or recap. Keep a
    # provisional card for each expected event rather than silently dropping it.
    if block.kind=='intro':
        owners=[b for b in project.blocks if b.kind=='analysis']
        for k,b in enumerate(owners):
            if any(c.title=='РАЗБОР МАТЧА' and c.text==b.title for c in cards):continue
            a=min(max(0,duration-.2),duration*k/max(1,len(owners)))
            cards.append(Card(a,min(duration,a+3),'РАЗБОР МАТЧА',b.title,review_reason='Пара не найдена во вступлении. Проверьте предварительную плашку или удалите её.'))
    if block.language=='uz' and block.sport!='combat':
        from .framing import forecast_text
        from .uzbek import norm
        if block.kind=='outro':
            owners=[b for b in project.blocks if b.kind=='analysis']
            for k,b in enumerate(owners):
                if any(c.forecast_id==b.uid for c in cards):continue
                a=min(max(0,duration-.2),duration*k/max(1,len(owners)))
                cards.append(Card(a,min(duration,a+3),'ПРОГНОЗ',forecast_text(b) or b.title+' — уточните прогноз',forecast_id=b.uid,review_reason='Повтор ставки не найден уверенно. Предварительное время.'))
        if 'telegram' in norm(block.script) and not any(c.title=='ТЕЛЕГРАМ' for c in cards):
            a=max(0,duration-5)
            cards.append(Card(a,duration,'ТЕЛЕГРАМ','Telegram',asset=project.assets.get('telegram',''),review_reason='Призыв Telegram есть в сценарии, но не найден в речи. Проверьте или удалите плашку.'))
    return cards,warnings


def shifted_metadata(plan,offset,line_offset=0):
    tasks=copy.deepcopy(plan.review_items);base=copy.deepcopy(plan.edit_baseline)
    for item in tasks:
        item['start']=frame(item['start']+offset);item['end']=frame(item['end']+offset)
        if item.get('deleted_card'):
            item['deleted_card']['start']=frame(item['deleted_card']['start']+offset)
            item['deleted_card']['end']=frame(item['deleted_card']['end']+offset)
    for kind in ('cards','inserts'):
        for item in base.get(kind,[]):
            item['start']=frame(item['start']+offset);item['end']=frame(item['end']+offset)
            if kind=='cards' and item.get('line',-1)>=0:item['line']+=line_offset
    return tasks,base


def section_metadata(plan,part,section):
    offset=section['start'];uid=section['block_id']
    tasks,base=shifted_metadata(plan,-offset,-section['line_start'])
    part.review_items=[x for x in tasks if x['block_id']==uid]
    # Includes deleted cards in the baseline, so deletions survive realignment.
    part.edit_baseline={name:[x for x in values if -.035<=x['start'] and x['end']<=part.duration+.035] for name,values in base.items()}


def semantic_conflict(script,heard,language='ru'):
    if not heard:return ''
    if language=='uz':
        from .uz_forecasts import features
        a,b=features(script),features(heard)
        keys=('chance','value','direction')
    else:
        from .ru_speech import tokens
        def features(text):
            t=' '.join(tokens(text))
            direction='under' if re.search(r'тотал.{0,30}меньше',t) else 'over' if re.search(r'тотал.{0,30}больше',t) else None
            value=None
            if 'тотал' in t:
                tail=t[t.index('тотал'):]
                for number,word in enumerate(['ноль','один','два','три','четыре','пять','шесть','семь','восемь','девять']):
                    if re.search(r'\b'+word+r'\b',tail):value=number+(.5 if 'полови' in tail else 0);break
            chance=next((v for v,pattern in [('1x',r'\b1\s*[xх]\b'),('x2',r'\b[xх]\s*2\b')] if re.search(pattern,text.lower())),None)
            return dict(direction=direction,value=value,chance=chance)
        a,b=features(script),features(heard);keys=('direction','value','chance')
    if any(a[k] is not None and b[k] is not None and a[k]!=b[k] for k in keys):
        return 'В распознавании и сценарии различаются условия ставки. Прослушайте и явно выберите правильный текст.'
    return ''


def retain_legacy_edits(project):
    """Treat a valid pre-review saved timeline as authored; never silently reset it."""
    from .editing import project_edit_key
    from .episode import assembly_project
    runtime=assembly_project(project) if project.whole_episode else project
    for i,b in enumerate(runtime.blocks):
        old=b.edit_plan
        if old and not old.get('input_key') and b.edit_key==project_edit_key(runtime,i):
            old['input_key']=input_key(project,b)
            old['edit_baseline']={'cards':[],'inserts':[]}
            for j,c in enumerate(old.get('cards',[])):
                c.setdefault('review_id',f'{b.uid}:legacy:{j}')


def script_context(block,card,line):
    if block.language!='uz':return line.text if line else card.text
    from .alignment import split_script
    rows=split_script(block.script)
    return max(rows,key=lambda text:SequenceMatcher(None,text.casefold(),card.text.casefold()).ratio()) if rows else card.text
