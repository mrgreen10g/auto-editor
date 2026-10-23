"""Russian speech adapter for the shared combat footage/montage pipeline."""
import re
from functools import lru_cache
from difflib import SequenceMatcher
from .model import Block,EventRequest
from .alignment import split_script
from .graphics import block_teams
from .timeline import Card

def plain(text):return text.lower().replace('ё','е').strip(' #*: ')

def forms(word):
    word=plain(word);out={word}
    if not re.search('[а-я]',word):return out
    if word=='петр':return {'петр','петра','петру','петром','петре'}
    if word.endswith('а'):out.update(word[:-1]+s for s in ('ы','и','е','у','ой','ою'))
    elif word.endswith('я'):out.update(word[:-1]+s for s in ('и','е','ю','ей'))
    elif word.endswith('ий'):out.update(word[:-2]+s for s in ('ия','ию','ием','ии'))
    elif word.endswith('й'):out.update(word[:-1]+s for s in ('я','ю','ем','е'))
    elif word[-1:] not in 'аеёиоуыэюяь':out.update(word+s for s in ('а','у','ом','е'))
    return out

@lru_cache(maxsize=4096)
def name_pattern(name):
    return r'(?<!\w)'+r'\s+'.join('(?:'+'|'.join(re.escape(v) for v in sorted(forms(w),key=len,reverse=True))+')' for w in name.split())+r'(?!\w)'

@lru_cache(maxsize=2048)
def full_names(text):
    from .fighter_russian import NAMES,VARIANTS
    hits=[]
    for en,ru in NAMES.items():
        positions=[m.start() for spelling in (en,ru,*VARIANTS.get(en,())) for m in re.finditer(name_pattern(spelling),plain(text))]
        if positions:hits.append((min(positions),ru))
    return [name for _,name in sorted(hits)]

def named(names,text):
    from .fighters import name_spellings
    found=[];t=plain(text)
    for name in names:
        if not name:continue
        spellings=name_spellings(name)
        if any(re.search(name_pattern(n),t) for n in spellings):found.append(name);continue
        # Local first names/surnames only; never globally merge namesakes.
        for part in (name.split()[0],name.split()[-1]):
            if sum(bool(set(forms(part)) & set(forms(n.split()[0])|forms(n.split()[-1]))) for n in names if n)!=1:continue
            if re.search(name_pattern(part),t):found.append(name);break
    return found

CUE=r'^(?:(?:и\s+)?(?:первый|второй|третий|четвертый|четвёртый|пятый|последний|следующий|очередной|\d+)\s+бой|начинаем\s+с|начн[её]м\s+с|теперь|далее(?:\s+бой)?)\s*[—–:\-]?\s*'
ENDING=r'^(?:итак\b|итоги\b|подвед[её]м\s+итог|повторю\s+(?:(?:\w+|\d+)\s+)?(?:основны\w*\s+)?прогноз|подытож)'

def pair_heading(line):
    from .fighters import canonical_name
    value=line.strip(' #*: ');cue=re.match(CUE,value,re.I)
    if cue:
        value=value[cue.end():].rstrip('.!');names=full_names(value)
        if len(names)==2:return ' — '.join(names)
    elif value.endswith(('.', '!', '?')):return None
    if len(value)>130:return None
    parts=re.split(r'\s+[—–-]\s+|\s+против\s+|\s+и\s+',value,flags=re.I)
    if len(parts)!=2 or any(not re.fullmatch(r'[А-ЯЁA-Z][\w’\' .-]+',p) or not 2<=len(p.split())<=4 for p in parts):return None
    names=[full_names(p) for p in parts]
    return ' — '.join(n[0] if len(n)==1 else canonical_name(p,language='ru') for p,n in zip(parts,names))

def parse_script(text,shorts=False):
    text=re.sub(r'https?://\S+|www\.\S+|\[(?:МОНТАЖ[ЕЁ]РУ|РЕДАКТОРУ|НЕ ЧИТАТЬ)[^\]]*\]','',text,flags=re.I)
    rows=[r.strip(' #*') for r in text.splitlines() if r.strip()]
    intro=Block(title='Начало',uid='intro',kind='intro',language='ru',sport='combat')
    outro=Block(title='Итоги',uid='outro',kind='outro',language='ru',sport='combat')
    ending=next((i for i,r in enumerate(rows) if re.match(ENDING,plain(r))),len(rows))
    outro.script='\n'.join(rows[ending:]);rows=rows[:ending]
    headers=[(i,pair_heading(r)) for i,r in enumerate(rows) if pair_heading(r)]
    if not headers:
        names=full_names(text)
        if not shorts or len(names)!=2:raise ValueError('Укажите пары заголовками, словами «Начинаем с … / Теперь …» или метками Разбор1, Разбор2 и далее.')
        headers=[(-1,' — '.join(names))]
    first,title=headers[0];stop=headers[1][0] if len(headers)>1 else len(rows)
    transition=next((i for i in range(first+1,stop) if re.search(r'переходим\s+к\s+разбор|начинаем\s+разбор',plain(rows[i]))),None)
    if first==0 and transition is not None and any(re.search('всем привет|здравств',plain(r)) for r in rows[1:transition+1]):
        intro.script='\n'.join(rows[1:transition+1]);headers[0]=(transition,title)
    else:intro.script='\n'.join(rows[:max(0,first)])
    blocks=[]
    for j,(i,title) in enumerate(headers):
        end=headers[j+1][0] if j+1<len(headers) else len(rows)
        body=rows[i+1:end]
        if i>=0 and re.match(CUE,rows[i],re.I):body=[rows[i]]+body
        script='\n'.join(body)
        if not script:raise ValueError('Нет текста разбора: '+title)
        blocks.append(Block(title=title,script=script,language='ru',sport='combat',forecast=primary_forecast(script)))
    intro.featured_pairs=[b.title for b in blocks]
    return intro,blocks,outro

def normalize_bet(text):
    from .card_text import numeric
    t=numeric(plain(text))
    values={'одиннадцать':11,'двенадцать':12,'тринадцать':13,'четырнадцать':14,'пятнадцать':15,'шестнадцать':16,'семнадцать':17,'восемнадцать':18,'девятнадцать':19,'двадцать':20,'тридцать':30,'сорок':40,'пятьдесят':50,'шестьдесят':60,'семьдесят':70,'восемьдесят':80,'девяносто':90,'сто':100}
    for word,value in values.items():t=re.sub(r'\b'+word+r'\b',str(value),t)
    t=re.sub(r'\b([2-9]0)\s+([1-9])\b',lambda m:str(int(m[1])+int(m[2])),t)
    t=re.sub(r'\bт([бм])\s*\(\s*(\d+(?:[.,]\d+)?)\s*\)',lambda m:'тотал '+('больше' if m[1]=='б' else 'меньше')+' '+m[2],t)
    return re.sub(r'(\d)\s*[,.]\s*(\d)',r'\1,\2',t)

def pick(text):
    t=normalize_bet(text)
    distance=re.search(r'бой\s+(не\s+)?пройдет\s+полную\s+дистанцию',t)
    if distance:return 'Бой '+('не ' if distance[1] else '')+'пройдёт полную дистанцию'
    total=re.search(r'тотал\s+(больше|меньше)\s+(\d+(?:[.,]\d+)?)',t)
    if total:return 'Тотал '+total[1]+' '+total[2]+' раунда'
    winner=re.search(r'победа\s+(.+)',text,re.I)
    if winner:return 'Победа '+winner[1].strip(' .!')
    return ''

def classify(text):
    t=plain(text)
    if re.search(r'телеграм|telegram|подписывай|ставьте лайк',t):return None,''
    alternative=bool(re.search(r'рискован|альтернатив|по самому бою жду|по сценарию больше',t))
    announcement=bool(re.search(r'(?:мой|основной)\s+(?:выбор|прогноз)|основная\s+ставка|(?:беру|ставлю)\s+(?:на|тотал)',t))
    body=pick(text)
    if announcement and body and not alternative:
        condition=re.match(r'^(если\b.+?)[,;]',text.strip(),re.I)
        if condition:body=condition[1]+': '+body
        return 'ПРОГНОЗ',body
    if alternative or re.search(r'бой должен пройти|ставка (?:пройдет|проходит|выигрывает)|то есть бой',t):return 'УСЛОВИЯ ПРОГНОЗА',text.strip(' .!')
    facts=[]
    for clause in re.split(r'(?<=[.!?])\s+|,\s+(?=(?:а |и )?(?:защит|у него|он ))',text):
        c=normalize_bet(clause)
        if (re.search(r'\d|ни одной|ни разу|дважды',c) and re.search(r'тейкдаун|значим\w* удар|процент|сабмиш|побед|поражен|нокаут|решени|раунд|перевод',c) and len(clause)<=165):facts.append(clause.strip(' .!'))
    if facts:return 'СТАТИСТИКА',' · '.join(facts)
    if len(text)<130 and re.search(r'контрол\w* дистанц|защит\w* от борьб|меняет уровни|борцовск\w* оруж|работ\w* ногами',t):return 'ИНФОРМАЦИЯ',text.strip(' .!')
    return None,''

def primary_forecast(script):
    picks=[body for row in split_script(script) for title,body in [classify(row)] if title=='ПРОГНОЗ']
    return picks[0] if picks else ''

def events(block,matches):
    from .fighters import same_fighter
    sources=[s for s in matches if s.id in block.match_ids and s.sport=='combat'];owner=None;result=[];usage={}
    for row in ([l['text'] for l in block.asr_lines] if block.asr_lines else split_script(block.script)):
        hits=named(block_teams(block.title),row)
        if hits:owner=hits[0] if len(hits)==1 else None
        title,_=classify(row);t=plain(row)
        if title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА') or re.search(r'телеграм|telegram|подпис|лайк|ставк|коэффициент',t):continue
        if not owner or not re.search(r'удар|борьб|борцов|защит|стойк|дистанц|давлен|тейкдаун|проход|контрол|ногами|руками|сабмиш|нокаут|размен',t):continue
        available=[s for s in sources if same_fighter(s.fighter,owner)]
        source=min(available,key=lambda s:usage.get(s.id,0)) if available else None
        if source:usage[source.id]=usage.get(source.id,0)+1
        result.append(EventRequest(source.id if source else '',row,'play',requested_teams=[owner]))
    return result

def coverage(expected,heard):
    from .ru_speech import tokens
    return SequenceMatcher(None,tokens(normalize_bet(expected)),tokens(normalize_bet(heard)),autojunk=False).ratio()

def confidence(card,line,block,project):
    if card.review_reason:return card.review_reason
    heard=line.recognized if line else ''
    if not heard:return 'Не найдена речь для плашки.'
    if line.review_reason:return line.review_reason
    if card.title=='РАЗБОР МАТЧА':return '' if len(named(block_teams(card.text),heard))==2 else 'Проверьте имена бойцов и время.'
    if card.title=='ТЕЛЕГРАМ':return '' if re.search('телеграм|telegram',plain(heard)) else 'Проверьте время Telegram.'
    if card.title=='ПОДПИСКА':return '' if re.search('подпис|лайк',plain(heard)) else 'Проверьте время подписки.'
    from .review import semantic_conflict
    if re.search(r'\b\d{2}:\d{2}\b',card.text):
        heard=re.sub(r'\b(\d{2})\s*[,–—:-]\s*(\d{2})\b',r'\1:\2',heard)
    expected=normalize_bet(card.text);actual=normalize_bet(heard)
    conflict=semantic_conflict(expected,actual)
    if conflict:return conflict
    if 'если' in expected and 'если' not in actual:return 'Условие прогноза не подтверждено речью.'
    numbers=lambda t:re.findall(r'\d+(?:[,.]\d+)?',t)
    if not all(n in numbers(actual) for n in numbers(expected)):return 'Числа плашки не подтверждены речью.'
    if bool(re.search(r'\bне\b|ни разу|ни одной',plain(line.text)))!=bool(re.search(r'\bне\b|ни разу|ни одной',plain(heard))):return 'Проверьте отрицание в речи.'
    owner=next((b for b in project.blocks if b.uid==card.forecast_id),block)
    a=named(block_teams(owner.title),card.text);b=named(block_teams(owner.title),heard)
    if a and not set(a)<=set(b):return 'Боец в плашке не подтвержден речью.'
    if card.title=='ПРОГНОЗ':
        if 'полную дистанцию' in expected:
            if pick(card.text)!=pick(heard):return 'Проверьте полную дистанцию и отрицание.'
            return ''
        if 'тотал' in expected:
            if not pick(heard) or pick(card.text)!=pick(heard):return 'Проверьте тотал, число и направление.'
            return ''
    return '' if coverage(line.text,heard)>=.65 else 'Проверьте факт и время плашки по речи.'

def framing_cards(project,block,lines,duration):
    cards=[];seen=set();analyses=[b for b in project.blocks if b.kind=='analysis']
    for i,line in enumerate(lines):
        low=plain(line.text)
        if re.search('телеграм|telegram',low):
            asset=project.assets.get('telegram','')
            if asset:cards.append(Card(line.start,line.end,'ТЕЛЕГРАМ','Telegram',i,asset))
            continue
        if re.search('подписывай|ставьте лайк',low):
            asset=project.assets.get('subscribe','')
            if asset:
                from .media import probe
                end=line.start+probe(asset)['duration']
                if end<=duration:cards.append(Card(line.start,end,'ПОДПИСКА','Подписка',i,asset))
            continue
        if block.kind=='intro':
            for b in analyses:
                if b.uid not in seen and len(named(block_teams(b.title),line.text))==2:
                    cards.append(Card(line.start,line.end,'РАЗБОР МАТЧА',b.title,i));seen.add(b.uid)
        elif block.kind=='outro':
            body=pick(line.text)
            if not body:continue
            owners=[b for b in analyses if len(named(block_teams(b.title),line.text))==2]
            if not owners:owners=[b for b in analyses if named(block_teams(b.title),line.text)]
            owner=owners[0] if len(owners)==1 else analyses[0] if len(analyses)==1 else None
            cards.append(Card(line.start,line.end,'ПРОГНОЗ',body,i,forecast_id=owner.uid if owner else '',fixture=owner.title if owner else '',review_reason='' if owner else 'Уточните, к какому бою относится прогноз.'))
    return cards,[]
