"""Explicit script refresh: reuse canonical parser, retain media, never overwrite a project."""
import copy,secrets,time
from dataclasses import asdict
from pathlib import Path
from .mini_server import RemoteError
from .folder_import import pair_key


def parse(d,text):
    text=str(text)
    if not text.strip() or len(text.encode())>500000:raise RemoteError('Сценарий пустой или больше 500 КБ.')
    from .folder_import import parse_episode
    intro,blocks,outro=parse_episode(text,d['profile'])
    if not blocks:raise RemoteError('Разборы не найдены. Проверьте сценарий и выбранный шаблон.')
    old={}
    for b in d.get('blocks',[]):old.setdefault(pair_key(b['title'],d['profile']),[]).append(b)
    counts={}
    for b in blocks:
        k=pair_key(b.title,d['profile']);counts[k]=counts.get(k,0)+1
    for b in blocks:
        k=pair_key(b.title,d['profile'])
        if k and counts[k]==1 and len(old.get(k,[]))==1:b.uid=old[k][0]['uid']
    result=copy.deepcopy(d);result.update(script=text,intro=asdict(intro),blocks=[asdict(b) for b in blocks],outro=asdict(outro),script_updated=time.time(),import_notes=[])
    return result


def reopen(d):
    if d.get('project'):
        d['previous_project']=d['project'];d['project']=''
        d['project_target']='Выпуск-обновлённый-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.hockeyproj'


def reconcile_files(d):
    ids={b['uid'] for b in d['blocks']};removed=[]
    for row in d['files']:
        if row['role']=='match' and row['status']!='removed' and row['block'] not in ids:
            removed.append(row['name']);row['status']='removed';row['unassigned']=True;row['message']='Разбор отсутствует после обновления сценария; файл сохранён.'
    if removed:d.setdefault('import_notes',[]).append('Не назначены новым разборам (файлы сохранены, можно выбрать повторно): '+', '.join(removed))


def refresh_script(inputs,data,from_file=False):
    with inputs.lock:
        d=inputs.load(data['id'])
        if not data.get('reparse'):
            inputs.mutable(d)
            if any(r['role']=='match' and r['status']!='removed' for r in d['files']):raise RemoteError('Для замены связанного сценария нажмите «Заново определить разборы».')
        if (data.get('reparse') or from_file) and inputs.active and inputs.active[0]==d['id']:raise RemoteError('Дождитесь текущей загрузки материалов.',409)
        if from_file:
            from .script_input import read_script
            path=Path(d.get('script_source') or Path(d['folder'])/'Сценарий'/'text.txt')
            if not path.is_file():raise RemoteError('Файл сценария недоступен. Вставьте обновлённый текст в поле сценария.')
            text=read_script(path)
        else:text=data.get('text','')
        result=parse(d,text);reopen(result);reconcile_files(result)
        target=Path(d['folder'])/'Сценарий'/'text.txt';target.parent.mkdir(exist_ok=True)
        from . import drive_upload as storage
        # Keep the imported source distinct from the editable working copy.
        if not from_file or not result.get('script_source'):result['script_source']=str(target)
        temporary=target.with_name('text-'+secrets.token_hex(4)+'.tmp');temporary.write_text(str(text),encoding='utf-8');temporary.replace(target)
        inputs.save(result)
        return dict(ok=True,count=len(result['blocks']),updated=result['script_updated'],previous_project=result.get('previous_project',''))
