"""Selective combat facts and local evidence, independent of prose alignment quality."""
import re
from difflib import SequenceMatcher
from .uzbek import norm, spoken_uz


def tokens(text):
    return re.findall(r"[a-z0-9]+", norm(spoken_uz(text)).replace("'", ''))


def similarity(a,b):
    return SequenceMatcher(None,a,b).ratio()


def coverage(expected,heard):
    a=tokens(expected);b=tokens(heard);used=set();hits=0
    for word in a:
        candidates=[(similarity(word,w),i) for i,w in enumerate(b) if i not in used]
        score,i=max(candidates,default=(0,-1))
        if score>=.76 and (len(word)>=4 or word==b[i]):hits+=1;used.add(i)
    return hits/max(1,len(a))


def numbers(text):
    """Conservative numeric evidence; do not 'correct' uncertain ASR values."""
    t=norm(text).replace("'",'')
    words=re.findall(r'[a-z]+|\d+',t)
    values=[];current=0;active=False
    units={'nol':0,'bir':1,'bitta':1,'biti':1,'ikki':2,'ikkita':2,'uch':3,'uchta':3,'tort':4,'torta':4,'tortta':4,'besh':5,'beshta':5,'olti':6,'oltita':6,'oltida':6,'oltisida':6,'yetti':7,'yetta':7,'yettita':7,'sakkiz':8,'toqqiz':9}
    tens={'on':10,'onta':10,'yigirma':20,'ottiz':30,'otiz':30,'qirq':40,'ellik':50,'oltmish':60,'yetmish':70,'sakson':80,'toqson':90}
    def flush():
        nonlocal current,active
        if active:values.append(current)
        current=0;active=False
    for w in words:
        if w.isdigit():flush();values.append(int(w))
        elif w in tens:
            if active and current%100:flush()
            current+=tens[w];active=True
        elif w in units or re.sub(r'(?:tasidan|tasini|tasi|ta)$','',w) in units:
            w=w if w in units else re.sub(r'(?:tasidan|tasini|tasi|ta)$','',w)
            if active and current%10:flush()
            current+=units[w];active=True
        elif w=='yuz':current=max(1,current)*100;active=True
        else:flush()
    flush();return values


def classify(text):
    t=norm(text);n=numbers(text)
    if re.search(r'\bprognoz\s*:|\btanlo(?:v|y)\w*|(?:[qk]ut\w*|kutil\w*)',t) and re.search(r"g'alab|nokaut|raund|total|ochko",t):
        return 'ПРОГНОЗ',re.split(r'tanlovim\s*[—–:\-]?\s*|PROGNOZ\s*:\s*',text,flags=re.I)[-1].strip(' .')
    from .uz_facts import combat_facts,argument
    facts=combat_facts(text)
    if facts:return 'СТАТИСТИКА',' · '.join(facts)
    claim=argument(text)
    if claim:return 'ИНФОРМАЦИЯ',claim
    return None,''


def polished_argument(body,heard,script):
    from .combat import clean_script
    from .alignment import split_script
    from .uz_facts import argument
    # Written phrasing may improve readability, but cannot introduce numbers
    # or reverse a condition/negation from the speaker.
    candidates=[]
    for row in split_script(clean_script(script)):
        claim=argument(row)
        if not claim or numbers(claim):continue
        if bool(re.search(r'agar|mumkin',norm(claim)))!=bool(re.search(r'agar|mumkin',norm(heard))):continue
        if bool(re.search(r'emas|maydi|yo.q',norm(claim)))!=bool(re.search(r'emas|maydi|yo.q',norm(heard))):continue
        score=coverage(claim,heard)
        if score>=.70:candidates.append((score,claim))
    return max(candidates,default=(0,body))[1]


def confidence(card,line,block,project):
    """Only the displayed fact needs proof; unrelated paraphrases don't veto it."""
    from .combat import name_position,pair_in
    from .graphics import block_teams
    heard=line.recognized if line else ''
    if not heard:return 'Не найдена речь для этой плашки. Проверьте время.'
    if line and 'Не подтверждены границы' in line.review_reason:return line.review_reason
    if card.title=='ТЕЛЕГРАМ':return '' if 'telegram' in norm(heard) else 'Проверьте время призыва Telegram.'
    if card.title=='ПОДПИСКА':return '' if re.search(r'obuna|layk|like',norm(heard)) else 'Проверьте время подписки.'
    if card.title=='РАЗБОР МАТЧА':return '' if pair_in(card.text,heard) else 'Имена пары распознаны неуверенно. Проверьте время.'
    if card.title=='ПРОГНОЗ':
        owner=next((b for b in project.blocks if b.uid==card.forecast_id),block)
        names=block_teams(owner.title)
        picked=[n for n in names if n and name_position(n,card.text) is not None]
        t=norm(heard)
        # Combat winner bets: both a fighter and a winning claim must be heard.
        if "g'alab" in norm(card.text):
            if len(picked)==1 and name_position(picked[0],heard) is not None and re.search(r"[gq]'?alab|yut(?:ish|adi|a|u)",t) and not re.search(r'yutmay|yutolmay|emas|mag.lub',t):
                claims=[]
                for hit in re.finditer(r"[gq]'?alab|yut(?:ish|adi|a|u)",t):
                    nearby=' '.join(t[:hit.start()].split()[-3:])
                    owners=[n for n in names if n and name_position(n,nearby) is not None]
                    if len(owners)==1:claims.append(owners[0])
                if claims and set(claims)==set(picked):return ''
            return 'Проверьте бойца и исход ставки по речи.'
        if coverage(card.text,heard)>=.8 and numbers(card.text)==numbers(heard):return ''
        return 'Условия ставки распознаны неуверенно. Проверьте их по речи.'
    if card.title=='СТАТИСТИКА':
        names=block_teams(block.title)
        expected_owners=[n for n in names if n and line and name_position(n,line.text) is not None]
        heard_owners=[n for n in names if n and name_position(n,heard) is not None]
        if expected_owners and heard_owners and set(expected_owners)!=set(heard_owners):
            return 'В речи статистика отнесена к другому бойцу. Проверьте принадлежность.'
        def record_facts(text):
            result={};low=norm(text)
            for key,pattern in [('win',r"[gq]'?alab"),('loss',r"ma[gq]?'?lub"),('draw',r'durr?ang')]:
                for hit in re.finditer(pattern,low):
                    found=numbers(' '.join(low[:hit.start()].split()[-4:]))
                    if found:result[key]=found[-1]
            return result
        if line and 'REKORD:' in card.text:
            a,b=record_facts(line.text),record_facts(heard)
            if any(a[k]!=b[k] for k in a.keys() & b.keys()):
                return 'В речи различаются победы, поражения или ничьи. Проверьте рекорд.'
        # Reordering a bundle (record + age + finishes) is a layout choice.
        # Compare independently extracted facts, not one numeric substring.
        from .uz_facts import combat_facts
        grounded=combat_facts(heard)
        if line and line.text.strip()==heard.strip() and card.text.split('\n')[-1]==' · '.join(grounded):return ''
        expected=numbers(card.text);actual=numbers(heard)
        if expected and not any(actual[i:i+len(expected)]==expected for i in range(len(actual))):
            return 'Числа статистики не подтверждены речью. Проверьте значения и время.'
        if expected and line and coverage(line.text,heard)>=.65:return ''
        return 'Проверьте принадлежность статистики и время плашки.'
    if line and coverage(line.text,heard)>=.78:return ''
    return 'Факт или его время распознаны неуверенно. Проверьте эту плашку.'


def migrate_plan(value,project,block=None):
    """Remove only proven old auto-subtitles, including blanket confirmations.

    Authored text, deleted real cards, inserts and source timing remain intact.
    The automatic baseline distinguishes a blanket acceptance from an edit.
    """
    if not value:return False
    from .timeline import Card,Line
    baseline=value.get('edit_baseline',{}).get('cards',[])
    base={c.get('review_id'):c for c in baseline if c.get('review_id')}
    live={c.get('review_id'):c for c in value.get('cards',[])}
    tasks={t['id']:t for t in value.get('review_items',[])}
    blocks={b.uid:b for b in [project.intro,*project.blocks,project.outro]}
    removed=set();changed=False
    for ident,b in base.items():
        i=b.get('line',-1);lines=value.get('lines',[])
        if not 0<=i<len(lines):continue
        line=Line(**lines[i]);card=live.get(ident)
        authored=card is not None and any(card.get(k)!=b.get(k) for k in ('text','title','asset','forecast_id'))
        if b['title'] in ('ИНФОРМАЦИЯ','СТАТИСТИКА') and b['text']==line.text and line.review_reason and (classify(line.text)[0] is None or (classify(line.text)[0]=='ИНФОРМАЦИЯ' and not re.search(r'jarohat|diskvalifik',norm(line.text)))) and not authored:
            removed.add(ident);continue
        if card is None or authored:continue
        title,body=classify(line.text)
        if card['title'] in ('СТАТИСТИКА','ИНФОРМАЦИЯ') and title=='СТАТИСТИКА' and card['text']==line.text:
            card['title']=b['title']=title;card['text']=body;b['text']=body;changed=True
        task=tasks.get(ident)
        owner=blocks.get(task.get('block_id')) if task else block
        if owner is None:continue
        if task and task['status']=='pending':
            reason=confidence(Card(**card),line,owner,project)
            if not reason:
                value['review_items'].remove(task);card['review_reason']='';b['review_reason']='';changed=True
            else:
                changed=changed or task['reason']!=reason or card.get('review_reason')!=reason or b.get('review_reason')!=reason
                task['reason']=reason;card['review_reason']=reason;b['review_reason']=reason
    if removed:
        value['cards']=[c for c in value['cards'] if c.get('review_id') not in removed]
        value['review_items']=[t for t in value.get('review_items',[]) if t['id'] not in removed]
        value['edit_baseline']['cards']=[c for c in baseline if c.get('review_id') not in removed]
        value.setdefault('warnings',[]).append(f'Удалены ошибочные автоматические плашки обычной речи: {len(removed)}. Видеовставки и тайминги сохранены.')
    return changed or bool(removed)


def migrate_project(project):
    if project.profile!='uz_combat':return
    from .episode import episode_key
    try:valid=bool(project.episode_plan and project.episode_key==episode_key(project))
    except OSError:valid=False  # Opening a moved project must not require its media.
    changed=migrate_plan(project.episode_plan,project)
    for block in [project.intro,*project.blocks,project.outro]:changed=migrate_plan(block.edit_plan,project,block) or changed
    if changed and valid:project.episode_key=episode_key(project)
