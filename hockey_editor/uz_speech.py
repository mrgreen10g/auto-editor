"""Local Uzbek ASR and script-guided section detection. Written times are hints."""
import copy, gc, hashlib, json, os, re, urllib.request
from functools import lru_cache
from pathlib import Path
from difflib import SequenceMatcher
from .media import Cancelled, run
from .uzbek import norm
from .graphics import block_teams
from .team_names import football_aliases, football_identity, normalize, compact, CATALOG_VERSION

MODEL_REPO='hostmepanda/whisper-large-v3-turbo-uzbek-ct2'
MODEL_REV='c1122214fcea840e8fab399df10d22ad7c56919f'
TOKENIZER_REV='41f01f3fe87f28c78e2fbf8b568835947dd65ed9'
DIGESTS={'config.json':'0bda718f9243009dfbd4163c1890ff1981c90108fe26c615cd698a49625442ec','preprocessor_config.json':'9322fbdbbb58e826043422e8bb6b23fe7976fde192d655f67547d1afdaead82d','vocabulary.json':'c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1','model.bin':'3e3aa474997013533099d8fe7d3e1c0ed0d64d96c36466c78e0edd7490889ea5','tokenizer.json':'297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd'}

def recording_key(project):
    data=[]
    for name in project.host_paths():
        p=Path(name).resolve();s=p.stat();data.append([str(p),s.st_size,s.st_mtime_ns])
    return hashlib.sha256(json.dumps([MODEL_REV,data]).encode()).hexdigest()

def speech_key(project):
    return hashlib.sha256(json.dumps(['uz-speech-7-spoken-x2',CATALOG_VERSION,recording_key(project),project.recording_times,[(b.uid,b.title,b.script) for b in [project.intro,*project.blocks,project.outro]]],ensure_ascii=False).encode()).hexdigest()

def model_path(cancel,log):
    folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'Models'/'uzbek-turbo'
    folder.mkdir(parents=True,exist_ok=True)
    for name,digest in DIGESTS.items():
        target=folder/name;marker=target.with_suffix(target.suffix+'.sha256')
        if target.exists() and marker.exists() and marker.read_text()==digest:continue
        repo,rev=('openai/whisper-large-v3-turbo',TOKENIZER_REV) if name=='tokenizer.json' else (MODEL_REPO,MODEL_REV)
        log('Первая настройка узбекской речи: модель ~1,6 ГБ. Видео остаётся на компьютере. '+name)
        temp=target.with_suffix(target.suffix+'.part');h=hashlib.sha256();size=0;last=0
        try:
            with urllib.request.urlopen(f'https://huggingface.co/{repo}/resolve/{rev}/{name}',timeout=30) as response,temp.open('wb') as out:
                while True:
                    if cancel.is_set():raise Cancelled('Отменено.')
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    h.update(chunk);out.write(chunk);size+=len(chunk)
                    if size-last>25*1024*1024:log(f'Модель речи: загружено {size//1024//1024} МБ');last=size
            if h.hexdigest()!=digest:raise ValueError('Проверка модели речи не пройдена. Повторите загрузку.')
            temp.replace(target);marker.write_text(digest)
        finally:
            if temp.exists():temp.unlink()
    return folder

def transcribe(project,cache,cancel,log):
    folder=Path(cache)/'uz-speech';folder.mkdir(parents=True,exist_ok=True);saved=folder/(recording_key(project)+'.json')
    if saved.exists():return json.loads(saved.read_text(encoding='utf-8'))
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['DO_NOT_TRACK']='1'
    model_dir=model_path(cancel,log)
    from .host_media import analysis_source
    source,_,_=analysis_source(project,folder,cancel,log)
    audio=folder/'voice.wav';run(['-y','-i',source,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',audio],cancel)
    from faster_whisper import WhisperModel
    log('Распознаю узбекскую речь на компьютере. Это может занять несколько минут…')
    model=WhisperModel(str(model_dir),device='cpu',compute_type='int8',cpu_threads=min(4,os.cpu_count() or 2),local_files_only=True)
    result=[]
    try:
        segments,_=model.transcribe(str(audio),language='uz',word_timestamps=True,beam_size=1,vad_filter=False,condition_on_previous_text=False)
        for s in segments:
            if cancel.is_set():raise Cancelled('Отменено.')
            words=[{'word':w.word,'start':w.start,'end':w.end} for w in s.words if w.end>w.start]
            if not words:continue
            result.append({'start':words[0]['start'],'end':words[-1]['end'],'text':s.text,'words':words})
            log(f'Распознана речь до {int(s.end)//60:02}:{int(s.end)%60:02}')
    finally:del model;gc.collect()
    if not result:raise ValueError('Узбекская речь в записи не распознана.')
    temp=saved.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');temp.replace(saved)
    return result

@lru_cache(maxsize=8192)
def token(text):
    value=compact(text)
    return {'asosuna':'osasuna','padedborn':'paderborn','paddeboron':'paderborn','padiboron':'paderborn','padiborun':'paderborn','maddiboron':'paderborn','padeborn':'paderborn','borussiya':'borussia','borusya':'borussia'}.get(value,value)
@lru_cache(maxsize=32768)
def similar(a,b):
    a=token(a);b=token(b)
    return SequenceMatcher(None,a,b,autojunk=False).ratio() if a and b else 0

def name_hits(name,words,context=()):
    names=[token(v) for v in football_aliases(name,context)];hits=[]
    club=football_identity(name)
    for i in range(len(words)):
        for count in (1,2,3):
            if i+count>len(words):break
            text=''.join(token(w['word']) for w in words[i:i+count])
            # Strip only Uzbek grammatical suffixes, never arbitrary word tails.
            variants=[text]+[text[:-len(s)] for s in ('ning','dan','ga','da','ni','mi') if text.endswith(s)]
            score=max([similar(n,v) if min(len(n),len(v))>=4 else float(n==v)
                       for n in names for v in variants]+[0])
            if club in ('Manchester United','Manchester City','Coventry City'):
                # Shared city/name words must not pass fuzzy matching alone.
                if text in ('manchester','city','siti','united'):score=0
                required={'Manchester United':('united','yunayted','юнайтед'),
                          'Manchester City':('city','siti','сити'),
                          'Coventry City':('coventry','koventri','ковентри')}[club]
                if not any(similar(token(w['word']),v)>=.78 for w in words[i:i+count] for v in required):score=0
                if club=='Manchester City' and i>0 and any(similar(words[i-1]['word'],v)>=.8 for v in ('koventri','coventry','hull','hall')):score=0
            if score>=.74:hits.append((i,i+count-1,score))
    return hits

def pair_hits(title,words):
    a,b=block_teams(title);left=name_hits(a,words,(a,b));right=name_hits(b,words,(a,b))
    choices=[(min(i[0],j[0]),max(i[1],j[1]),i[2]+j[2]) for i in left for j in right if abs(i[0]-j[0])<=8 and (i[1]<j[0] or j[1]<i[0])]
    return [(a,b) for a,b,_ in sorted(choices,key=lambda v:(-v[2],v[0],v[1]-v[0]))]

def telegram_spans(words):
    result=[]
    for i,w in enumerate(words):
        direct=similar(w['word'],'telegram')>=.76
        channel=any(similar(v['word'],'kanalimizda')>=.6 for v in words[i+1:i+4])
        context=norm(' '.join(v['word'] for v in words[max(0,i-9):i+14]))
        # A badly transcribed channel name can still be supported by channel,
        # information and link cues together, never by a generic word alone.
        channel_link=(similar(w['word'],'kanalimizda')>=.6
                      and re.search(r'informats|prognoz|ma.lumot',context)
                      and re.search(r'havola|silqa|silka|tavsif',context))
        if not direct and not(similar(w['word'],'telegram')>=.62 and channel) and not channel_link:continue
        lo=i
        while lo>0 and i-lo<14:
            previous=words[lo-1]
            if words[lo]['start']-previous['end']>.2 or previous['word'].rstrip().endswith(('.','!','?')):break
            lo-=1
        for j in range(lo,i):
            if token(words[j]['word'])=='va' and token(words[j+1]['word']).startswith('shunga'):lo=j
        hi=i
        while hi+1<len(words) and words[hi]['end']-w['start']<14:
            if words[hi]['word'].rstrip().endswith(('.','!','?')):break
            hi+=1
        nxt=norm(' '.join(v['word'] for v in words[hi+1:hi+6]))
        if any(v in nxt for v in ('havola','silka','silqa','sivgay','opisani','tavsif')):
            hi+=1
            while hi+1<len(words) and not words[hi]['word'].rstrip().endswith(('.','!','?')):hi+=1
        span=(words[lo]['start'],words[hi]['end'])
        if not result or span[0]>result[-1][1]:result.append(span)
    return result

def recap_cue(text):
    t=norm(text)
    return bool(re.search(r'qaytar|takror|yakun|xulosa|jaml',t) or
                (re.search(r'eslat',t) and re.search(r'tanlovlar|variantlar',t) and re.search(r'yana|oxir|qisqacha',t)))

def sections(project,segments):
    words=[w for s in segments for w in s['words']];tg=telegram_spans(words);starts=[]
    if project.recording_times.strip():
        from .recording_times import recording_bounds
        return recording_bounds(project,segments),tg,words
    # A clearer repetition in the first analysis must not move the intro floor.
    intro_limit=tg[0][0] if tg and tg[0][0]<60 else 60
    early=[w for w in words if w['start']<intro_limit];floor=0
    for b in project.blocks:
        hits=pair_hits(b.title,early)
        if hits:
            first=min(hits,key=lambda hit:hit[0]);floor=max(floor,early[first[1]]['end'])
    if tg and tg[0][0]<60:floor=max(floor,tg[0][1])
    from .uz_forecasts import features
    for index,b in enumerate(project.blocks):
        def is_start(segment):
            if pair_hits(b.title,segment['words']):return True
            ordinal=features(segment['text'])['ordinal']
            if ordinal==-1:ordinal=len(project.blocks)-1
            return ordinal==index and any(h[2]>=.85 for team in block_teams(b.title) for h in name_hits(team,segment['words']))
        choices=[s['start'] for s in segments if s['start']>=floor-.1 and is_start(s)]
        if not choices:raise ValueError('Не удалось найти начало разбора по речи: '+b.title+'. Проверьте названия и состав блоков.')
        starts.append(choices[0]);floor=starts[-1]+10
    ending=next((s['start'] for s in segments if s['start']>starts[-1]+10 and recap_cue(s['text'])),None)
    if ending is None:raise ValueError('В речи не найден переход к итогам. Таймкоды сценария не использованы.')
    bounds=[words[0]['start'],*starts,ending,words[-1]['end']]
    if any(b-a<3 for a,b in zip(bounds,bounds[1:])):raise ValueError('Неустойчивые границы разделов. Нужна проверка записи.')
    return bounds,tg,words

def bet_cue(text):return bool(re.search(r'tanlo|varia|qildik|qila qold',norm(text)))
def bet_score(text,reference):
    t=norm(text);ref=norm(reference);score=2 if bet_cue(t) else 0
    if re.search(r"go['‘’]?[li]?l|golson|go.son",t) and ('ko‘p' in reference or "ko'p" in ref or 'kam' in ref):score+=2
    if re.search(r'g.alab|alaba|qalaba',t) and 'alab' in ref:score+=2
    if 'x2' in t and 'x2' in ref:score+=5
    return score

def make_lines(segments,lo,hi,annotations):
    boundaries={lo,hi}
    for s in segments:
        if lo<s['start']<hi:boundaries.add(s['start'])
    for a,b,_,_ in annotations:boundaries.update((max(lo,a),min(hi,b)))
    # Do not split authored Telegram overlays on ASR sentence boundaries.
    for a,b,title,_ in annotations:
        boundaries={v for v in boundaries if not a<v<b}
    values=sorted(boundaries);words=[w for s in segments for w in s['words'] if w['end']>lo and w['start']<hi];lines=[];cards={}
    for a,b in zip(values,values[1:]):
        selected=[w for w in words if a<=((w['start']+w['end'])/2)<b]
        if not selected or b-a<.15:continue
        text=' '.join(w['word'].strip() for w in selected)
        annotated=False
        for x,y,title,body in annotations:
            if abs(x-a)<.05 and abs(y-b)<.05:
                cards[str(len(lines))]={'title':title,'text':body};annotated=True
        if not annotated:
            a=max(a,selected[0]['start']);b=min(b,selected[-1]['end'])
            if b-a<.15:continue
        lines.append({'text':text,'start':a,'end':b,'agreement':0.})
    return lines,cards

def prepare(project,segments):
    from .framing import forecast_text
    from .uz_forecasts import match_forecasts
    bounds,tg,words=sections(project,segments);key=speech_key(project)
    ranges=list(zip(bounds,bounds[1:]))
    if project.recording_times.strip():
        from .recording_times import recording_ranges
        ranges=recording_ranges(project,segments)
    picks={b.uid:forecast_text(b) for b in project.blocks}
    if any(not v for v in picks.values()):raise ValueError('Укажите основной прогноз в сценарии каждого разбора: Mening tanlovim — …')
    for index,b in enumerate([project.intro,*project.blocks,project.outro]):
        lo,hi=ranges[index];annotations=[];local=[s for s in segments if lo<=s['start']<hi];forecast_review=[];forecast_owners={}
        if b.kind=='intro':
            subset=[w for w in words if lo<=w['start']<hi]
            matched=[];uncertain=set()
            for owner in project.blocks:
                hits=pair_hits(owner.title,subset)
                if hits:
                    a,z=hits[0];matched.append((subset[a]['start'],subset[z]['end']))
                else:
                    # One clearly spoken team can anchor a known script fixture.
                    teams=block_teams(owner.title)
                    single=[hit for team in teams for hit in name_hits(team,subset) if hit[2]>=.85]
                    if single:
                        a,z,_=max(single,key=lambda hit:hit[2]);matched.append((subset[a]['start'],subset[min(len(subset)-1,z+2)]['end']))
                    else:matched.append(None)
                    uncertain.add(owner.title)
            for j,owner in enumerate(project.blocks):
                span=matched[j]
                if span is None:
                    # Bounded by neighbouring known fixtures; keep the result reviewable.
                    a=next((matched[k][1] for k in range(j-1,-1,-1) if matched[k]),lo)
                    z=next((matched[k][0] for k in range(j+1,len(matched)) if matched[k]),min(hi,tg[0][0] if tg else hi))
                    remaining=sum(matched[k] is None for k in range(j,len(matched)) if all(matched[n] is None for n in range(j,k+1)))
                    span=(a,a+(z-a)/max(1,remaining));matched[j]=span
                a,z=span
                next_start=next((matched[k][0] for k in range(j+1,len(matched)) if matched[k]),hi)
                z=min(z,next_start)
                if z-a>=.15:annotations.append((a,z,'РАЗБОР МАТЧА',owner.title))
        elif b.kind=='analysis':
            s=match_forecasts(segments,lo,hi,[b],picks,recap=False)[0]
            spoken_total=re.search(r'(\d+[,.]\d+)\s*(?:ta)?dan',norm(s['text']))
            reference_total=re.search(r'(\d+[,.]\d+)\s+dan',norm(picks[b.uid]))
            if spoken_total and reference_total and spoken_total[1].replace(',','.')!=reference_total[1].replace(',','.'):
                raise ValueError('Значение ставки в речи отличается от сценария: '+b.title)
            annotations.append((s['start'],s['end'],'ПРОГНОЗ',picks[b.uid]))
            if s['needs_review']:forecast_review.append((s['start'],s['end']))
            for phrase in local:
                if phrase['start']<s['end'] and phrase['end']>s['start']:continue
                t=norm(phrase['text']).replace("go'l",'gol').replace("go'il",'gol')
                if 'ikkita' in t and 'gol' in t and any(v in t for v in ('kamida','shart','kerak')):
                    body='Kamida 2 gol'
                    if re.search(r"ma[g']*lub",t) and 'X2' in picks[b.uid]:
                        body=picks[b.uid].splitlines()[0].replace(' X2',' yutadi yoki durang')+'\n'+body
                    annotations.append((phrase['start'],phrase['end'],'УСЛОВИЯ ПРОГНОЗА',body))
        else:
            recap=match_forecasts(segments,lo,hi,project.blocks,picks)
            for owner,s in zip(project.blocks,recap):
                annotations.append((s['start'],s['end'],'ПРОГНОЗ',picks[owner.uid]))
                forecast_owners[(s['start'],s['end'])]=owner.uid
                if s['needs_review']:forecast_review.append((s['start'],s['end']))
        for a,z in tg:
            if lo<=a<z<=hi:annotations.append((a,z,'ТЕЛЕГРАМ','Telegram'))
        b.asr_lines,b.speech_cards=make_lines(segments,lo,hi,annotations);b.speech_key=key
        for i,card in b.speech_cards.items():
            line=b.asr_lines[int(i)]
            if card['title']=='ПРОГНОЗ' and (line['start'],line['end']) in forecast_review:card['needs_review']=True
        if b.kind=='intro':
            for card in b.speech_cards.values():
                if card['title']=='РАЗБОР МАТЧА' and card['text'] in uncertain:card['needs_review']=True
        if b.kind=='outro':
            for i,card in b.speech_cards.items():
                if card['title']=='ПРОГНОЗ':
                    line=b.asr_lines[int(i)]
                    card['forecast_id']=forecast_owners[(line['start'],line['end'])]
        b.events=[];b.edit_plan=None;b.edit_key=''
    project.episode_plan=None;project.episode_key=''
    return bounds

def synchronize(project,cache,cancel,log):
    key=speech_key(project)
    if not all(b.speech_key==key and b.asr_lines for b in [project.intro,*project.blocks,project.outro]):
        bounds=prepare(project,transcribe(project,cache,cancel,log))
        log('Разделы по речи: '+', '.join(f'{v//60:02.0f}:{v%60:05.2f}' for v in bounds))
        for card in project.intro.speech_cards.values():
            if card.get('needs_review'):log('Проверьте плашку во вступлении: '+card['text']+'. Одно из названий распознано неуверенно; сборка продолжена.')
    from .uzbek import events
    from .goals import GoalScanner,propose
    for b in project.blocks:
        if b.events:continue
        local=[m for m in project.matches if m.id in b.match_ids]
        if not local:log('Нет игровой записи: '+b.title+'. Останется ведущий.');continue
        scans={m.id:GoalScanner(cancel=cancel,log=log).scan(m) for m in local}
        actual=copy.deepcopy(b);actual.script='\n'.join(l['text'] for l in b.asr_lines)
        b.events=propose(events(actual,local),scans,local,False)
