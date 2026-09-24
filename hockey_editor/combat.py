"""Uzbek fight scripts, explicit fighter ownership and recoverable speech."""
import copy,hashlib,json,re
from difflib import SequenceMatcher
from pathlib import Path
from .model import Block,EventRequest,EventSelection
from .alignment import split_script
from .graphics import block_teams
from .uzbek import norm
from .timeline import Card


def clean_script(text):
    text=re.sub(r'\[\s*(?:МОНТАЖ[ЕЁ]РУ|РЕДАКТОРУ|ПРИМЕЧАНИЕ)\s*:.*?(?:\]|\Z)','',text,flags=re.I|re.S)
    return '\n'.join(row for row in text.splitlines() if not re.search(r'https?://|www\.|[А-Яа-яЁё]',row))


def heading(line):
    line=re.sub(r'^\s*\d+[.)]\s*','',line.split('|')[0]).strip()
    if len(line)>100 or line.endswith(('.', '!', '?')):return None
    if re.fullmatch(r"[A-Z][A-Z '\"‘’“”ʻʼ.-]+\s+[—–-]\s+[A-Z][A-Z '\"‘’“”ʻʼ.-]+",line):return line
    return None


def parse_script(text):
    index=[];intro=None;outro=None;blocks=[];current=None
    for raw in clean_script(text).splitlines():
        line=raw.strip().lstrip('\ufeff')
        if not line:continue
        key=norm(line.split('|')[0].strip())
        if key=='kirish':
            if intro is not None:raise ValueError('В сценарии должен быть один KIRISH.')
            intro=Block(title='Boshlanish',uid='intro',kind='intro',language='uz',sport='combat');current=intro;continue
        if key in ('yakun','xulosa','yakuniy tanlovlar','yakuniy cta','yakuniy ekspress'):
            if outro is None:outro=Block(title='Yakun',uid='outro',kind='outro',language='uz',sport='combat')
            current=outro;continue
        pair=heading(line)
        if pair and intro is None:index.append(pair);continue
        if pair and current is not outro:
            current=Block(title=pair,language='uz',sport='combat');blocks.append(current);continue
        if current is None or re.fullmatch(r'\d+:\d+\s*[—–-]\s*\d+:\d+',line):continue
        pick=re.match(r'PROGNOZ\s*:\s*(.+)',line,re.I)
        if pick and current.kind=='analysis':current.forecast=pick[1].strip().rstrip('.');continue
        current.script+=('\n' if current.script else '')+line
    if not intro or not blocks:raise ValueError('Нужны KIRISH и заголовки пар бойцов: 1. NAME — NAME.')
    if any(not b.script.strip() for b in blocks):raise ValueError('У заголовка боя отсутствует текст разбора.')
    from .fighters import identity
    pairs={}
    for title in index+[b.title for b in blocks]:pairs[tuple(identity(n) for n in block_teams(title))]=title
    intro.featured_pairs=list(pairs.values())
    return intro,blocks,outro or Block(title='Yakun',uid='outro',kind='outro',language='uz',sport='combat')


def name_position(name,text):
    from .fighters import position
    return position(name,text)


def pair_in(title,text):
    names=block_teams(title);positions=[name_position(n,text) for n in names]
    return bool(names[1]) and all(p is not None for p in positions) and positions[0]!=positions[1]


def classify(text):
    from .combat_cards import classify as select_card
    return select_card(text)


def events(block,matches):
    from .fighters import same_fighter
    sources=[s for s in matches if s.id in block.match_ids and s.sport=='combat']
    names=block_teams(block.title);owner=None;result=[];usage={};aliases={n:[n] for n in names}
    for n in names:
        for line in split_script(block.script):
            for nick,surname in re.findall(r'[“"]([^”"]+)[”"]\s+(\w+)',line):
                if name_position(n,surname) is not None:aliases[n].append(nick)
    lines=[l['text'] for l in block.asr_lines] if block.asr_lines else split_script(block.script)
    for line in lines:
        hits=[n for n in names if any(name_position(alias,line) is not None for alias in aliases[n])]
        if len(hits)==1:owner=hits[0]
        elif len(hits)>1:
            tail=re.split(r'[,;.!?]',line.rstrip(' .!?'))[-1]
            last=[n for n in names if name_position(n,tail) is not None]
            owner=last[0] if len(last)==1 and re.search(r'misol|esa|rekord|statistik|tanish|bazasi',norm(tail)) else None
            continue
        title,_=classify(line);t=norm(line)
        if title=='ПРОГНОЗ' or any(x in t for x in ('telegram','obuna','layk')):continue
        if not owner or not re.search(r'jang|zarba|hujum|himoya|nokaut|masofa|texnik|uslub|almashin|bosim|rekord|tajriba|boks|raund|temp|g.alab|mag.lub|yosh|statistik',t):continue
        eligible=[s for s in sources if same_fighter(s.fighter,owner)]
        if not eligible:
            result.append(EventRequest('',line,'play',note='Нет записи бойца '+owner,requested_teams=[owner]));continue
        source=min(eligible,key=lambda s:usage.get(s.id,0));usage[source.id]=usage.get(source.id,0)+1
        result.append(EventRequest(source.id,line,'play',requested_teams=[owner]))
    return result


def propose_event(event,scans,usage,source=None):
    if event.skipped or (event.selection and event.selection.accepted):return
    from .fighters import same_fighter
    data=scans.get(event.source_id,{})
    choices=sorted(data.get('candidates',[]),key=lambda c:(-c['confidence'],c['time']));used=usage.setdefault(event.source_id,set())
    c=next((c for c in choices if c['id'] not in used),None)
    if not c:event.note='Нет нового боевого фрагмента. Выберите момент вручную или оставьте ведущего.';return
    used.add(c['id'])
    from .combat_scan import DETECTOR_VERSION
    owner=bool(source and len(event.requested_teams)==1 and same_fighter(source.fighter,event.requested_teams[0]) and norm(data.get('fighter',''))==norm(source.fighter))
    accepted=owner and data.get('detector_version')==DETECTOR_VERSION and c.get('kind')=='play' and c['confidence']>=.85
    event.selection=EventSelection(c['id'],c['start'],c['end'],c['time'],data['signature'],accepted,'Архив боя · '+', '.join(event.requested_teams));event.note=c['note']


def active_blocks(project):return [b for b in [project.intro,*project.blocks,project.outro] if b.script.strip()]


def speech_key(project):
    from .uz_speech import recording_key
    return hashlib.sha256(json.dumps(['combat-speech-v4-grounded',recording_key(project),project.recording_times,[(b.uid,b.title,b.script,b.forecast,b.featured_pairs) for b in active_blocks(project)]],ensure_ascii=False).encode()).hexdigest()


def spoken_segments(segments):
    """Break long ASR paragraphs on real timed punctuation, not script rows."""
    result=[]
    for s in segments:
        chunk=[]
        for w in s.get('words',[]):
            chunk.append(w)
            length=w['end']-chunk[0]['start']
            if (length>=2 and re.search(r'[.!?]$',w['word'].strip())) or (length>=7 and re.search(r'[,;]$',w['word'].strip())):
                result.append(dict(start=chunk[0]['start'],end=chunk[-1]['end'],text=' '.join(v['word'] for v in chunk),words=chunk));chunk=[]
        if chunk:result.append(dict(start=chunk[0]['start'],end=chunk[-1]['end'],text=' '.join(v['word'] for v in chunk),words=chunk))
    return result


def intro_annotations(project,segments,lo,hi):
    from .fighters import normalized,identity
    words=[]
    for segment in segments:
        for w in segment.get('words',[]):
            if w['start']>=lo and w['end']<=hi:
                words.extend(dict(word=t,start=w['start'],end=w['end']) for t in normalized(w['word']).split())
    text=' '.join(w['word'] for w in words);found=[];seen=set()
    for title in project.intro.featured_pairs or [b.title for b in project.blocks]:
        key=tuple(identity(n) for n in block_teams(title))
        if key in seen:continue
        positions=[name_position(n,text) for n in block_teams(title)]
        if not all(p is not None for p in positions) or abs(positions[0]-positions[1])>8:continue
        a,z=min(positions),max(positions)
        start=words[max(0,a-1)]['start'];end=words[z]['end']
        if end-start>=.3:found.append((start,end,'РАЗБОР МАТЧА',title));seen.add(key)
    return sorted(found)


def prepare(project,segments,duration):
    from .review import draft_alignment
    from .speech_boundaries import slice_segments,intro_floor
    blocks=active_blocks(project);aligned=copy.deepcopy(blocks)
    heard=norm(' '.join(s.get('text','') for s in segments))
    if segments:
        for b in aligned:
            if b.kind=='analysis':continue
            clean=[]
            for row in split_script(b.script):
                low=norm(row)
                if 'telegram' not in heard and any(x in low for x in ('telegram','havola','tavsif','biriktirilgan izoh')):continue
                if not any(x in heard for x in ('obuna','layk')) and any(x in low for x in ('obuna','layk')):continue
                clean.append(row)
            b.script='\n'.join(clean) or b.script
    rough=draft_alignment(aligned,segments,duration,'Не удалось подтвердить границы боёв. Проверьте переходы.')
    words=[w for s in segments for w in s.get('words',[])];bounds=[0.];reliable=True
    floor=intro_floor(words,'uz') if blocks[0].kind=='intro' else 0.
    for b in blocks[1:]:
        if b.kind=='analysis':choices=[s['start'] for s in segments if s['start']>=max(floor,bounds[-1]+1,rough[b.uid][0][0].start-3)-.01 and pair_in(b.title,s['text'])]
        else:
            from .uz_speech import recap_cue
            choices=[s['start'] for s in segments if s['start']>bounds[-1]+10 and recap_cue(s['text'])]
        if not choices:reliable=False;break
        bounds.append(choices[0]);floor=choices[0]+10
    ranges=list(zip(bounds,bounds[1:]+[duration]))
    if project.recording_times.strip():
        from .recording_times import parse_times
        rows=parse_times(project.recording_times,len(project.blocks),include_outro=bool(project.outro.script.strip()))
        ranges=[(a,z) for a,z,_ in rows]
        if len(ranges)==len(blocks)+1:ranges=ranges[:-2]+[(ranges[-2][0],ranges[-1][1])]
        if len(ranges)!=len(blocks) or ranges[-1][1]>duration+.1:raise ValueError('Проверьте число разделов и границы таймкодов записи.')
        reliable=True;bounds=[a for a,z in ranges]
    if reliable and len(ranges)==len(blocks) and all(z-a>.5 for a,z in ranges):
        recovered={}
        for b,(lo,hi) in zip(aligned,ranges):
            local=copy.deepcopy(slice_segments(segments,lo,hi))
            for s in local:
                s['start']-=lo;s['end']-=lo
                for w in s['words']:w['start']-=lo;w['end']=min(hi,w['end'])-lo
            found=draft_alignment([b],local,hi-lo,'Проверьте слова и тайминг боя.')
            for line in found[b.uid][0]:line.start+=lo;line.end+=lo
            recovered.update(found)
    else:
        reliable=False;recovered=rough
    key=speech_key(project)
    for b in blocks:
        if b.speech_key and b.speech_key!=key:b.events=[]
        lines=recovered[b.uid][0]
        if segments:
            from .uz_speech import make_lines
            from .timeline import Line
            k=blocks.index(b)
            lo,hi=ranges[k] if reliable else (lines[0].start,lines[-1].end)
            annotations=intro_annotations(project,segments,lo,hi) if b.kind=='intro' else []
            spoken,_=make_lines(spoken_segments(segments),lo,hi,annotations)
            if spoken:
                lines=[Line(**dict(row,recognized=row['text'],agreement=0.)) for row in spoken]
                recovered[b.uid]=(lines,[])
        b.asr_lines=[vars(l) for l in lines];b.speech_cards={};b.speech_key=key
        if not reliable:
            for line in b.asr_lines:line['review_reason']='Не подтверждены границы раздела. Проверьте время.'
        for i,line in enumerate(lines):
            title,text=classify(line.text)
            if title=='ПРОГНОЗ' and b.forecast:text=b.forecast
            if title:b.speech_cards[str(i)]={'title':title,'text':text,'needs_review':bool(line.review_reason)}
    return [recovered[b.uid][0][0].start for b in blocks]+[duration]


def synchronize(project,cache,cancel,log):
    from .uz_speech import transcribe
    from .host_media import sources
    from .review import retain_legacy_edits
    from .combat_cards import migrate_project
    migrate_project(project)
    retain_legacy_edits(project);key=speech_key(project)
    if not all(b.speech_key==key and b.asr_lines for b in active_blocks(project)):
        segments=transcribe(project,Path(cache)/'combat-asr-v2',cancel,log)
        prepare(project,segments,sum(p['duration'] for p in sources(project)))
        log('Бои размечены по речи; сомнительные плашки сохранены для проверки.')
    from .goals import GoalScanner,propose
    for b in project.blocks:
        if b.events:continue
        local=[s for s in project.matches if s.id in b.match_ids and s.sport=='combat']
        if not local:continue
        scans={s.id:GoalScanner(cancel=cancel,log=log).scan(s) for s in local}
        b.events=propose(events(b,local),scans,local,False)
        log('Вставки подобраны; неуверенные моменты доступны для проверки: '+b.title)


def framing_cards(project,block,lines,duration):
    from .framing import forecast_text,optional_subscription
    from .media import probe
    from .fighters import identity
    unique={}
    for title in (block.featured_pairs or [b.title for b in project.blocks]):
        unique[tuple(identity(n) for n in block_teams(title))]=title
    cards=[];seen=set()
    for i,line in enumerate(lines):
        t=norm(line.text);heard=norm(line.recognized)
        if block.kind=='intro':
            matches=[]
            for title in unique.values():
                if title not in seen and pair_in(title,line.text):
                    pos=min(name_position(n,line.text) for n in block_teams(title))
                    matches.append((max(0,pos-1),title))
            matches.sort()
            count=max(1,len(re.findall(r'[a-z]+',norm(line.text))))
            for j,(pos,title) in enumerate(matches):
                start=line.start if j==0 else line.start+(line.end-line.start)*pos/count
                end=line.end if j+1==len(matches) else line.start+(line.end-line.start)*matches[j+1][0]/count
                if end-start>=.3:cards.append(Card(start,end,'РАЗБОР МАТЧА',title,i));seen.add(title)
        elif block.kind=='outro':
            # A recap can contain several bets in one ASR sentence.
            from .fighters import identity
            claims=[]
            for match in re.finditer(r"[gq]'?alab\w*",t):
                prefix=t[:match.start()];near=' '.join(prefix.split()[-5:]);candidates=[]
                for owner in project.blocks:
                    for name in block_teams(owner.title):
                        first=identity(name).split()[0] if identity(name) else ''
                        pos=name_position(name,near)
                        first_hits=[j for j,w in enumerate(re.findall(r'[a-z]+',near)) if w==first]
                        if pos is not None or first_hits:candidates.append((max([pos if pos is not None else -1]+first_hits),owner))
                if not candidates:continue
                best=max(v[0] for v in candidates);owners={b.uid:b for score,b in candidates if score==best}
                if len(owners)!=1:continue
                owner=next(iter(owners.values()))
                if owner.uid in seen:continue
                text=forecast_text(owner)
                if text:claims.append((max(0,len(prefix.split())-4),owner,text));seen.add(owner.uid)
            count=max(1,len(t.split()))
            for j,(pos,owner,text) in enumerate(claims):
                start=line.start if j==0 else line.start+(line.end-line.start)*pos/count
                end=line.end if j+1==len(claims) else line.start+(line.end-line.start)*claims[j+1][0]/count
                cards.append(Card(start,end,'ПРОГНОЗ',text,i,forecast_id=owner.uid))
        if 'telegram' in heard and project.assets.get('telegram'):cards.append(Card(line.start,line.end,'ТЕЛЕГРАМ','Telegram',i,project.assets['telegram']))
        if ('obuna' in heard or 'layk' in heard) and project.assets.get('subscribe'):
            asset=project.assets['subscribe'];cards.append(Card(line.start,line.start+probe(asset)['duration'],'ПОДПИСКА','Obuna bo‘ling',i,asset))
    if block.kind=='outro':
        for b in project.blocks:
            text=forecast_text(b)
            if b.uid not in seen and text:cards.append(Card(max(0,duration-4),duration,'ПРОГНОЗ',text,forecast_id=b.uid,review_reason='Повтор ставки не найден. Проверьте время.'))
    for c in cards:
        if str(c.line) in block.card_overrides and not c.asset:c.text=block.card_overrides[str(c.line)]
    return optional_subscription([c for c in cards if c.text.strip()],duration)


def recover_gaps(model,audio,segments,cancel,log):
    import wave
    import numpy as np
    from .media import Cancelled
    if not segments:return segments
    with wave.open(str(audio),'rb') as wav:
        rate=wav.getframerate();samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)/32768
    duration=len(samples)/rate;cursor=0.;gaps=[]
    for s in sorted(segments,key=lambda s:s['start']):
        if s['start']-cursor>=6:gaps.append((cursor,s['start']))
        cursor=max(cursor,s['end'])
    if duration-cursor>=6:gaps.append((cursor,duration))
    result=list(segments);budget=180.
    for lo,hi in gaps:
        if hi-lo>90 or hi-lo>budget:continue
        signal=samples[int(lo*rate):int(hi*rate)]
        if not len(signal) or float(np.sqrt(np.mean(signal*signal)))<.006:continue
        budget-=hi-lo
        for a in np.arange(lo,hi,28.):
            if cancel.is_set():raise Cancelled('Отменено.')
            end=min(hi,float(a)+28);start=max(0,float(a)-.5)
            log(f'Повторно проверяю пропуск речи {a:.1f}–{end:.1f} с…')
            found,_=model.transcribe(samples[int(start*rate):int(min(duration,end+.5)*rate)],language='uz',word_timestamps=True,beam_size=5,vad_filter=False,condition_on_previous_text=False)
            for s in found:
                if cancel.is_set():raise Cancelled('Отменено.')
                words=[dict(word=w.word,start=max(float(a),start+w.start),end=min(end,start+w.end)) for w in s.words if float(a)<=start+w.start<end and w.end>w.start]
                words=[w for w in words if w['end']>w['start']]
                if words:result.append(dict(start=words[0]['start'],end=words[-1]['end'],text=' '.join(w['word'] for w in words),words=words))
    return sorted(result,key=lambda s:s['start'])
