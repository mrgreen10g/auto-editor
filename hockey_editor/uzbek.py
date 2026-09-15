"""Uzbek football scripts. Written timecodes are hints, never edit boundaries."""
import re
from .model import Block,EventRequest
from .timeline import Card,frame
from .alignment import split_script
from .graphics import block_teams
from .team_names import football_positions, football_identity


def norm(text):
    return text.casefold().translate(str.maketrans({'’':"'",'‘':"'",'ʻ':"'",'ʼ':"'",'`':"'",'–':'—'}))


def number(n):
    n=int(n);ones=['nol','bir','ikki','uch',"to'rt",'besh','olti','yetti',"sakkiz","to'qqiz"]
    tens=['',"o'n",'yigirma',"o'ttiz",'qirq','ellik','oltmish','yetmish','sakson',"to'qson"]
    if n<10:return ones[n]
    if n<100:return tens[n//10]+(' '+ones[n%10] if n%10 else '')
    if n<1000:return ones[n//100]+' yuz'+(' '+number(n%100) if n%100 else '')
    if n<1000000:return number(n//1000)+' ming'+(' '+number(n%1000) if n%1000 else '')
    return str(n)


def spoken_uz(text):
    text=norm(text).replace('x2','iks ikki').replace('1x','bir iks')
    text=re.sub(r'(\d+)[,.](\d+)\b',lambda m:number(m[1])+' butun '+number(m[2]),text)
    text=re.sub(r'(\d+)\s*:\s*(\d+)',lambda m:number(m[1])+' '+number(m[2]),text)
    return re.sub(r'\d+',lambda m:number(m[0]),text)


HINT=re.compile(r'^\s*(\d{1,2}):(\d{2})\s*[—–-]\s*(\d{1,2}):(\d{2})\s*$')

def display_title(line):
    return ' '.join(w.upper() if w.upper() in ('PSG','PSJ','OKMK','AGMK')
                    else w[:1].upper()+w[1:].lower() for w in line.split())

def parse_script(text):
    sections=[];current=None
    rows=text.splitlines()
    # Authors supply an unspoken title and fixture index before KIRISH.
    start=next((i for i,l in enumerate(rows) if norm(l.strip().lstrip('\ufeff'))=='kirish'),None)
    if start is None:raise ValueError('Начните узбекский сценарий с заголовка KIRISH.')
    for raw in rows[start:]:
        line=raw.strip().lstrip('\ufeff')
        if not line:continue
        key=norm(line)
        kind='intro' if key=='kirish' else 'outro' if key in ('yakuniy tanlovlar','yakuniy cta','yakuniy ekspress','xulosa','yakun') else None
        pair=re.fullmatch(r"[A-ZА-ЯЁa-zа-яёʻʼ'’ .0-9]+\s+[—–-]\s+[A-ZА-ЯЁa-zа-яёʻʼ'’ .0-9]+",norm(line))
        pair_names=block_teams(line) if pair else []
        known=bool(pair_names) and all(football_identity(n) for n in pair_names)
        pair_heading=pair and not line.endswith('.') and len(line)<100 and (known or line.upper()==line)
        if current and current['kind']=='outro':pair_heading=False
        if kind or pair_heading:
            current={'kind':kind or 'analysis','title':display_title(line) if not kind else 'Boshlanish' if kind=='intro' else 'Yakun','lines':[],'hint':[]};sections.append(current);continue
        hint=HINT.match(line)
        if hint:
            if current:current['hint']=[int(hint[1])*60+int(hint[2]),int(hint[3])*60+int(hint[4])]
            continue
        if current is None:raise ValueError('Начните узбекский сценарий с заголовка KIRISH.')
        current['lines'].append(line)
    intro=[s for s in sections if s['kind']=='intro'];analyses=[s for s in sections if s['kind']=='analysis'];outro=[s for s in sections if s['kind']=='outro']
    if len(intro)!=1 or not 1<=len(analyses)<=4 or not outro:raise ValueError('Нужны KIRISH, 1–4 заголовка пар команд и YAKUNIY TANLOVLAR / YAKUNIY CTA.')
    def make(s):return Block(title=s['title'],script='\n'.join(s['lines']),kind=s['kind'],language='uz',source_hint=s['hint'])
    start=make(intro[0]);end=make(outro[0]);end.script='\n'.join('\n'.join(s['lines']) for s in outro)
    if end.source_hint and outro[-1]['hint']:end.source_hint=[end.source_hint[0],outro[-1]['hint'][1]]
    start.uid='intro';end.uid='outro'
    return start,[make(s) for s in analyses],end


def prepared(block):
    if block.asr_lines:return '\n'.join(l['text'] for l in block.asr_lines)
    values=split_script(block.script);result=[];i=0
    while i<len(values):
        line=values[i];t=norm(line)
        promo=('telegram' in t or ("youtube'da" in t and 'prognoz' in t) or ('aytgancha' in t and 'prognoz' in t))
        if block.kind!='analysis' and promo:
            j=i
            while j<min(len(values),i+10) and 'havola' not in norm(values[j]):j+=1
            if j<len(values) and 'havola' in norm(values[j]):
                result.append(' — '.join(v.rstrip('.!?') for v in values[i:j+1]));i=j+1;continue
        if block.kind=='outro' and ('izoh' in t or 'komment' in t) and line.endswith(':'):
            j=i+1
            while j<len(values) and '?' in values[j]:j+=1
            if j>i+1:
                result.append(' — '.join(v.rstrip('.!?') for v in values[i:j]));i=j;continue
        result.append(line);i+=1
    return '\n'.join(result)


def mentions(title,text):
    names=block_teams(title)
    hits=[football_positions(name,text,names) for name in names]
    return bool(names[1]) and any(a[1]<=b[0] or b[1]<=a[0] for a in hits[0] for b in hits[1])


def core(text):
    # Remove only introductory speech; retain the actual selection and team names.
    return re.sub(r"^.*?mening\s+(?:asosiy\s+)?tanlovim\s*[—:–-]?\s*",'',text,flags=re.I).strip(' .')


def bet(text):
    raw=core(text);t=norm(raw)
    total=re.search(r"(\d+(?:[,.]\d+)?)\s*(?:ta)?dan\s+(ko'p|kam)\s+gol",t)
    pieces=[]
    double=re.search(r"([\w'’ʻʼ .-]+?)\s+\b(1x|x2|12)\b",raw,re.I)
    winner=re.search(r"([\w'’ʻʼ .-]+?)\s+g['’ʻʼ]alab\w*",raw,re.I)
    if double:pieces.append(double[1].strip().title()+' '+double[2].upper())
    elif winner:pieces.append(winner[1].strip().title()+' g‘alabasi')
    if total:pieces.append('Jami gollar: '+total[1].replace('.',',')+(' dan ko‘p' if total[2]=="ko'p" else ' dan kam'))
    # Unknown bets keep the complete Uzbek wording rather than inventing a market.
    return '\n'.join(pieces) if pieces else raw


def classify(text):
    t=norm(text).replace("go'l","gol").replace("go'il","gol");is_pick='mening tanlovim' in t or 'mening asosiy tanlovim' in t
    market=bool(re.search(r"\b(?:x2|1x)\b|g'alab|(?:ta)?dan (?:ko'p|kam) gol|fora|total",t))
    if is_pick or (market and text==text.upper() and re.search('[A-Z]',text)):
        return 'ПРОГНОЗ',bet(text)
    if re.search(r'\d+:\d+',t) and any(s in t for s in ('mos',"o'tadi",'yetarli')):
        return 'УСЛОВИЯ ПРОГНОЗА',', '.join(re.findall(r'\d+:\d+',text))+' — mos keladi'
    if any(s in t for s in ('kamida','kerak',"shart emas",'majburiy emas','qaytar','stavka','tanlovimiz yut')):
        if any(s in t for s in ('gol',"mag'lub",'durang','qaytar','stavka')):
            body=re.sub(r"^(?:Ya'ni|Bizga|Birinchisi|Ikkinchisi)\s*[—:–-]?\s*",'',text,flags=re.I).strip()
            body=re.sub(r"\buchrashuvda\s+|\bumumiy hisobda\s+",'',body,flags=re.I)
            return 'УСЛОВИЯ ПРОГНОЗА',body
    if any(w in t for w in ('jarohat','diskvalifik','safdan chi')):return 'СОСТАВ КОМАНДЫ',text
    if re.search(r'\d',t) and any(w in t for w in ('zarba','foiz','statistika','koeffits','g\'alaba','durang','mag\'lubiyat')):
        return 'СТАТИСТИКА',text
    return None,''


def events(block,matches):
    sources=[m for m in matches if m.id in block.match_ids]
    if len(sources)>1:raise ValueError('Оставьте одну очную встречу на футбольный разбор.')
    if not sources:return []
    result=[]
    speech=[l['text'] for l in block.asr_lines] if block.asr_lines else split_script(block.script)
    for index,line in enumerate(speech):
        t=norm(line);title,_=classify(line)
        if str(index) in block.speech_cards:title=block.speech_cards[str(index)]['title']
        if title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','СОСТАВ КОМАНДЫ') or any(v in t for v in ('telegram','obuna','layk')):continue
        if len(t.split())>=6 or any(w in t for w in ("o'yn","o'yin",'hujum','himoya','vaziyat','nazorat','bosim','hisob','uchrashuv','gollar','birinchi gol','ikkinchi gol','mezbon','mehmon','jamoa','safar','maydon')):
            result.append(EventRequest(sources[0].id,line,kind='play'))
    return result


LABELS={'РАЗБОР МАТЧА':'O‘YIN TAHLILI','ПРОГНОЗ':'MENING TANLOVIM','УСЛОВИЯ ПРОГНОЗА':'TANLOV SHARTLARI','СТАТИСТИКА':'STATISTIKA','ИНФОРМАЦИЯ':'MA’LUMOT','СОСТАВ КОМАНДЫ':'JAMOA TARKIBI','ОЖИДАЕМЫЙ СЧЁТ':'KUTILAYOTGAN HISOB','СМЕНА МАТЧА':'KEYINGI O‘YIN','ИТОГИ ВЫПУСКА':'YAKUNIY TANLOVLAR','ВОПРОС ЗРИТЕЛЯМ':'FIKRINGIZNI YOZING','РЕЗУЛЬТАТ МАТЧА':'O‘YIN NATIJASI','КОЭФФИЦИЕНТЫ':'KOEFFITSIYENTLAR'}
def card_label(title):return LABELS.get(title,'MA’LUMOT')


def framing_cards_uz(project,block,lines,duration):
    if block.asr_lines:return asr_framing_cards(project,block,lines,duration)
    from .framing import forecast_text
    from .media import probe
    cards=[];seen=set();owner=None;analyses=[b for b in project.blocks if b.kind=='analysis']
    for i,line in enumerate(lines):
        t=norm(line.text)
        if 'telegram' in t:
            asset=project.assets.get('telegram','')
            if not asset:raise ValueError('Добавьте Telegram узбекского ведущего.')
            if 'havola' not in t:raise ValueError('Дополните фразу Telegram словами о ссылке (Havola).')
            cards.append(Card(line.start,line.end,'ТЕЛЕГРАМ','Telegram',i,asset));continue
        pairs=[b for b in analyses if mentions(b.title,line.text)]
        if pairs:
            if len(pairs)>1:raise ValueError('Разделите представления пар команд переносом строки: '+line.text)
            owner=pairs[0]
        if block.kind=='intro':
            if pairs and owner.uid not in seen:
                seen.add(owner.uid);cards.append(Card(line.start,line.end,'РАЗБОР МАТЧА',owner.title,i));continue
            title,body=classify(line.text)
            if title and body:cards.append(Card(line.start,line.end,title,body,i))
        else:
            title,body=classify(line.text)
            # Recap often names the pair on one line and the bet on the next.
            if title=='ПРОГНОЗ' or (owner and re.search(r"(?:ta)?dan (?:ko'p|kam) gol|\bx2\b|\b1x\b",t)):
                if owner is None:raise ValueError('Перед повтором ставки укажите пару команд: '+line.text)
                text=forecast_text(owner)
                if not text:raise ValueError('Не найден основной прогноз: '+owner.title)
                cards.append(Card(line.start,line.end,'ПРОГНОЗ',text,i,forecast_id=owner.uid));seen.add(owner.uid);continue
            if 'obuna' in t or 'layk bos' in t:
                asset=project.assets.get('subscribe','')
                if not asset:raise ValueError('Добавьте анимацию подписки узбекского ведущего.')
                end=frame(line.start+probe(asset)['duration'])
                cards.append(Card(line.start,end,'ПОДПИСКА','Obuna bo‘ling',i,asset))
            if 'izoh' in t or 'komment' in t:
                question=re.split(r'[:—]',line.text,maxsplit=1)[-1].strip()
                cards.append(Card(line.start,line.end,'ВОПРОС ЗРИТЕЛЯМ',question,i))
    missing=[b.title for b in analyses if b.uid not in seen]
    if missing:raise ValueError(('В начале не найдены пары: ' if block.kind=='intro' else 'В итогах не найдены повторы ставок: ')+', '.join(missing))
    if block.kind=='outro' and (not lines or not re.search(r"ko'rishguncha|xayr|omon bo'ling",norm(lines[-1].text))):
        raise ValueError('Последняя строка завершения должна содержать полное прощание ведущего.')
    result=[]
    for card in cards:
        override=block.card_overrides.get(str(card.line))
        if override is not None and not card.asset and card.title!='ПРОГНОЗ':
            if not override.strip():continue
            card.text=override
        result.append(card)
    from .framing import optional_subscription
    return optional_subscription(result,duration)


def asr_framing_cards(project,block,lines,duration):
    from .media import probe
    cards=[]
    for i,line in enumerate(lines):
        annotation=block.speech_cards.get(str(i))
        if annotation:
            title,text=annotation['title'],annotation['text'];asset=''
            if title=='ТЕЛЕГРАМ':
                asset=project.assets.get('telegram','')
                if not asset:raise ValueError('Добавьте запись Telegram узбекского ведущего.')
            cards.append(Card(line.start,line.end,title,text,i,asset,forecast_id=annotation.get('forecast_id','')))
            continue
        t=norm(line.text)
        if block.kind=='outro':
            if 'obuna' in t or 'layk bos' in t:
                asset=project.assets.get('subscribe','')
                if not asset:raise ValueError('Добавьте анимацию подписки узбекского ведущего.')
                end=frame(line.start+probe(asset)['duration'])
                cards.append(Card(line.start,end,'ПОДПИСКА','Obuna bo‘ling',i,asset))
            if ('izoh' in t or 'komment' in t) and ('yoz' in t or '?' in t):
                cards.append(Card(line.start,line.end,'ВОПРОС ЗРИТЕЛЯМ',line.text,i))
        else:
            title,text=classify(line.text)
            if title and text:cards.append(Card(line.start,line.end,title,text,i))
    for card in cards:
        value=block.card_overrides.get(str(card.line))
        if value is not None and not card.asset and card.title!='ПРОГНОЗ':card.text=value
    from .framing import optional_subscription
    return optional_subscription([c for c in cards if c.text.strip()],duration)
