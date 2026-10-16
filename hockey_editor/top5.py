"""Narrated rankings: identities, facts and owned archive footage, never bets."""
import re
from .model import Block,EventRequest
from .timeline import Card,Line

PROFILES=('ru_hockey_top5_shorts','ru_football_top5_shorts')
RANK_WORD=r'(?:пят(?:ое|ый|ая|ом)|четв[её]рт(?:ое|ый|ая|ом)|трет(?:ье|ий|ья|ьем)|втор(?:ое|ой|ая|ом)|перв(?:ое|ый|ая|ом)|[1-5](?:-[ейя])?)'
ANNOUNCE=re.compile(r'(?:^|(?<=[.!?])\s+|\n+)\s*(?:(?:и|но)\s+)?(?:вот\s+)?(?:на\s+)?(?P<rank>'+RANK_WORD+r')\b(?:\s+мест[ое])?\s*[—–,:-]?\s*',re.I)

def rank_number(word):
    value=word.lower().replace('ё','е')
    if value[:1].isdigit():return int(value[0])
    return next(n for root,n in [('пят',5),('четверт',4),('трет',3),('втор',2),('перв',1)] if value.startswith(root))

def club(name,sport):
    from .team_names import normalize,RU,FOOTBALL,football_positions
    value=normalize(name).strip(' .!?,:—–-')
    if sport=='football':
        found=[key for key in FOOTBALL if any(a==0 and z==len(value) for a,z in football_positions(key,value))]
    else:
        found=[]
        for key,patterns in RU.items():
            rest=list(value)
            for pattern in patterns:
                for match in re.finditer(r'(?<!\w)(?:'+pattern+r')(?!\w)',value):rest[match.start():match.end()]=' '*(match.end()-match.start())
            if not re.search(r'\w',''.join(rest)):found.append(key)
    return next(iter(set(found))) if len(set(found))==1 else None

def display(key,sport):
    if sport!='football':return key
    from .team_names import FOOTBALL
    return next((n for n in FOOTBALL[key] if re.search('[А-Яа-яЁё]',n)),key)

def members(title,sport):
    parts=re.split(r'\s+[—–-]\s+|\s+против\s+|\s+и\s+',title.strip(' .!'),flags=re.I)
    values=[club(p,sport) for p in parts]
    return values if len(values) in (1,2) and all(values) and len(set(values))==len(values) else []

def parse_script(text,sport='hockey'):
    text=re.sub(r'https?://\S+|\[[^\]]*\]','',text).strip()
    starts=[]
    for match in ANNOUNCE.finditer(text):
        tail=text[match.end():]
        # "И вот первое место.\nБарыс." is one announcement, not two blocks.
        tail=re.sub(r'^[.\s]+','',tail)
        candidate=re.split(r'[.!?\n]',tail,maxsplit=1)[0].strip()
        candidate=re.sub(r'^сам(?:а|о)?\s+','',candidate,flags=re.I)
        names=members(candidate,sport)
        if names:starts.append((match.start(),rank_number(match['rank']),' — '.join(display(n,sport) for n in names)))
    if len(starts)!=5 or sorted(n for _,n,_ in starts)!=[1,2,3,4,5]:
        raise ValueError('ТОП‑5: не удалось однозначно найти все пять мест с названиями команд или матчей. Используйте, например, «Пятое место — Спартак» или «Пятое место — СКА против Лады».')
    last=starts[-1][0]
    closing=re.search(r'(?:^|(?<=[.!?])\s+|\n+)\s*(?:вот\s+так\s+сейчас|а\s+(?:кто|кого)\b|но\s+здесь\s+(?:хочу\s+поспорить|точно\s+будет\s+спор)|но\s+напишите\b|кто\s+у\s+вас\b|напишите\s+в\s+комментариях)',text[last:],re.I)
    end=last+closing.start() if closing else len(text)
    blocks=[Block(title=title,script=text[a:(starts[i+1][0] if i+1<len(starts) else end)].strip(),sport=sport,top5_rank=rank) for i,(a,rank,title) in enumerate(starts)]
    return (Block(title='Начало ТОП‑5',uid='intro',kind='intro',script=text[:starts[0][0]].strip(),sport=sport),blocks,
            Block(title='Завершение ТОП‑5',uid='outro',kind='outro',script=text[end:].strip(),sport=sport))

def header_end(block,lines):
    """Include a separately spoken name after a standalone place announcement."""
    for i,line in enumerate(lines[:3]):
        if all(mentioned(n,line.text,block.sport) for n in members(block.title,block.sport)):
            # A title and its following fact can share an aligned sentence.
            return i,min(line.end,line.start+2.4)
    return 0,min(lines[0].end,lines[0].start+2.4) if lines else 0

def mentioned(name,text,sport):
    if sport=='football':
        from .team_names import football_positions
        return bool(football_positions(name,text))
    from .event_rules import team_position
    return team_position(name,text) is not None

def promo_indices(lines):
    from .shorts import promo_line_ranges
    return {i for a,z in promo_line_ranges(lines) for i in range(a,z+1)}

def facts(block,lines,duration):
    from .card_text import numeric
    if not block.top5_rank:return []
    head,until=header_end(block,lines)
    cards=[Card(lines[0].start,until,f'{block.top5_rank} МЕСТО',block.title,0)] if lines and until>lines[0].start else []
    promo=promo_indices(lines);i=head+1
    while i<len(lines):
        line=lines[i];text=line.text.strip();low=text.lower().replace('ё','е')
        if i in promo or re.search(r'комментари|кто\s+у\s+вас|кого\s+бы|подпис|ставьте\s+лайк',low):i+=1;continue
        # Consecutive spoken scores are a progression, not a pile of subtitles.
        scores=[];last=i
        for j in range(i,len(lines)):
            value=lines[j].text.strip(' .')
            if j in promo or not re.fullmatch(r'\d{1,2}\s*:\s*\d{1,2}',value):break
            scores.append(value);last=j
        if len(scores)>1:
            reason='; '.join(dict.fromkeys(l.review_reason for l in lines[i:last+1] if l.review_reason))
            cards.append(Card(line.start,lines[last].end,'ХОД МАТЧА',' → '.join(scores),i,fixture=block.title,review_reason=reason));i=last+1;continue
        n=numeric(low)
        for word,value in [('одиннадцать','11'),('двенадцать','12'),('тринадцать','13'),('четырнадцать','14'),('пятнадцать','15'),('шестнадцать','16')]:n=re.sub(r'\b'+word+r'\b',value,n)
        scored=bool(re.search(r'\b\d{1,2}\s*:\s*\d{1,2}\b',text))
        statistic=bool(re.search(r'\d',n) and re.search(r'побед|поражен|ничь|матч|тур|гол|шайб|забил|забит|заброс|пропущ|очк|передач|минут|разниц',low))
        argument=bool(re.search(r'без\s+поражений|не\s+проигрывал|крупнейш\w*\s+побед|хет[- ]?трик|камбэк|перевернул\w*\s+встреч|главн\w*\s+(?:сюрприз|разочарован)',low))
        if scored or statistic or argument:
            # Keep the clause intact; never convert any score into a shots stat.
            body=re.sub(r'^(?:причем|и\s+теперь|а\s+потом|да,|то\s+есть)\s+','',text,flags=re.I)
            title='ХОД МАТЧА' if scored else 'СТАТИСТИКА' if statistic else 'ФАКТ'
            if 0<len(body)<=150 and line.end-line.start>=.8:
                body=block.card_overrides.get(str(i),body)
                if body.strip():cards.append(Card(line.start,line.end,title,body,i,fixture=block.title))
        i+=1
    return cards

def events(block,matches):
    from .alignment import split_script
    sources=[m for m in matches if m.id in block.match_ids and m.sport==block.sport]
    owners=set(members(block.title,block.sport))
    teams={m.id:{club(m.home,block.sport),club(m.away,block.sport)} for m in sources}
    sources=[m for m in sources if owners and owners.issubset(teams[m.id])]
    if not sources:return []
    phrases=split_script(block.script);lines=[Line(t,i,i+1) for i,t in enumerate(phrases)]
    promo=promo_indices(lines);head,_=header_end(block,lines);counts={m.id:0 for m in sources};result=[]
    names={n for m in sources for n in teams[m.id] if n}
    for i,text in enumerate(phrases):
        if i<=head or i in promo or re.search(r'комментари|подпис|лайк',text,re.I):continue
        if len(text.split())<3 and not re.search(r'\d\s*:\s*\d',text):continue
        named={n for n in names if mentioned(n,text,block.sport)}
        explicit=[m for m in sources if named and named.issubset(teams[m.id])]
        selected=min(explicit or sources,key=lambda m:counts[m.id]);counts[selected.id]+=1
        # Footage illustrates the fact. A score is not an instruction to find a
        # particular goal; a ranking number is never a scoreboard request.
        result.append(EventRequest(selected.id,text,kind='play',requested_teams=list(owners),strict_source=True))
    return result
