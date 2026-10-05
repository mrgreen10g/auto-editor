"""Russian hockey / Uzbek football Shorts: compact cards and shared layout."""
import copy
import re
import uuid
from dataclasses import asdict
from pathlib import Path
from .model import Block
from .uzbek import norm

PROFILE='uz_football_shorts'


def parse_script(text,sport="football"):
    """Spoken ordinal introductions are boundaries; hook team names are not."""
    from .script_input import clean_script
    from .team_names import football_identity
    from .uzbek import parse_script as long_script
    if sport=='hockey':
        from .uz_hockey import clean_script,parse_script as long_script
        from .hockey_names import identity as football_identity,display
    text=clean_script(text)
    if re.search(r'^KIRISH\s*$',text,re.M|re.I):return long_script(text)
    rows=[line.strip() for line in text.splitlines() if line.strip()]
    headers=[]
    for i,line in enumerate(rows):
        match=re.match(r"(?:Birinchi|Ikkinchi|Uchinchi|To.rt.inchi|Beshinchi|Keyingi|Oxirgi)\s+(?:o.yin|uchrashuv)\s*[—–:,-]\s*(.+?)[.!]?\s*$",line,re.I)
        if not match and sport=='hockey':
            match=re.match(r"(?:Va|Keyin|Endi)\s+(.+?)[.!]?\s*$",line,re.I)
        if not match:continue
        pair=re.split(r'\s+va\s+|\s+[—–-]\s+',match[1].rstrip('.!'),maxsplit=1,flags=re.I)
        if len(pair)==2 and all(football_identity(n) for n in pair) and football_identity(pair[0])!=football_identity(pair[1]):
            if sport=='hockey':pair=[display(football_identity(n)) for n in pair]
            headers.append((i,' — '.join(pair)))
    if not headers:raise ValueError('Не найдены представления матчей. Например: Birinchi o‘yin — Xorvatiya va Angliya.')
    end=next((i for i in range(headers[-1][0]+1,len(rows)) if re.match(r'^(?:Demak|Xulosa|Yakuniy tanlovlar|Tanlovlarni takror)',rows[i],re.I)),None)
    if end is None:raise ValueError('Не найдены итоги шортса. Отделите их строкой Demak: или YAKUNIY TANLOVLAR.')
    intro=[]
    for line in rows[:headers[0][0]]:
        if re.search(r'SSENARIY|SCENARIO|SHORTS|^\s*\d+\s*[—–-]\s*\d+\s*soniya',line,re.I):continue
        intro.append(line)
    if not intro:raise ValueError('Перед первым разбором не найден текст вступления.')
    blocks=[Block(title=title,script='\n'.join(rows[start:(headers[j+1][0] if j+1<len(headers) else end)]),language='uz',sport='hockey' if sport=='hockey' else '') for j,(start,title) in enumerate(headers)]
    return Block(title='Boshlanish',uid='intro',kind='intro',language='uz',script='\n'.join(intro)),blocks,Block(title='Yakun',uid='outro',kind='outro',language='uz',script='\n'.join(rows[end:]))


def sections(project,segments):
    from .uz_speech import pair_hits,telegram_spans,recap_cue
    from .uz_forecasts import clauses,features
    if project.profile=='uz_hockey_shorts':
        from .hockey_names import pair_in
        pair_hits=lambda title,words:pair_in(title,' '.join(w['word'] for w in words))
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
            if f['ordinal']==index and pair_hits(block.title,window):strong.append(words[i]['start'])
        # A pair as a standalone sentence may omit the ordinal, never a hook statistic.
        for unit in units:
            text=norm(' '.join(w['word'] for w in unit))
            if unit[0]['start']>=floor and len(unit)<=10 and pair_hits(block.title,unit) and not re.search(r'gol|ochko|hisob|yut|mag.lub',text):fallback.append(unit[0]['start'])
        choices=strong or fallback
        if not choices:raise ValueError('Не найдено представление пары в шортсе: '+block.title+'. Укажите таймкоды записи.')
        starts.append(min(choices));floor=starts[-1]+1
    ending=next((unit[0]['start'] for unit in units if unit[0]['start']>starts[-1]+1 and ((recap_cue(' '.join(w['word'] for w in unit)) and not re.search(r'tanlovim|yakuniy.*g.alab',norm(' '.join(w['word'] for w in unit)))) or norm(unit[0]['word']).rstrip(':,.')=='demak')),None)
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
        if re.search(r'telegram|телеграм',norm(block.script)):
            from .timeline import Line
            phrases=[Line(' '.join(w['word'] for w in u),u[0]['start'],u[-1]['end']) for u in units]
            for a,z in promo_line_ranges(phrases):
                start,end=phrases[a].start,phrases[z].end
                overlap=[(x,y) for x,y in local if x<end and y>start]
                if overlap:start=min(start,*(x for x,y in overlap));end=max(end,*(y for x,y in overlap))
                local=[v for v in local if v not in overlap]+[(start,end)]
        result.extend(local)
    return sorted(result)


def finish_cards(project,block,lines,cards,inserts,duration):
    """One text card at a time; bets and the channel promo own their intervals."""
    from .timeline import frame,Card
    ranges=promo_line_ranges(lines)
    for a,z in ranges:
        lo,hi=frame(lines[a].start),frame(min(duration,lines[z].end))
        if hi-lo<.15:continue
        existing=[c for c in cards if c.title=='ТЕЛЕГРАМ' and c.start<hi and c.end>lo]
        for c in existing:cards.remove(c)
        reason='; '.join(dict.fromkeys([l.review_reason for l in lines[a:z+1] if l.review_reason]+[c.review_reason for c in existing if c.review_reason]))
        cards.append(Card(lo,hi,'ТЕЛЕГРАМ','Telegram',a if a==z else -1,review_reason=reason))
    if block.language=='ru':
        cards=[c for c in cards if not (c.title=='РЕЗУЛЬТАТ ВСТРЕЧИ' and 0<=c.line<len(lines) and re.search(r'главный вопрос|пишите.*комментари',lines[c.line].text,re.I))]
        for c in cards:
            if c.title=='РЕЗУЛЬТАТ ВСТРЕЧИ' and 0<=c.line<len(lines) and re.match(r'^результат\b',lines[c.line].text,re.I):c.text=block.title+'\n'+c.text
        for c in number_list_cards(block,lines):
            cards=[old for old in cards if old.title!='СТАТИСТИКА' or old.end<=c.start or old.start>=c.end]
            cards.append(c)
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
    hockey=project.profile=='uz_hockey_shorts'
    if hockey:
        from .hockey_names import identity as football_identity
        from .uz_hockey import events
    sport='hockey' if hockey else 'football'
    if project.profile not in (PROFILE,'uz_hockey_shorts') or not donor.profile.startswith('uz_'+sport):raise ValueError('Выберите лонг того же вида спорта и УЗ спикера.')
    def pair(block):return frozenset(football_identity(n) or norm(n) for n in block_teams(block.title))
    draft=copy.deepcopy(project);total=0;notes=[]
    for block in draft.blocks:
        owners=[b for b in donor.blocks if pair(b)==pair(block)]
        if not owners:notes.append('Не найдена пара в лонге: '+block.title);continue
        ids={m.id:m for m in donor.matches};pool=[];mapping={}
        for owner in owners:
            for event in owner.events:
                s=event.selection;source=ids.get(event.source_id)
                if event.skipped or not s or not s.accepted or not source or source.sport!=sport:continue
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


def parse_ru_script(text):
    """Keep unheaded Shorts as one spoken analysis; never require a recap."""
    from .event_rules import suggested_names,team_position
    from .card_text import teams
    text=re.sub(r'https?://\S+','',text)
    rows=[r.strip() for r in text.splitlines() if r.strip() and not re.match(r'^\s*\[.*\]\s*$',r)]
    headers=[]
    for i,row in enumerate(rows):
        heading=re.sub(r'^\s*(?:матч|пара|разбор)\s*:\s*','',row,flags=re.I)
        pair=re.split(r'\s*[—–]\s*|\s+-\s+',heading.rstrip('.:'),maxsplit=1)
        if len(pair)==2 and all(len(p.split())<=5 and len(suggested_names(p))==1 for p in pair):
            names=[suggested_names(p)[0] for p in pair]
            if names[0]!=names[1]:headers.append((i,' — '.join(names)))
    intro=Block(title='Начало',uid='intro',kind='intro',language='ru')
    outro=Block(title='Завершение',uid='outro',kind='outro',language='ru')
    if headers:
        intro.script='\n'.join(rows[:headers[0][0]])
        blocks=[Block(title=title,script='\n'.join([title,*rows[start+1:(headers[j+1][0] if j+1<len(headers) else len(rows))]]),language='ru') for j,(start,title) in enumerate(headers)]
        return intro,blocks,outro
    # A historical rival mentioned in the hook is not necessarily today's rival.
    # Prefer the bet's team and repeated direct encounters involving that team.
    bet=' '.join(r for r in rows if re.search(r'основной прогноз|мой прогноз|мой выбор|ставка\s*[—:]',r,re.I))
    owners=teams(bet);scores={}
    for row in rows:
        names=list(dict.fromkeys(teams(row)))
        if len(names)!=2:continue
        if owners and not any(team_position(n,bet) is not None for n in names):continue
        weight=1+3*bool(re.search(r'игра\w*\s+с\b|очн|забрасывал\w*',row,re.I))
        key=frozenset(names);scores[key]=scores.get(key,0)+weight
    if not scores:
        names=list(dict.fromkeys(teams('\n'.join(rows))))
        if len(names)==2:scores[frozenset(names)]=1
    # Separate paragraphs can describe today's two teams. Historical results
    # are not evidence that a past rival is today's opponent.
    if len(set(owners))==1:
        owner=owners[0];candidates={}
        for row in rows:
            names=list(dict.fromkeys(teams(row)))
            if len(names)!=1 or names[0]==owner:continue
            if re.search(r'\d+\s*[:：]\s*\d+|вчера|прошл|предыдущ|последн.*(?:игр|матч)|перед поражением',row,re.I):continue
            cue=bool(re.search(r'списывать|недооцен|но\b.*(?:здесь|сегодня)|если\b|соперник|против|в гостях|на выезде',row,re.I))
            candidates[names[0]]=candidates.get(names[0],0)+(4 if cue else 1)
        ranked_teams=sorted(candidates,key=candidates.get,reverse=True)
        if ranked_teams and candidates[ranked_teams[0]]>=4 and (len(ranked_teams)==1 or candidates[ranked_teams[0]]>=candidates[ranked_teams[1]]+3):
            scores[frozenset((owner,ranked_teams[0]))]=max(scores.values(),default=0)+5
    ranked=sorted(scores,key=scores.get,reverse=True)
    if not ranked or (len(ranked)>1 and scores[ranked[0]]==scores[ranked[1]]):
        raise ValueError('Не удалось однозначно определить пару шортса. Добавьте отдельную строку «Команда — Команда» перед разбором.')
    names=sorted(ranked[0],key=lambda n:(n not in owners,team_position(n,'\n'.join(rows)) or 0))
    return intro,[Block(title=' — '.join(names),script='\n'.join(rows),language='ru')],outro


def promo_line_ranges(lines):
    """Use aligned script as well as ASR: Telegram is often mangled by ASR."""
    texts=[norm(l.text+' '+l.recognized) for l in lines]
    ranges=[]
    for i,t in enumerate(texts):
        core=bool(re.search(r'telegram|телеграм|\btg\b|\bтг\b',t))
        # Channel alone also means YouTube; require the link/publication context.
        core=core or bool(re.search(r'kanal',t) and re.search(r'joyla|havola|tavsif|qo.shimcha.*prognoz',t))
        if not core:continue
        a=z=i
        if a and lines[a].start-lines[a-1].end<1.5:
            prev=texts[a-1]
            if re.search(r'aytgancha|qo.shimcha.*prognoz|дополнительн\w*\s+ставк',prev):a-=1
        while z+1<len(lines) and lines[z+1].start-lines[z].end<1.5 and re.search(r'havola|tavsif|ссылк\w*.*описани',texts[z+1]):z+=1
        if ranges and a<=ranges[-1][1]+1:ranges[-1]=(ranges[-1][0],max(z,ranges[-1][1]))
        else:ranges.append((a,z))
    return ranges


def number_list_cards(block,lines):
    """Show a spoken series as one statistic, never number-by-number subtitles."""
    from .card_text import numeric
    from .event_rules import suggested_names
    from .timeline import Card
    output=[]
    for i,line in enumerate(lines[:-2]):
        if not re.search(r'забрасывал|сколько.*(?:гол|шайб)|по матчам',line.text,re.I):continue
        values=[];end=i
        for j in range(i+1,min(i+13,len(lines))):
            value=re.sub(r'^(?:и\s+)?(?:снова\s+)?','',numeric(lines[j].text.lower())).strip(' .,!;')
            if not re.fullmatch(r'\d{1,2}',value):break
            values.append(value);end=j
        if len(values)<3:continue
        names=suggested_names(line.text) or suggested_names(block.title)
        label=(' — '.join(names)+'\n' if names else '')+'Заброшено по матчам'
        output.append(Card(line.start,lines[end].end,'СТАТИСТИКА',label+'\n'+' · '.join(values),i))
    return output


def panel_intervals(plan):
    """Join adjacent game/promo panels so the presenter moves only once."""
    from .timeline import game_transitions
    spans=[(c.start,c.end+tail) for c,tail,_,_ in game_transitions(plan)]
    # Full-screen Telegram does not move the presenter into a split view.
    spans += [(c.start,c.end) for c in plan.cards if c.asset and c.title!='ТЕЛЕГРАМ']
    merged=[]
    for a,b in sorted(spans):
        if merged and a<=merged[-1][1]+.001:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    return merged


def panel_motion(plan,animate=True):
    expressions=[]
    for a,b in panel_intervals(plan):
        edge=min(.35,(b-a)/3)
        if animate:
            expressions.append(f'if(between(t,{a:.6f},{b:.6f}),(1-cos(PI*min(1,min((t-{a:.6f})/{edge:.6f},({b:.6f}-t)/{edge:.6f}))))/2,0)')
        else:expressions.append(f'gte(t,{a:.6f})*lt(t,{b:.6f})')
    return '+'.join(expressions) or '0'
