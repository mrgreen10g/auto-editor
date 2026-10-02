"""Uzbek football Shorts: spoken structure, compact cards and reusable archives."""
import copy
import re
import uuid
from dataclasses import asdict
from pathlib import Path
from .model import Block
from .uzbek import norm

PROFILE='uz_football_shorts'


def parse_script(text):
    """Spoken ordinal introductions are boundaries; hook team names are not."""
    from .script_input import clean_script
    from .team_names import football_identity
    from .uzbek import parse_script as long_script
    text=clean_script(text)
    if re.search(r'^KIRISH\s*$',text,re.M|re.I):return long_script(text)
    rows=[line.strip() for line in text.splitlines() if line.strip()]
    headers=[]
    for i,line in enumerate(rows):
        match=re.match(r"(?:Birinchi|Ikkinchi|Uchinchi|To.rt.inchi|Beshinchi|Keyingi|Oxirgi)\s+(?:o.yin|uchrashuv)\s*[—–:,-]\s*(.+?)[.!]?\s*$",line,re.I)
        if not match:continue
        pair=re.split(r'\s+va\s+|\s+[—–-]\s+',match[1].rstrip('.!'),maxsplit=1,flags=re.I)
        if len(pair)==2 and all(football_identity(n) for n in pair):headers.append((i,' — '.join(pair)))
    if not headers:raise ValueError('Не найдены представления матчей. Например: Birinchi o‘yin — Xorvatiya va Angliya.')
    end=next((i for i in range(headers[-1][0]+1,len(rows)) if re.match(r'^(?:Demak|Xulosa|Yakuniy tanlovlar|Tanlovlarni takror)',rows[i],re.I)),None)
    if end is None:raise ValueError('Не найдены итоги шортса. Отделите их строкой Demak: или YAKUNIY TANLOVLAR.')
    intro=[]
    for line in rows[:headers[0][0]]:
        if re.search(r'SSENARIY|SCENARIO|SHORTS|^\s*\d+\s*[—–-]\s*\d+\s*soniya',line,re.I):continue
        intro.append(line)
    if not intro:raise ValueError('Перед первым разбором не найден текст вступления.')
    blocks=[Block(title=title,script='\n'.join(rows[start:(headers[j+1][0] if j+1<len(headers) else end)]),language='uz') for j,(start,title) in enumerate(headers)]
    return Block(title='Boshlanish',uid='intro',kind='intro',language='uz',script='\n'.join(intro)),blocks,Block(title='Yakun',uid='outro',kind='outro',language='uz',script='\n'.join(rows[end:]))


def sections(project,segments):
    from .uz_speech import pair_hits,telegram_spans,recap_cue
    from .uz_forecasts import clauses,features
    words=[w for s in segments for w in s['words']]
    if not words:raise ValueError('В шортсе не распознана речь.')
    if project.recording_times.strip():
        from .recording_times import recording_ranges
        ranges=recording_ranges(project,segments)
        return [a for a,b in ranges]+[ranges[-1][1]],telegram_spans(words),words
    units=clauses(segments,words[0]['start'],words[-1]['end']+.01)
    starts=[];floor=words[0]['start']
    for index,block in enumerate(project.blocks):
        strong=[];fallback=[]
        for i in range(len(words)):
            if words[i]['start']<floor:continue
            f=features(words[i]['word'])
            if f['ordinal'] not in (index,-1):continue
            window=words[i:i+15];text=norm(' '.join(w['word'] for w in window[:5]))
            if not re.search(r'o.yin|uchrashuv',text):continue
            if pair_hits(block.title,window):strong.append(words[i]['start'])
        # A pair as a standalone sentence may omit the ordinal, never a hook statistic.
        for unit in units:
            text=norm(' '.join(w['word'] for w in unit))
            if unit[0]['start']>=floor and len(unit)<=10 and pair_hits(block.title,unit) and not re.search(r'gol|ochko|hisob|yut|mag.lub',text):fallback.append(unit[0]['start'])
        choices=strong or fallback
        if not choices:raise ValueError('Не найдено представление пары в шортсе: '+block.title+'. Укажите таймкоды записи.')
        starts.append(min(choices));floor=starts[-1]+1
    ending=next((unit[0]['start'] for unit in units if unit[0]['start']>starts[-1]+1 and (recap_cue(' '.join(w['word'] for w in unit)) or norm(unit[0]['word']).rstrip(':,.')=='demak')),None)
    if ending is None:raise ValueError('Не найдены итоги шортса. Укажите таймкод концовки.')
    bounds=[words[0]['start'],*starts,ending,words[-1]['end']]
    if any(b-a<.15 for a,b in zip(bounds,bounds[1:])):raise ValueError('Границы шортса пересекаются. Проверьте таймкоды.')
    return bounds,telegram_spans(words),words


def promo_spans(project,segments,ranges,detected):
    """Include the spoken promo lead-in, but never absorb the preceding bet."""
    from .uz_forecasts import clauses
    result=[]
    for block,(lo,hi) in zip([project.intro,*project.blocks,project.outro],ranges):
        units=clauses(segments,lo,hi)
        local=[(a,b) for a,b in detected if lo<=a<b<=hi]
        if 'telegram' in norm(block.script):
            for i,unit in enumerate(units):
                t=norm(' '.join(w['word'] for w in unit))
                if 'telegram' not in t:continue
                a,z=unit[0]['start'],unit[-1]['end']
                if i and a-units[i-1][-1]['end']<1.2:
                    prev=norm(' '.join(w['word'] for w in units[i-1]))
                    if ('aytgancha' in prev or 'youtube' in prev) and 'prognoz' in prev:a=units[i-1][0]['start']
                if i+1<len(units) and units[i+1][0]['start']-z<1.2:
                    nxt=norm(' '.join(w['word'] for w in units[i+1]))
                    if re.search(r'havola|tavsif|kirib',nxt):z=units[i+1][-1]['end']
                local=[(x,y) for x,y in local if not x<z or not y>a];local.append((a,z))
        result.extend(local)
    return sorted(result)


def finish_cards(project,block,lines,cards,inserts,duration):
    """One text card at a time; bets and the full-screen promo own their intervals."""
    from .timeline import frame
    for card in cards:
        if card.title=='ТЕЛЕГРАМ':
            card.asset=project.assets.get('telegram','')
            if not card.asset:raise ValueError('Добавьте видео Telegram в материалах шортса.')
        if card.title=='ПРОГНОЗ' and block.kind=='outro':
            owner=next((b for b in project.blocks if b.uid==card.forecast_id),None)
            if owner:card.fixture=owner.title
    priorities={'ТЕЛЕГРАМ':5,'ПРОГНОЗ':4,'РАЗБОР МАТЧА':3,'ПОДПИСКА':2}
    selected=[]
    for card in sorted(cards,key=lambda c:(-priorities.get(c.title,1),c.start)):
        pieces=[(card.start,card.end)]
        for other in selected:
            pieces=[p for a,b in pieces for p in ([(a,b)] if other.start>=b or other.end<=a else [(a,min(b,other.start)),(max(a,other.end),b)]) if p[1]-p[0]>=.15]
        if not pieces:continue
        a,b=max(pieces,key=lambda v:v[1]-v[0])
        if priorities.get(card.title,1)==1 and b-a<.8:continue
        original=card.start;card.start=frame(a);card.end=frame(b)
        if card.asset:card.source_in+=card.start-original
        selected.append(card)
    protected=[c for c in selected if c.title in ('ТЕЛЕГРАМ','ПРОГНОЗ','РАЗБОР МАТЧА')]
    kept=[]
    for clip in inserts:
        pieces=[(clip.start,clip.end)]
        for card in protected:
            pieces=[p for a,b in pieces for p in ([(a,b)] if card.start>=b or card.end<=a else [(a,min(b,card.start)),(max(a,card.end),b)]) if p[1]-p[0]>=.5]
        if not pieces:continue
        a,b=max(pieces,key=lambda v:v[1]-v[0]);clip.source_in+=a-clip.start;clip.start=frame(a);clip.end=frame(b);kept.append(clip)
    return sorted(selected,key=lambda c:c.start),kept


def archive_scans(block,sources):
    from .goals import source_signature
    output={}
    for source in sources:
        try:signature=source_signature(source)
        except OSError:continue
        candidates=[]
        for row in block.archive_pool:
            s=row['selection']
            if row['source_id']!=source.id or not s.get('accepted') or s['source_signature']!=signature:continue
            candidates.append(dict(id=s['candidate_id'],score=None,before=None,time=s['event_time'],start=s['source_start'],end=s['source_end'],confidence=1.,kind='play',note='Проверенный эпизод из лонга.'))
        if candidates:output[source.id]={'signature':signature,'candidates':candidates}
    return output


def import_archives(project,donor):
    """Import accepted source selections, never speech timings or donor edits."""
    from .graphics import block_teams
    from .team_names import football_identity
    from .goals import source_signature,propose
    from .uzbek import events
    if project.profile!=PROFILE or not donor.profile.startswith('uz_football'):raise ValueError('Нужны шортс УЗ футбола и проект футбольного лонга.')
    def pair(block):return frozenset(football_identity(n) or norm(n) for n in block_teams(block.title))
    draft=copy.deepcopy(project);total=0;notes=[]
    for block in draft.blocks:
        owners=[b for b in donor.blocks if pair(b)==pair(block)]
        if not owners:notes.append('Не найдена пара в лонге: '+block.title);continue
        ids={m.id:m for m in donor.matches};pool=[];mapping={}
        for owner in owners:
            for event in owner.events:
                s=event.selection;source=ids.get(event.source_id)
                if event.skipped or not s or not s.accepted or not source or source.sport!='football':continue
                try:
                    if source_signature(source)!=s.source_signature:continue
                except OSError:continue
                if source.id not in mapping:
                    existing=next((m for m in draft.matches if Path(m.path).resolve()==Path(source.path).resolve() and m.home==source.home and m.away==source.away and m.score_box==source.score_box),None)
                    if existing is None:
                        existing=copy.deepcopy(source)
                        if any(m.id==existing.id for m in draft.matches):existing.id=uuid.uuid4().hex[:12]
                        draft.matches.append(existing)
                    mapping[source.id]=existing.id
                ident=mapping[source.id]
                row={'source_id':ident,'selection':asdict(s)}
                if row not in pool:pool.append(row)
                if ident not in block.match_ids:block.match_ids.append(ident)
        for row in pool:
            if row not in block.archive_pool:block.archive_pool.append(row);total+=1
        local=[m for m in draft.matches if m.id in block.match_ids]
        scans=archive_scans(block,local)
        if scans:
            block.events=propose(events(block,local),scans,local,False)
            block.edit_key='';block.speech_key=''
        if not pool:notes.append('Нет доступных подтверждённых эпизодов: '+block.title+'. Проверьте пути и результаты поиска в лонге.')
    draft.team_logos={**donor.team_logos,**draft.team_logos}
    draft.episode_key=''
    project.__dict__.update(draft.__dict__)
    return total,notes
