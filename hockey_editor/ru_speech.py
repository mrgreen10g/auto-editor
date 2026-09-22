"""Local lexical fallback for continuous Russian episodes; script text is retained."""
import hashlib,json,os,re,urllib.request
from pathlib import Path
from difflib import SequenceMatcher
import numpy as np
from .alignment import AlignmentError,split_script,spoken
from .timeline import Line
from .media import Cancelled,run

MODEL_REPO='Systran/faster-whisper-small'
MODEL_REV='536b0662742c02347bc0e980a01041f333bce120'
DIGESTS={
 'config.json':'b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828',
 'tokenizer.json':'fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab',
 'vocabulary.txt':'34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913',
 'model.bin':'3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671',
}

def model_path(cancel,log):
    folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'Models'/'russian-small'
    folder.mkdir(parents=True,exist_ok=True)
    for name,digest in DIGESTS.items():
        target=folder/name;marker=target.with_suffix(target.suffix+'.sha256')
        if target.is_file() and marker.is_file() and marker.read_text()==digest:continue
        log('Первая настройка запасного распознавания русской речи: ~460 МБ один раз. '+name)
        temp=target.with_suffix(target.suffix+'.part');h=hashlib.sha256();size=0;last=0
        try:
            with urllib.request.urlopen(f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REV}/{name}',timeout=30) as src,temp.open('wb') as out:
                while True:
                    if cancel.is_set():raise Cancelled('Отменено.')
                    data=src.read(1024*1024)
                    if not data:break
                    out.write(data);h.update(data);size+=len(data)
                    if size-last>=25*1024*1024:log(f'Модель русской речи: загружено {size//1024//1024} МБ');last=size
            if h.hexdigest()!=digest:raise ValueError('Проверка модели русской речи не пройдена. Повторите загрузку.')
            temp.replace(target);marker.write_text(digest)
        finally:temp.unlink(missing_ok=True)
    return folder

def recording_key(project):
    from .host_media import identity
    return hashlib.sha256(json.dumps([MODEL_REV,[identity(p) for p in project.host_paths()]]).encode()).hexdigest()

def transcribe(project,cache,cancel,log):
    folder=Path(cache)/'ru-speech';folder.mkdir(parents=True,exist_ok=True)
    saved=folder/(recording_key(project)+'.json')
    if saved.exists():
        log('Использую сохранённое распознавание русской речи.')
        return json.loads(saved.read_text(encoding='utf-8'))
    os.environ['HF_HUB_DISABLE_TELEMETRY']='1';os.environ['DO_NOT_TRACK']='1'
    model_dir=model_path(cancel,log)
    from .host_media import analysis_source
    source,_,_=analysis_source(project,folder,cancel,log)
    audio=folder/'voice.wav';run(['-y','-i',source,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',audio],cancel)
    from faster_whisper import WhisperModel
    model=WhisperModel(str(model_dir),device='cpu',compute_type='int8',cpu_threads=min(4,os.cpu_count() or 2),local_files_only=True)
    result=[]
    log('Распознаю русскую речь на компьютере для проверки порядка частей…')
    try:
        segments,_=model.transcribe(str(audio),language='ru',word_timestamps=True,beam_size=5,vad_filter=False,condition_on_previous_text=False)
        for s in segments:
            if cancel.is_set():raise Cancelled('Отменено.')
            words=[{'word':w.word,'start':w.start,'end':w.end} for w in s.words if w.end>w.start]
            if words:result.append({'text':s.text,'start':words[0]['start'],'end':words[-1]['end'],'words':words})
            log(f'Русская речь: {int(s.end)//60:02}:{int(s.end)%60:02}')
    finally:del model
    # Empty ASR is handled by a fully reviewable script draft, not a lost episode.
    temp=saved.with_suffix('.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(saved)
    return result

def tokens(text):
    text=text.lower().replace('ё','е')
    text=re.sub(r'\bcska\b|\bцск\b','цска',text)
    text=re.sub(r'\b(?:ska|sk)\b','ска',text)
    halves={'одного':'один','одной':'один','двух':'два','трех':'три','четырех':'четыре','пяти':'пять','шести':'шесть','семи':'семь','восьми':'восемь','девяти':'девять'}
    text=re.sub(r'\b('+ '|'.join(halves) +r')\s+с\s+половиной',lambda m:halves[m[1]]+' половина',text)
    text=re.sub(r'\b(\d+)[,.]5\b',lambda m:spoken(m[1])+' половина',text)
    text=spoken(text)
    return [w if len(w)<6 else w[:6] for w in re.findall(r'[а-яa-z]+',text)]

def align_episode(blocks,segments):
    """One monotone mapping for the whole script, not independent phrase searches."""
    from .framing import prepared_script
    from .team_names import normalize
    rows=[];script=[];source=[];stamps=[]
    for block in blocks:
        for index,text in enumerate(split_script(prepared_script(block))):
            ts=tokens(text);lo=len(script);script+=ts
            heading=block.kind=='analysis' and index==0 and normalize(text).strip('. ') == normalize(block.title).strip('. ')
            rows.append((block.uid,text,lo,len(script),heading))
    for segment in segments:
        for w in segment['words']:
            ts=tokens(w['word'])
            for i,token in enumerate(ts):
                source.append(token)
                span=(w['end']-w['start'])/len(ts)
                stamps.append((w['start']+i*span,w['start']+(i+1)*span))
    if not script or not source:raise AlignmentError('Не найден текст или голос для сопоставления выпуска.')
    mapping={}
    for a,b,size in SequenceMatcher(None,script,source,autojunk=False).get_matching_blocks():
        for i in range(size):mapping[a+i]=b+i
    if len(mapping)<.55*len(script):raise AlignmentError('Распознанная речь существенно отличается от полного сценария. Проверьте запись и текст выпуска.')
    keys=sorted(mapping);starts=[stamps[mapping[k]][0] for k in keys]
    result={b.uid:[] for b in blocks};warnings={b.uid:[] for b in blocks};pending=[]
    for uid,text,lo,hi,heading in rows:
        matched=[k for k in range(lo,hi) if k in mapping]
        if heading and len(matched)<max(1,(hi-lo)/2):
            warnings[uid].append('Заголовок разбора не прочитан отдельно; начало взято по первой произнесённой фразе.')
            continue
        coverage=len(matched)/max(1,hi-lo)
        if not matched or (hi-lo>=8 and coverage<.35):
            raise AlignmentError('Не удалось подтвердить фразу по русской речи: «'+text+'». Проверьте эту фразу в сценарии и записи.')
        start=float(np.interp(lo,keys,starts))
        end=stamps[mapping[matched[-1]]][1]
        if hi-lo>=8 and coverage<.7:warnings[uid].append('Проверьте фразу по распознанным словам: '+text)
        pending.append((uid,text,start,end,coverage))
    for i,(uid,text,start,end,coverage) in enumerate(pending):
        if i+1<len(pending):end=pending[i+1][2]
        if end-start<.15:raise AlignmentError('Слишком короткое совпадение фразы: '+text)
        result[uid].append(Line(text,start,end,0. if coverage>=.7 else 1.))
    # Preserve a short spoken sign-off omitted from the written script.
    last=result[blocks[-1].uid][-1] if result[blocks[-1].uid] else None
    if last and blocks[-1].kind=='outro':
        tail=[w for s in segments for w in s['words'] if w['start']>=last.end-.01]
        if tail and tail[-1]['end']-last.end<=2 and tokens(' '.join(w['word'] for w in tail)) in (['пока'],['всем','пока']):
            last.end=tail[-1]['end']
    previous=0
    for block in blocks:
        lines=result[block.uid]
        if not lines:raise AlignmentError('В записи не найден раздел: '+block.title)
        if block.kind=='intro' and (lines[0].start>=120 or lines[-1].end>120):
            raise AlignmentError('Начало не подтверждено в первых двух минутах записи. Проверьте вступление.')
        if lines[0].start<previous-.001:raise AlignmentError('Нарушен порядок разделов: '+block.title)
        previous=lines[-1].end
        warnings[block.uid].insert(0,'Разметка восстановлена по распознанным словам. Текст плашек сохранён из сценария; проверьте предпросмотр.')
    return {uid:(lines,warnings[uid]) for uid,lines in result.items()}

def prepare(project,blocks,cache,cancel,log):
    segments=transcribe(project,cache,cancel,log)
    try:result=align_episode(blocks,segments)
    except AlignmentError as error:
        from .review import draft_alignment
        from .host_media import sources
        duration=sum(p['duration'] for p in sources(project))
        result=draft_alignment(blocks,segments,duration,str(error))
        log('Создана черновая разметка. Сомнительные фразы сохранены для ручной проверки.')
    for b in blocks:
        lines,_=result[b.uid]
        for line in lines:
            line.recognized=' '.join(w['word'].strip() for s in segments for w in s['words'] if line.start<=w['start']<line.end)
            if line.agreement>.8 and not line.review_reason:line.review_reason='Неуверенное совпадение со сценарием.'
            from .review import semantic_conflict
            conflict=semantic_conflict(line.text,line.recognized)
            if conflict:line.review_reason=conflict;line.agreement=1.
        log(f'Подтверждён раздел «{b.title}»: {lines[0].start:.2f}–{lines[-1].end:.2f} с.')
    return result

