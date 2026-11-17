"""Recover draft metadata without confusing it with the user's media directory."""
import copy,re
from pathlib import Path
from . import drive_upload as storage
from .mini_server import RemoteError

def valid(value):
    return isinstance(value,dict) and bool(re.fullmatch(r'[a-f0-9]{32}',str(value.get('id','')))) and isinstance(value.get('files'),list) and 'profile' in value

def register(inputs,draft):
    rows=[r for r in inputs.catalog() if r['id']!=draft['id'] and Path(r['folder']).resolve()!=Path(draft['folder']).resolve()]
    prior=next((r for r in inputs.catalog() if r['id']==draft['id']),{})
    rows.append({**prior,**{k:draft[k] for k in ('id','name','folder','profile','created')}})
    storage.write(inputs.index,rows)

def backup_path(inputs,ident):
    if not re.fullmatch(r'[a-f0-9]{32}',str(ident)):raise RemoteError('Некорректный идентификатор выпуска.')
    return inputs.index.parent/'mobile-draft-state'/(ident+'.json')

def save(inputs,draft):
    storage.write(Path(draft['folder'])/'mobile-draft.json',draft)
    storage.write(backup_path(inputs,draft['id']),draft)

def load(inputs,ident):
    entry=next((r for r in inputs.catalog() if r['id']==ident),None)
    if not entry:raise RemoteError('Выпуск не найден. Обновите список или выберите его папку.',404)
    folder=Path(entry['folder'])
    if not folder.is_dir():raise RemoteError('Папка материалов недоступна на сервере: '+str(folder),409)
    disk=storage.read(folder/'mobile-draft.json')
    if valid(disk):
        if disk['id']!=ident:
            if disk['profile']!=entry['profile']:raise RemoteError('В папке сохранён другой выпуск. Выберите актуальный выпуск из списка.',409)
            register(inputs,disk)
        return disk
    backup=storage.read(backup_path(inputs,ident))
    if valid(backup) and backup['id']==ident and Path(backup['folder']).resolve()==folder.resolve():
        save(inputs,backup);return backup
    raise RemoteError('Не найден служебный файл состояния выпуска. Видео не удалены. Выберите эту папку в «Материалы из папки сервера» и повторите импорт.',409)

def existing(inputs,target,profile):
    disk=storage.read(target/'mobile-draft.json')
    if valid(disk):
        if disk['profile']!=profile:raise RemoteError('В этой папке уже есть выпуск с другим шаблоном.')
        register(inputs,disk);return disk
    entry=next((r for r in inputs.catalog() if Path(r['folder']).resolve()==target.resolve() and r['profile']==profile),None)
    if entry:
        try:return load(inputs,entry['id'])
        except RemoteError:
            # Explicit re-import can rebuild missing state from source material.
            if (target/'mobile-draft.json').exists():raise
            storage.write(inputs.index,[r for r in inputs.catalog() if r['id']!=entry['id']])
    return None
