"""One ordered presenter list and one optional continuous microphone recording."""
from pathlib import Path
from .mini_server import RemoteError

def update(inputs,data):
    from .mini_export import folder
    from .media import probe
    from .folder_import import VIDEO
    from .mobile_sources import ready
    hosts=data.get('hosts',[]);mic=str(data.get('microphone',''))
    if not isinstance(hosts,list) or any(not isinstance(p,str) for p in hosts):raise RemoteError('Проверьте части ведущего.')
    paths=[str(Path(p).resolve()) for p in hosts if p]
    if len(paths)!=len(set(paths)):raise RemoteError('Одна запись выбрана дважды.')
    for path,role in [(p,'host') for p in paths]+([(mic,'mic')] if mic else []):
        p=Path(path);folder(str(p.parent))
        if not p.is_file() or p.is_symlink() or p.suffix.lower() not in (set(VIDEO)|{'.mp3','.wav','.m4a','.aac','.flac'} if role=='mic' else VIDEO):raise RemoteError('Выберите существующий медиафайл.')
        info=probe(p)
        if not info.get('audio') or (role=='host' and not info.get('video')):raise RemoteError('В записи не найдена нужная дорожка звука или видео.')
    if mic and str(Path(mic).resolve()) in paths:raise RemoteError('Микрофон должен быть отдельной записью.')
    with inputs.lock:
        d=inputs.load(data['id']);inputs.mutable(d)
        if inputs.active and inputs.active[0]==d['id']:raise RemoteError('Дождитесь завершения передачи файла.')
        for row in d['files']:
            if row['role']=='host' and row['status']=='ready' and str(Path(row['path']).resolve()) not in paths:row['status']='removed'
        for p in paths:ready(inputs,d,p,'host',explicit=True)
        ordered=[next(r for r in d['files'] if r['role']=='host' and r['status']=='ready' and Path(r['path']).resolve()==Path(p)) for p in paths]
        d['files']=[r for r in d['files'] if r not in ordered]+ordered
        for row in d['files']:
            if row['role']=='mic' and row['status']=='ready' and not (mic and row.get('block')=='*' and Path(row['path']).resolve()==Path(mic).resolve()):row['status']='removed'
        if mic:ready(inputs,d,mic,'mic','*',explicit=True)
        inputs.save(d)
    return dict(ok=True)
