"""Uzbek fight Shorts: spoken bouts, conditional picks and portrait composition."""
import re
from .model import Block
from .timeline import Card
from .uz_structure import rows, key, INTRO, OUTRO
from .uzbek import norm

ORDINAL = r"(?:birinchi|ikkinchi|uchinchi|to'rtinchi|beshinchi|oltinchi|yettinchi|sakkizinchi|to'qqizinchi|o'ninchi|keyingi|oxirgi)"
ANNOUNCEMENT = rf"^(?:va\s+)?{ORDINAL}\s+(?:jang|bahs|uchrashuv)\s*[—–:,-]?\s*(.+)"


def classify(text):
    from .combat_cards import classify as base
    title,body=base(text)
    # A conditional pick must never become an unconditional recommendation.
    if title=='ПРОГНОЗ' and re.search(r'\bagar\b|tasdiqlansa|belgilangan',norm(text)):
        body=text.strip(' *.')
    return title,body


def pair_title(value):
    from .fighters import canonical_name
    parts=re.split(r'\s+va\s+|\s+[—–-]\s+',value.rstrip('.!'),maxsplit=1,flags=re.I)
    if len(parts)!=2:return None
    names=[]
    for part in parts:
        # A nationality describes a person; it is not part of their name.
        part=re.sub(r"^(?:o['’‘ʻʼ`]zbekistonlik|rossiyalik|angliyalik|gruziyalik|braziliyalik)\s+",'',part.strip(),flags=re.I)
        if not re.fullmatch(r"[\w'’‘ʻʼ`. -]+",part) or not 1<=len(part.split())<=4:return None
        names.append(canonical_name(part,language='uz'))
    from .fighters import same_fighter
    return None if same_fighter(*names) else ' — '.join(names)


def parse_script(text):
    values=[r.replace('**','') for r in rows(text)]
    if not any(re.match(ANNOUNCEMENT,r.translate(str.maketrans({c:"'" for c in '’‘ʻʼ`'})),re.I) for r in values):
        from .combat import parse_script as long_parse
        intro,blocks,outro=long_parse(text)
    else:
        intro=Block(title='Boshlanish',uid='intro',kind='intro',language='uz',sport='combat')
        outro=Block(title='Yakun',uid='outro',kind='outro',language='uz',sport='combat')
        blocks=[];current=intro
        for row in values:
            k=key(row)
            if k in INTRO:continue
            if k in OUTRO or (blocks and re.match(r'^demak\b',k)):
                current=outro
                if k in OUTRO:continue
            match=re.match(ANNOUNCEMENT,row.translate(str.maketrans({c:"'" for c in '’‘ʻʼ`'})),re.I)
            if match and current is not outro:
                title=pair_title(match[1])
                if not title:raise ValueError('Укажите двух бойцов после представления боя: '+row)
                current=Block(title=title,language='uz',sport='combat');blocks.append(current)
            if re.search('[А-Яа-яЁё]',row):continue
            current.script+=('\n' if current.script else '')+row
        if not blocks:raise ValueError('Не найдены представления боёв. Например: Birinchi jang — Petr Yan va Merab Dvalishvili.')
    for b in [intro,*blocks,outro]:
        b.sport='combat';b.language='uz'
        if b.kind=='analysis':
            picks=[body for row in b.script.splitlines() for title,body in [classify(row)] if title=='ПРОГНОЗ']
            if picks:b.forecast=picks[-1]
    intro.featured_pairs=[b.title for b in blocks]
    return intro,blocks,outro


def spoken_ranges(project,segments,duration):
    """Ordinal introductions exclude the hook's fixture list and middle promo."""
    from .combat import pair_in,active_blocks
    words=[w for s in segments for w in s.get('words',[])]
    starts=[];floor=0.
    for block in project.blocks:
        candidates=[]
        for i,w in enumerate(words):
            if w['start']<floor:continue
            window=' '.join(x['word'] for x in words[i:i+16])
            if re.match(ANNOUNCEMENT,norm(window),re.I) and pair_in(block.title,window):candidates.append(w['start'])
        if not candidates:return None
        starts.append(candidates[0]);floor=starts[-1]+.5
    bounds=([0.] if project.intro.script.strip() else [])+starts
    if project.outro.script.strip():
        ending=next((w['start'] for w in words if w['start']>starts[-1]+.5 and re.fullmatch(r'demak[:,.!]?',norm(w['word']).strip())),None)
        if ending is None:return None
        bounds.append(ending)
    spans=list(zip(bounds,bounds[1:]+[duration]))
    return spans if len(spans)==len(active_blocks(project)) and all(b-a>.15 for a,b in spans) else None


def framing_cards(project,block,lines,duration):
    from .combat import framing_cards as base,pair_in
    if block.kind!='outro':return base(project,block,lines,duration)
    # Keep promo/subscription handling, replace winner-only recap extraction.
    cards,warnings=base(project,block,lines,duration)
    cards=[c for c in cards if c.title!='ПРОГНОЗ'];seen=set()
    for i,line in enumerate(lines):
        from .graphics import block_teams
        from .combat import name_position
        claims=[]
        for owner in project.blocks:
            if owner.uid in seen or not owner.forecast or not pair_in(owner.title,line.text):continue
            if not re.search(r'total|raund|ko.p|kam|g.alab|tanlov',norm(line.text)):continue
            positions=[name_position(n,line.text) for n in block_teams(owner.title)]
            claims.append((max(0,min(positions)-1),owner))
        claims.sort(key=lambda v:v[0]);count=max(1,len(line.text.split()))
        for j,(pos,owner) in enumerate(claims):
            a=line.start if j==0 else line.start+(line.end-line.start)*pos/count
            b=line.end if j+1==len(claims) else line.start+(line.end-line.start)*claims[j+1][0]/count
            if b-a<.15:continue
            cards.append(Card(a,b,'ПРОГНОЗ',owner.forecast,i,forecast_id=owner.uid,fixture=owner.title));seen.add(owner.uid)
    for owner in project.blocks:
        if owner.forecast and owner.uid not in seen:
            cards.append(Card(max(0,duration-4),duration,'ПРОГНОЗ',owner.forecast,forecast_id=owner.uid,fixture=owner.title,review_reason='Повтор ставки не найден. Проверьте время.'))
    return cards,warnings
