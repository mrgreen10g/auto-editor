"""Uzbek speech with the same footage search and montage engine as RU hockey."""
import copy,hashlib,json,re
from .model import Block
from .timeline import Line,Card,frame
from .alignment import split_script
from .uzbek import norm
from .hockey_names import identity,mentioned,pair_in,canonicalize,display

def clean_script(text):
    # Notes can contain English captions and club headings: remove whole blocks.
    text=re.sub(r'\[\s*(?:МОНТАЖ[ЕЁ]РУ|РЕДАКТОРУ|ПРИМЕЧАНИЕ|КОММЕНТАРИЙ)\s*:.*?(?:\]|\Z)','',text,flags=re.I|re.S)
    text=re.sub(r':chatgpt-content-reference\{[^}]*\}|[^]*','',text)
    text=re.sub(r'https?://\S+|www\.\S+','',text)
    return '\n'.join(l.strip() for l in text.splitlines() if not re.search('[А-Яа-яЁё]',l)).strip()

def heading(line):
    t=re.sub(r'^\s*\d+[.)]\s*','',line.split('|')[0]).strip(' #*')
    # Only two standalone names qualify, never a prose comparison or recap label.
    from .graphics import block_teams
    names=block_teams(t)
    if len(names)==2 and all(identity(n) for n in names):return ' — '.join(display(identity(n)) for n in names)
    return None

def parse_script(text):
    intro=None;outro=None;blocks=[];current=None
    for raw in clean_script(text).splitlines():
        line=raw.strip().lstrip('\ufeff');key=norm(line.split('|')[0].strip(' #*'))
        if not line:continue
        if key=='kirish':
            if intro is not None:
                if not intro.script:continue
                raise ValueError('В сценарии должен быть один KIRISH.')
            intro=Block(title='Boshlanish',uid='intro',kind='intro',language='uz',sport='hockey');current=intro;continue
        if key in ('yakun','xulosa','yakuniy tanlovlar','yakuniy cta','yakuniy ekspress'):
            if outro is None:outro=Block(title='Yakun',uid='outro',kind='outro',language='uz',sport='hockey')
            current=outro;continue
        title=heading(line)
        if title and not line.endswith((':','.','!','?')) and intro is not None and current is not outro and (re.match(r'^\d+[.)]',line) or '|' in line or line.upper()==line):
            current=Block(title=title,language='uz',sport='hockey');blocks.append(current);continue
        if current is None or re.fullmatch(r'\d+:\d+\s*[—–-]\s*\d+:\d+',line):continue
        current.script+=('\n' if current.script else '')+line
    if not intro or not blocks or not outro:raise ValueError('Нужны KIRISH, пары хоккейных команд и YAKUN / YAKUNIY TANLOVLAR.')
    if any(len(b.script.strip())<30 for b in [intro,*blocks,outro]):raise ValueError('У раздела отсутствует текст: проверьте заголовки и сценарий.')
    for b in blocks:
        picks=[body for row in split_script(b.script) for title,body in [classify(row)] if title=='ПРОГНОЗ']
        b.forecast=picks[-1] if picks else ''
    intro.featured_pairs=[b.title for b in blocks]
    return intro,blocks,outro

def numeric(text):
    t=norm(text)
    t=re.sub(r"\bto'?(?:r|ri)yam(?:ti)?dan\b","4,5 dan",t)
    t=re.sub(r'\bbeshta(?:ndan|na|da)\b','5 dan',t)
    if re.search(r'total|tanlo|varia',t):t=re.sub(r'\b(?:brixs|briggs)\b','1x',t)
    t=re.sub(r'\bbir\s*(?:iks|eks)\b','1x',t)
    t=re.sub(r'\b(?:iks|eks)\s*ikki\b','x2',t)
    t=re.sub(r'\b(?:plyus|plus)\s*','+',t);t=re.sub(r'\bminus\s*','-',t)
    t=t.replace("qo'shimcha vaqt",'overtaym').replace('overtime','overtaym')
    for a,z in [("besh yarim","5,5"),("to'rt yarim","4,5"),("uch yarim","3,5"),("ikki yarim","2,5"),("bir yarim","1,5")]:t=t.replace(a,z)
    for n,w in enumerate(['nol','bir','ikki','uch',"to'rt",'besh','olti','yetti','sakkiz',"to'qqiz", "o'n"]):
        t=re.sub(r'\b'+re.escape(w)+r'(?:ta)?(?=dan\b|\b)',str(n),t)
    t=re.sub(r'(\d)(?:ta)?dan\b',r'\1 dan',t)
    return t

def bet(text):
    raw=re.sub(r'^.*?(?:tanlovim|tanlayman|tanlovimiz)\s*[:—–-]?\s*','',text,flags=re.I).strip(' .→') or text.strip(' .')
    t=numeric(raw);clubs=mentioned(raw);team=display(clubs[0]) if clubs else ''
    pieces=[]
    chance=re.search(r'\b(1x|x2|12)\b',t)
    total=re.search(r"(?:total\s*)?(\d+(?:[,.]\d+)?)\s*(?:ta)?dan\s+(ko'p|kam)",t)
    handicap=re.search(r'fora\w*\s*(?:bilan\s*)?\(?\s*([+-]?\d+(?:[,.]\d+)?)',t)
    if chance:pieces.append((team+' '+chance[1].upper()).strip())
    elif handicap:pieces.append((team+' FORA ('+handicap[1].replace('.',',')+')').strip())
    elif re.search(r"g['’]?alab",t):pieces.append((team+' g‘alabasi').strip())
    if total:
        label='Individual total' if 'individual' in t or 'jamoa totali' in t else 'Total'
        pieces.append((team+'\n' if label=='Individual total' and team else '')+label+': '+total[1].replace('.',',')+(' dan ko‘p' if total[2]=="ko'p" else ' dan kam'))
    if not pieces:return ''
    if re.search(r'asosiy vaqt|60 daqiqa',t):pieces.append('Asosiy vaqt')
    elif re.search(r'(?:overtaym|bullit).*(?:bilan|hisobga)|(?:hisobga|bilan).*(?:overtaym|bullit)|yakuniy.*g.alab',t):pieces.append('OT va bullitlar bilan')
    elif 'overtaymda' in t:pieces.append('Faqat overtaymda')
    return '\n'.join(pieces)

def classify(text):
    t=norm(text);body=bet(text)
    pick=bool(re.search(r'tanlo\w*|tanlu\w*|tanlayman|varia\w*|qildik',t) or (text==text.upper() and re.search('[A-Z]',text)))
    short_market=bool(len(t.split())<=16 and re.search(r'^total\s+\d|\b(?:1x|x2)\b|\bfora\s*[+-]?\d',numeric(t)))
    pick=pick or (short_market and not re.search(r'emas|olmay|yutqaz|o.tgan|agar|bukmeker',t))
    if pick and body:
        if re.search(r'\bemas\b|olmayman|tanlamay',t):return None,''
        return 'ПРОГНОЗ',body
    if re.search(r'mos|o.tadi|qaytar|kerak|kamida',t) and re.search(r'\d|shayba|gol|qaytar',t):
        return 'УСЛОВИЯ ПРОГНОЗА',text.strip() if len(text.split())<=23 else ''
    if re.search(r'telegram|havola|obuna|layk|izohda|kafolat',t):return None,''
    # Bare pair labels are not statistics; historical scores are.
    if re.search(r'\d+\s*[:–-]\s*\d+',t) and re.search(r'hisob|yutqaz|yutdi|mag.lub|g.alaba|uchrashuv',t):
        return 'РЕЗУЛЬТАТ МАТЧА',text.strip()
    if re.search(r'jarohat|transfer|murabbiy|darvozabon.*(?:keldi|o.tdi)|tarkib.*(?:yo.q|o.zgar)|safdan',t):
        return 'СОСТАВ КОМАНДЫ',text.strip() if len(text.split())<=25 else ''
    if re.search(r'\d|\b(?:birinchi|ikki|uch|to.rt|besh|olti|yetti|sakkiz|o.n)(?:ta)?\b',t) and re.search(r'yosh|g.alaba|mag.lub|shayba|zarba|foiz|ketma.ket|xet.trik|raund|final|chempion|uchrashuv|overtaym|overtime|\bgol\b',t):
        return 'СТАТИСТИКА',text.strip() if len(text.split())<=25 else ''
    from .uz_facts import argument
    value=argument(text)
    if value:return 'ИНФОРМАЦИЯ',value
    if re.search(r'power play|penalty kill|ko.pchilik|kamchilik|zveno|bo.sh darvoza',t) and 3<=len(t.split())<=23:
        return 'ИНФОРМАЦИЯ',text.strip()
    return None,''

def hockey_semantics(text):
    """An internal adapter only: emitted requests retain original Uzbek words."""
    t=canonicalize(text).replace('St. Louis','St Louis')
    score=re.search(r'\d+\s*:\s*\d+',text)
    if score:
        from .hockey_names import hits
        candidates=[club for a,z,club in hits(text[:score.start()]) if not re.search(r'(?:ning|ni|ga|da|dan)$',norm(text[a:z]))]
        if candidates:t=candidates[-1]+' '+t
        # A quoted old scoreboard with no outcome verb doesn't establish which
        # club scored first. Use archive play, not a fabricated exact goal.
        if not re.search(r'mag.lub|yutqaz|yutdi|g.alaba|tenglash|oldinga|shayba ur|gol ur',norm(text)):
            t=re.sub(r'\d+\s*:\s*\d+','',t)
    rules=[(r'tanlovim|tanlovimiz|tanlayman','мой выбор'),(r'mos|o.tadi|qaytariladi','ставка проходит'),
        (r'yutqaz\w*|mag.lub bo.l\w*','проиграл'),(r'mag.lub (?:qil|et)\w*|yutdi|g.alaba qozon\w*','победил'),
        (r'hisobni tenglashtir\w*','сравнял'),(r'overtaym','овертайм'),(r'hal qil\w*|g.alaba shaybasi','победный'),
        (r'oldingi|o.tgan|oxirgi|preseason','прошлый'),(r'uchrashuv|o.yin','матч'),
        (r'jarohat|safdan chiq','травма'),(r'fora|koeffitsiyent','фора'),(r'zarba','броски'),
        (r'shayba ur\w*|gol ur\w*','забросил')]
    for pattern,value in rules:t=re.sub(pattern,value,t,flags=re.I)
    return t

def forecast_conflict(reference,spoken):
    """Keep conflicting ASR markets visible for review; never rewrite the script."""
    a,b=numeric(reference),numeric(bet(spoken))
    if not b:return 'Ставка не распознана уверенно. Проверьте текст и время.'
    def values(t):
        return (re.findall(r'[+-]?\d+(?:[,.]\d+)?',t),bool(re.search(r'\bkam\b',t)),bool(re.search(r'ko.p',t)),set(mentioned(t)),bool(re.search(r'overtaym|bullit|\bot\b',t)))
    x,y=values(a),values(b)
    if x[:3]!=y[:3] or (x[3] and y[3] and x[3]!=y[3]) or x[4]!=y[4]:return 'Ставка в речи отличается от сценария. Проверьте число, команду и учёт овертайма.'
    return ''

def events(block,matches,use_manual=True):
    from .event_rules import requests_for
    b=copy.deepcopy(block);b.language='ru';b.sport='';b.title=canonicalize(block.title);b.archive_context=True
    rows=[l['text'] for l in block.asr_lines] if block.asr_lines else split_script(clean_script(block.script))
    from .shorts import promo_line_ranges
    excluded={i for a,z in promo_line_ranges([Line(t,i,i+1) for i,t in enumerate(rows)]) for i in range(a,z+1)}
    rows=[t for i,t in enumerate(rows) if i not in excluded]
    # Apply these exclusions before the shared RU archive selector as well as
    # the fallback below: calls to subscribe are not gameplay narration.
    rows=[t for t in rows if classify(t)[0] not in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА')
          and not re.search(r'telegram|havola|obuna|layk|tanlo|varia|ko.rishguncha',norm(t))]
    rows=[t for t in rows if not (pair_in(block.title,t) and len(t.split())<=12 and not re.search(r'\d+\s*:\s*\d+|yut|mag.lub|g.alaba',norm(t)))]
    mapping={hockey_semantics(t):t for t in rows};b.script='\n'.join(mapping)
    for c in b.clips:c.phrase=hockey_semantics(c.phrase)
    owners=set(mentioned(block.title))
    sources=copy.deepcopy([m for m in matches if (identity(m.home) in owners or identity(m.away) in owners) and m.sport=='hockey'])
    for s in sources:s.home=identity(s.home) or s.home;s.away=identity(s.away) or s.away
    result=requests_for(b,sources,use_manual)
    for e in result:e.phrase=mapping.get(e.phrase,e.phrase)
    result=[e for e in result if e.phrase in rows]
    # Use actual narrated analysis for archive b-roll even without a score cue.
    from .model import EventRequest
    assigned=[m for m in sources if m.id in block.match_ids]
    if not assigned:return result
    seen={e.phrase for e in result};counts={m.id:0 for m in assigned}
    for text in rows:
        t=norm(text);title,_=classify(text)
        if text in seen or title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА') or re.search(r'telegram|havola|obuna|layk|tanlo|varia',t):continue
        if len(t.split())<5:continue
        named=set(mentioned(text))
        choices=[m for m in assigned if named & {identity(m.home),identity(m.away)}] or assigned
        source=min(choices,key=lambda m:counts[m.id]);counts[source.id]+=1
        result.append(EventRequest(source.id,text,kind='play',requested_teams=list(owners)))
    return result

def speech_key(project):
    from .uz_speech import recording_key
    return hashlib.sha256(json.dumps(['uz-hockey-shorts-v1' if project.profile=='uz_hockey_shorts' else 'uz-hockey-v2',recording_key(project),project.recording_times,[(b.uid,b.script,b.title) for b in [project.intro,*project.blocks,project.outro]]],ensure_ascii=False).encode()).hexdigest()

def intro_annotations(project,segments,lo,hi):
    from .hockey_names import hits
    words=[w for s in segments for w in s.get('words',[]) if lo<=w['start']<hi]
    text='';spans=[]
    for w in words:
        start=len(text);text+=norm(w['word']).strip()+' ';spans.append((start,len(text),w))
    found=hits(text);annotations=[]
    for b in project.blocks:
        teams=mentioned(b.title)
        options=[]
        for a,z,club in found:
            if len(teams)!=2 or club!=teams[0]:continue
            for x,y,other in found:
                if other!=teams[1]:continue
                selected=[w for start,end,w in spans if start<max(z,y) and end>min(a,x)]
                if selected and len(selected)<=14:options.append((selected[0]['start'],selected[-1]['end']))
        if options:
            a,z=min(options);annotations.append((a,z,'РАЗБОР МАТЧА',b.title))
    for b in project.blocks:
        if any(v[3]==b.title for v in annotations):continue
        teams=set(mentioned(b.title));single=[(a,z) for a,z,club in found if club in teams]
        if single:
            a,z=single[0];selected=[w for start,end,w in spans if start<z and end>a]
            if selected:annotations.append((selected[0]['start'],selected[-1]['end'],'РАЗБОР МАТЧА',b.title))
    return annotations

def prepare(project,segments,duration):
    from .review import draft_alignment
    from .speech_boundaries import intro_floor,slice_segments
    from .combat import spoken_segments
    from .uz_speech import make_lines
    blocks=[b for b in [project.intro,*project.blocks,project.outro] if b.script.strip()]
    aligned=copy.deepcopy(blocks)
    for b in aligned:b.script=clean_script(b.script)
    cuts=[]
    if project.settings.cut_pauses:
        from .speech_cleanup import remove_retakes
        segments,cuts=remove_retakes(aligned,segments)
    from .uz_hockey_support import check_script
    check_script(project,segments)
    rough=draft_alignment(aligned,segments,duration,'Проверьте границы хоккейного раздела.')
    words=[w for s in segments for w in s.get('words',[])]
    bounds=[0.];floor=intro_floor(words,'uz') if blocks[0].kind=='intro' else 0.;reliable=True
    for b in blocks[1:]:
        approximate=rough[b.uid][0][0].start
        if b.kind=='analysis':
            choices=[s['start'] for s in segments if s['start']>=max(floor,bounds[-1]+1,approximate-8)-.01 and pair_in(b.title,s['text'])]
        else:
            choices=[s['start'] for s in segments if s['start']>=max(bounds[-1]+10,approximate-10) and re.search(r'xullas|qull?as|xulosa|demak|yakun|takror|ko.rib chiqdik',norm(s['text']))]
        if not choices:reliable=False;break
        bounds.append(min(choices,key=lambda x:abs(x-approximate)));floor=bounds[-1]+5
    ranges=list(zip(bounds,bounds[1:]+[duration]))
    shorts=project.profile=='uz_hockey_shorts'
    if shorts and not project.recording_times.strip():
        from .shorts import sections
        try:
            bounds,_,_=sections(project,segments);ranges=list(zip(bounds,bounds[1:]));reliable=True
        except ValueError:reliable=False
    if project.recording_times.strip():
        from .recording_times import recording_ranges,parse_times
        if segments:ranges=recording_ranges(project,segments)
        else:
            ranges=[(a,z) for a,z,_ in parse_times(project.recording_times,len(project.blocks),allow_promos=shorts)]
            if len(ranges)==len(blocks)+1:ranges=ranges[:-2]+[(ranges[-2][0],ranges[-1][1])]
        if len(ranges)!=len(blocks) or ranges[-1][1]>duration+.1:raise ValueError('Проверьте границы таймкодов записи.')
        reliable=True
    if not reliable or len(ranges)!=len(blocks):ranges=[(rough[b.uid][0][0].start,rough[b.uid][0][-1].end) for b in blocks]
    promos=[]
    if shorts:
        from .shorts import promo_spans
        from .uz_speech import telegram_spans
        promos=promo_spans(project,segments,ranges,telegram_spans(words))
    key=speech_key(project)
    for b,(lo,hi) in zip(blocks,ranges):
        local=spoken_segments(slice_segments(segments,lo,hi))
        timed=intro_annotations(project,segments,lo,hi) if b.kind=='intro' and not shorts else []
        from .uz_hockey_support import forecast_span
        pick=forecast_span(b,local,lo,hi) if b.kind=='analysis' else None
        if pick:timed.append((pick[1],pick[2],'ПРОГНОЗ',pick[3]))
        if shorts:timed.extend((a,z,'ТЕЛЕГРАМ','Telegram') for a,z in promos if lo<=a<z<=hi and not any(a<y and z>x for x,y,_,_ in timed))
        rows,timed_cards=make_lines(local,lo,hi,timed)
        if rows:
            for row in rows:row['recognized']=row['text']
        else:
            if project.recording_times.strip():
                fallback=draft_alignment([next(v for v in aligned if v.uid==b.uid)],[],hi-lo,'Речь не распознана.')
                rows=[dict(vars(l),start=l.start+lo,end=l.end+lo) for l in fallback[b.uid][0]]
            else:rows=[vars(l) for l in rough[b.uid][0]]
            for row in rows:row['review_reason']='Речь не распознана. Проверьте время и текст выбранной плашки.'
        if not reliable and rows:rows[0]['review_reason']='Проверьте границу раздела.'
        # Script-backed forecasts; prose is never turned into subtitle cards.
        if rows:rows[0]['omit']=list(cuts)
        annotations=dict(timed_cards)
        if b.kind=='intro':
            for i,card in annotations.items():
                if card['title']=='РАЗБОР МАТЧА' and not pair_in(card['text'],rows[int(i)]['text']):card.update(needs_review=True,review_reason='Одно название пары распознано неуверенно.')
        if pick and pick[4]:
            for card in annotations.values():
                if card['title']=='ПРОГНОЗ':card.update(needs_review=True,review_reason=pick[4])
        for i,row in enumerate(rows):
            if str(i) in annotations:continue
            title,body=classify(row['text'])
            if title=='ПРОГНОЗ' and pick:
                annotations[str(i)]={'title':None,'text':''};continue
            if title and body:
                value={'title':title,'text':body}
                if title=='ПРОГНОЗ' and b.kind=='analysis':
                    from .framing import forecast_text
                    reference=forecast_text(b)
                    reason=forecast_conflict(reference,row['text']) if reference else 'Уточните основной прогноз в сценарии.'
                    if reason:value.update(needs_review=True,review_reason=reason)
                elif title in ('СТАТИСТИКА','РЕЗУЛЬТАТ МАТЧА'):
                    from difflib import SequenceMatcher
                    from .combat_cards import numbers
                    choices=split_script(clean_script(b.script))
                    reference=max(choices,key=lambda t:SequenceMatcher(None,canonicalize(t),canonicalize(row['text'])).ratio(),default='')
                    score=SequenceMatcher(None,canonicalize(reference),canonicalize(row['text'])).ratio()
                    low=any(w.get('probability',1.)<.65 and numbers(w['word']) for s in local for w in s['words'] if row['start']<=w['start']<row['end'])
                    if low or (score>.72 and numbers(reference)!=numbers(row['text'])):
                        value.update(needs_review=True,review_reason='Проверьте число: распознанная статистика не подтверждена уверенно.')
                annotations[str(i)]=value
        if b.speech_key!=key:b.events=[e for e in b.events if e.skipped or (e.selection and e.selection.accepted)]
        b.asr_lines=rows;b.speech_cards=annotations;b.speech_key=key
        # Confirmed choices are keyed to original sources; don't discard them.
        bind_archives(b,project.matches)
    project.episode_key=''
    return ranges

def bind_archives(block,matches):
    if not block.asr_lines:return
    from difflib import SequenceMatcher
    available=events(block,matches,False);used=set()
    for e in block.events:
        if e.skipped or not e.selection or not e.selection.accepted:continue
        options=[(i,v) for i,v in enumerate(available) if i not in used and v.source_id==e.source_id and v.kind==e.kind and v.score==e.score]
        if not options:continue
        i,v=max(options,key=lambda iv:SequenceMatcher(None,norm(e.phrase),norm(iv[1].phrase)).ratio())
        used.add(i);e.phrase=v.phrase

def synchronize(project,cache,cancel,log):
    from .uz_speech import transcribe
    from .host_media import sources
    blocks=[b for b in [project.intro,*project.blocks,project.outro] if b.script.strip()]
    if not all(b.asr_lines and b.speech_key==speech_key(project) for b in blocks):
        prepare(project,transcribe(project,cache,cancel,log),sum(p['duration'] for p in sources(project)))
    from .goals import GoalScanner,propose
    for b in project.blocks:
        local=[m for m in project.matches if m.id in b.match_ids]
        if not local:continue
        bind_archives(b,local)
        existing={(e.source_id,e.phrase,e.kind) for e in b.events}
        b.events.extend(e for e in events(b,local) if (e.source_id,e.phrase,e.kind) not in existing)
        if any(not e.skipped and (not e.selection or not e.selection.accepted) for e in b.events):
            from .shorts import archive_scans
            reused=archive_scans(b,local) if project.profile=='uz_hockey_shorts' else {}
            scans={m.id:reused[m.id] if m.id in reused else GoalScanner(cancel=cancel,log=log).scan(m) for m in local}
            for source_id,data in scans.items():
                reserved={e.selection.candidate_id for e in b.events if e.source_id==source_id and e.selection and e.selection.accepted}
                data['candidates']=[c for c in data['candidates'] if c['id'] not in reserved]
            pending=[e for e in b.events if not e.skipped and (not e.selection or not e.selection.accepted)]
            propose(pending,scans,local,False)
            for e in pending:
                if e.selection and e.kind=='play':
                    m=next(m for m in local if m.id==e.source_id)
                    e.selection.context_label='Архивные кадры · '+m.title

def framing_cards(project,block,lines,duration):
    from .framing import forecast_text,optional_subscription
    from .media import probe
    cards=[];seen=set();owner=None
    for i,line in enumerate(lines):
        t=norm(line.text);pairs=[b for b in project.blocks if pair_in(b.title,t)]
        if len(pairs)==1:owner=pairs[0]
        if block.kind=='intro' and project.profile=='uz_hockey_shorts':
            title,body=classify(line.text)
            if title and body and title!='ПРОГНОЗ':cards.append(Card(line.start,line.end,title,body,i))
        elif block.kind=='intro':
            annotation=block.speech_cards.get(str(i),{})
            if annotation.get('title')=='РАЗБОР МАТЧА':
                pairs=[b for b in project.blocks if b.title==annotation['text']]
            for b in pairs:
                if b.uid not in seen:cards.append(Card(line.start,line.end,'РАЗБОР МАТЧА',b.title,i));seen.add(b.uid)
        else:
            title,body=classify(line.text)
            if title=='ПРОГНОЗ' or (owner and bet(line.text) and re.search(r'total|\b1x\b|\bx2\b|tanlov|tanlay|g.alaba\w*',t)):
                own=[b for b in project.blocks if set(mentioned(line.text)) & set(mentioned(b.title))]
                if len(own)==1:owner=own[0]
                if owner and owner.uid not in seen:
                    expected=forecast_text(owner)
                    cards.append(Card(line.start,line.end,'ПРОГНОЗ',expected,i,forecast_id=owner.uid,review_reason=forecast_conflict(expected,line.text)));seen.add(owner.uid)
            if 'izoh' in t and '?' in t:cards.append(Card(line.start,line.end,'ВОПРОС ЗРИТЕЛЯМ',line.text,i))
        if 'telegram' in t and project.assets.get('telegram'):
            end=line.end
            for other in lines[i+1:i+4]:
                if re.search(r'havola|tavsif|biriktirilgan izoh',norm(other.text)):end=other.end
                else:break
            cards.append(Card(line.start,end,'ТЕЛЕГРАМ','Telegram',-1,project.assets['telegram']))
        if re.search(r'obuna|layk bos',t) and project.assets.get('subscribe') and not any(c.title=='ПОДПИСКА' for c in cards):
            asset=project.assets['subscribe'];cards.append(Card(line.start,frame(line.start+probe(asset)['duration']),'ПОДПИСКА','Obuna bo‘ling',i,asset))
    return optional_subscription(cards,duration)
