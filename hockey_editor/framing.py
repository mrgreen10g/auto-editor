"""Intro/outro semantics; reusable alpha assets and shared forecast cards."""
from pathlib import Path
import copy,re,json,hashlib,subprocess,os
from .timeline import Card,Line,Plan,frame
from .alignment import split_script
from .card_text import classify_card,summarize_card
from .graphics import block_teams
from .event_rules import team_position
from .media import probe,ffmpeg


def prepared_script(block):
    if block.kind=='analysis':return block.script
    # Align team introductions independently even inside a single sentence.
    from .event_rules import TEAMS
    names='|'.join(re.escape(n) for n in TEAMS)
    text=re.sub(r'[,：:]\s*(?=(?:а\s+)?(?:московск\w*\s+)?«?(?:'+names+r')\b)', '\n', block.script, flags=re.I)
    lines=split_script(text);result=[]
    for line in lines:
        if re.search(r'ссылка\s+находится\s+в\s+описании',line,re.I) and result and 'телеграм' in result[-1].lower():
            result[-1]=result[-1].rstrip('.!?')+' — '+line
        else:result.append(line)
    return '\n'.join(result)


def pair_matches(text,block):
    names=block_teams(block.title)
    def mentioned(name):
        key=name.lower().split()[0]
        if key in ('ска','цска'):pattern=r'\b'+key+r'\b'
        else:pattern=r'\b'+re.escape(key[:3] if key=='лада' else key[:6])+r'\w*'
        return re.search(pattern,text.lower()) is not None
    return len(names)==2 and all(mentioned(n) for n in names if n)


def forecast_text(block):
    if block.edit_plan:
        card=next((c for c in reversed(block.edit_plan.get('cards',[])) if c['title']=='ПРОГНОЗ'),None)
        if card:return card['text']
    for i,line in reversed(list(enumerate(split_script(block.script)))):
        if classify_card(line)=='ПРОГНОЗ':
            return block.card_overrides.get(str(i),summarize_card('ПРОГНОЗ',line))
    return ''


def framing_cards(project,block,lines,duration):
    cards=[];warnings=[];seen_pairs=set()
    analyses=[b for b in project.blocks if b.kind=='analysis']
    for i,line in enumerate(lines):
        low=line.text.lower()
        if 'телеграм' in low:
            asset=project.assets.get('telegram','')
            if not asset:raise ValueError('Добавьте запись Telegram для фразы о канале.')
            if 'ссылка' not in low:raise ValueError('В сценарии после упоминания Telegram должна быть фраза о ссылке в описании.')
            cards.append(Card(line.start,line.end,'ТЕЛЕГРАМ','Telegram · канал автора',i,asset))
            continue
        pairs=[b for b in analyses if pair_matches(line.text,b)]
        if block.kind=='intro' and pairs and pairs[0].uid not in seen_pairs:
            # Normally prepared_script splits the spoken pairs; fail visibly if
            # a custom sentence still contains several rather than guess timing.
            if len(pairs)>1:raise ValueError('Разделите представления пар в сценарии начала переносом строки: '+line.text)
            seen_pairs.add(pairs[0].uid)
            cards.append(Card(line.start,line.end,'РАЗБОР МАТЧА',pairs[0].title,i));continue
        if block.kind=='outro':
            if pairs and re.search(r'беру|выбираю|вариант|выбор|став',low):
                owner=pairs[0];text=forecast_text(owner)
                if not text:raise ValueError('Не найден основной прогноз в разборе: '+owner.title)
                cards.append(Card(line.start,line.end,'ПРОГНОЗ',text,i,forecast_id=owner.uid));continue
            if re.search(r'подписывай|ставьте\s+лайк',low):
                asset=project.assets.get('subscribe','')
                if not asset:raise ValueError('Добавьте анимацию подписки для призыва ведущего.')
                end=frame(line.start+probe(asset)['duration'])
                if end>duration+.034:raise ValueError('Анимация подписки длиннее оставшегося завершения. Нужна более короткая анимация, чтобы сохранить её целиком и закончить на прощании.')
                cards.append(Card(line.start,end,'ПОДПИСКА','Подписка и лайк',i,asset))
            if 'комментари' in low:
                question=re.split(r'комментари\w*\s*:\s*',line.text,maxsplit=1,flags=re.I)[-1]
                # Keep the choice in the question; remove rhetorical filler only.
                question=re.sub(r'действительно\s+должен\s+идти\s+настолько\s+явным', '—',question,flags=re.I)
                question=re.sub(r'рынок\s+сейчас\s+просто\s+слишком\s+сильно\s+покупает\s+имя\s+клуба','переоценённое имя',question,flags=re.I)
                question=re.sub(r'\s+',' ',question).strip()
                cards.append(Card(line.start,line.end,'ВОПРОС ЗРИТЕЛЯМ',question,i))
            continue
        if re.search(r'проиграл\w*\s+оба\s+(?:официальных\s+)?матча',low):
            team=next((n for n in ('Динамо','СКА','ЦСКА','Лада','Адмирал','Торпедо') if team_position(n,line.text) is not None),'Команда')
            cards.append(Card(line.start,line.end,'СТАРТ СЕЗОНА',team+'\nДва поражения',i));continue
        if 'спасаться в концовке' in low and pairs:
            cards.append(Card(line.start,line.end,'ПРЕДЫДУЩАЯ ВСТРЕЧА',pairs[0].title+'\nБорьба до концовки',i));continue
        if re.match(r'(?:всем привет|сегодня разбер)',low):continue
        if 'фаворит' in low and 'букмекер' in low:
            cards.append(Card(line.start,line.end,'ЛИНИЯ БУКМЕКЕРОВ','Хозяева — фавориты',i));continue
        title=classify_card(line.text)
        if title:
            text=summarize_card(title,line.text)
            if text:cards.append(Card(line.start,line.end,title,text,i))
    if block.kind=='outro':
        for b in analyses:
            if not any(c.forecast_id==b.uid for c in cards):
                raise ValueError('В итогах не найден повтор прогноза: '+b.title+'. Проверьте сценарий завершения.')
        if not lines or not re.search(r'до\s+(?:встречи|свидания)|увидимся|пока',lines[-1].text,re.I):
            raise ValueError('В конце сценария укажите полное прощание ведущего.')
    if block.kind=='intro':
        missing=[b.title for b in analyses if b.uid not in seen_pairs]
        if missing:raise ValueError('В начале не найдены представления пар: '+', '.join(missing))
    updated=[]
    for card in cards:
        override=block.card_overrides.get(str(card.line))
        if override is not None and not card.asset and card.title!='ПРОГНОЗ':
            if not override.strip():continue
            card.text=override
        updated.append(card)
    return updated,warnings


def disclaimer_plan(path):
    info=probe(path)
    if not info['video']:raise ValueError('Дисклеймер должен быть видео.')
    duration=frame(info['duration'])
    return Plan(0,duration,[(0,duration)],[],[],[],[],duration,0,[],
                [{'path':path,'start':0,'end':duration,'rotation':0,'kind':'disclaimer'}])


def alpha_bounds(path,cache,cancel):
    """Union of nontransparent pixels at sampled times, in original dimensions."""
    from PIL import Image
    import io
    from .host_media import identity
    key=hashlib.sha256(json.dumps(identity(path)).encode()).hexdigest()
    target=Path(cache)/(key+'-alpha.json')
    if target.exists():return json.loads(target.read_text())
    info=probe(path);bounds=[]
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    for t in (min(.5,info['duration']/3), min(2,info['duration']/2),info['duration']*.5,info['duration']*.85):
        if cancel.is_set():
            from .media import Cancelled
            raise Cancelled()
        r=subprocess.run([ffmpeg(),'-hide_banner','-loglevel','error','-ss',str(t),'-i',str(path),'-frames:v','1',
                          '-vf','scale=480:-1','-f','image2pipe','-c:v','png','-pix_fmt','rgba','-'],capture_output=True,timeout=30,creationflags=flags)
        if r.returncode:raise ValueError('Не удалось прочитать прозрачную анимацию: '+Path(path).name)
        im=Image.open(io.BytesIO(r.stdout));a=im.getchannel('A');box=a.point(lambda v:255 if v>8 else 0).getbbox()
        if box:bounds.append((box,im.size))
    if not bounds:raise ValueError('Анимация полностью прозрачна: '+Path(path).name)
    lo=min(b[0]/size[0] for b,size in bounds);top=min(b[1]/size[1] for b,size in bounds)
    hi=max(b[2]/size[0] for b,size in bounds);bottom=max(b[3]/size[1] for b,size in bounds)
    margin=.012
    x=max(0,int((lo-margin)*info['width']));y=max(0,int((top-margin)*info['height']))
    w=min(info['width']-x,int((hi-lo+2*margin)*info['width']));h=min(info['height']-y,int((bottom-top+2*margin)*info['height']))
    result=[x,y,w,h];target.write_text(json.dumps(result));return result


def asset_filter(card,cache,cancel):
    length=card.end-card.start;info=probe(card.asset)
    if card.source_in+length>info['duration']+.034:
        raise ValueError('Анимация короче выбранной фразы: '+Path(card.asset).name)
    filt=f'trim=duration={length:.6f},setpts=PTS-STARTPTS,fps=30,format=rgba'
    if card.title=='ТЕЛЕГРАМ':
        x,y,w,h=alpha_bounds(card.asset,cache,cancel)
        filt+=f',crop={w}:{h}:{x}:{y},scale=340:600:force_original_aspect_ratio=decrease,pad=iw+16:ih+16:8:8:color=black@0'
        return filt,'38','(720-overlay_h)/2'
    # Subscription retains its complete canvas, position and authored timing.
    filt+=',scale=1280:720'
    return filt,'0','0'


def split_full_script(text):
    # Headings are standalone team pairs; hyphens within ordinary prose aren't headings.
    from .event_rules import TEAMS
    rows=text.splitlines();headers=[]
    for i,line in enumerate(rows):
        if len(line.strip())<75 and re.fullmatch(r'[А-Яа-яЁёA-Za-z «»]+\s+[—–-]\s+[А-Яа-яЁёA-Za-z «»]+',line.strip()):
            pair=block_teams(line.strip())
            if all(any(team_position(team,name) is not None for team in TEAMS) for name in pair):headers.append(i)
    end=next((i for i,l in enumerate(rows) if re.match(r'\s*Итак[, ]',l,re.I)),None)
    if not 1<=len(headers)<=4 or end is None or end<=headers[-1]:
        raise ValueError('Нужны отдельные строки с названиями пар и завершение со слова «Итак». Можно заполнить тексты вручную.')
    intro='\n'.join(rows[:headers[0]]).strip();outro='\n'.join(rows[end:]).strip()
    blocks=[(rows[a].strip(),'\n'.join(rows[a:(headers[j+1] if j+1<len(headers) else end)]).strip()) for j,a in enumerate(headers)]
    if not intro:raise ValueError('Перед первым разбором не найден текст начала.')
    return intro,blocks,outro

