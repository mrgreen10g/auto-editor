"""Persistent mobile drafts. Only authenticated owners can select server folders."""
import copy,hashlib,re,secrets,shutil,threading,time
from pathlib import Path
from dataclasses import asdict
from .mini_server import RemoteError
from . import drive_upload as storage

CHUNK=2*1024*1024
MAX_VIDEO=50*1024**3

def name(value):
    value=str(value).strip()
    if not value or len(value)>100 or re.search(r'[<>:"/\\|?*\x00-\x1f]',value) or value.endswith(('.', ' ')) or value in ('.','..') or value.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise RemoteError('Введите название без символов <>:"/\\|?* и без точки в конце.')
    return value

class Inputs:
    def __init__(self,bridge,index=None):
        from .preferences import location
        self.bridge=bridge;self.index=Path(index or location().with_name('mobile-drafts.json'))
        self.lock=threading.RLock();self.worker=None;self.cancel=threading.Event();self.active=None
    def catalog(self):
        data=storage.read(self.index)
        return data if isinstance(data,list) else []
    def load(self,ident):
        entry=next((x for x in self.catalog() if x['id']==ident),None)
        if not entry:raise RemoteError('Черновик не найден.',404)
        path=Path(entry['folder'])/'mobile-draft.json';draft=storage.read(path)
        if not draft or draft.get('id')!=ident:raise RemoteError('Папка черновика перемещена или недоступна.',409)
        return draft
    def save(self,draft):storage.write(Path(draft['folder'])/'mobile-draft.json',draft)
    def mutable(self,draft):
        if draft.get('project'):raise RemoteError('Проект уже создан. Откройте его для обработки; для нового выпуска создайте новый черновик.',409)
    def status(self,data):
        from .profiles import PROFILES,kit_path
        from .preferences import presets
        from .material_folder import load_kit
        with self.lock:
            draft=copy.deepcopy(self.load(data['id'])) if data.get('id') else None
            if draft:
                for item in draft['files']:
                    if item['status'] in ('downloading','checking') and self.active!=(draft['id'],item['id']):item.update(status='paused',message='Прервано. Продолжите загрузку.')
                    item.pop('remote',None)
                draft['summary']=self.summary(self.load(draft['id']))
            reusable=[]
            for entry in self.catalog():
                try:previous=self.load(entry['id'])
                except RemoteError:continue
                for row in previous['files']:
                    if row['role']=='match' and (row['status']=='ready' or row.get('unassigned')) and row.get('path') and Path(row['path']).is_file():
                        reusable.append(dict(draft=previous['id'],file=row['id'],label=previous['name']+' · '+(row.get('fighter') or row.get('home','')+' — '+row.get('away',''))))
            return dict(draft=draft,drafts=self.catalog(),profiles=PROFILES,presets=list(presets('ru_hockey')),reusable=reusable,
                        kits={p:load_kit(kit_path(p))[0] for rows in PROFILES.values() for p,_ in rows},busy=bool(self.worker and self.worker.is_alive()))
    def mkdir(self,data):
        from .mini_export import folder
        root=folder(data.get('parent',''));target=root/name(data.get('name',''))
        try:target.mkdir()
        except FileExistsError:raise RemoteError('Такая папка уже существует. Выберите её или задайте другое название.') from None
        return dict(path=str(target))

    def server_files(self,data):
        from .mini_export import folder
        from .folder_import import root_files
        from .profiles import PROFILES
        profile=data.get('profile')
        if profile not in {p for rows in PROFILES.values() for p,_ in rows}:raise RemoteError('Выберите шаблон.')
        root=folder(data.get('folder',''))
        target=root/'shorts' if profile.endswith('_shorts') else root
        if profile.endswith('_shorts'):
            choices=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name.casefold()=='shorts']
            if len(choices)>1:raise RemoteError('Выберите единственную папку shorts.')
            if choices:target=choices[0]
        if target.is_symlink():raise RemoteError('Выберите обычную папку материалов, не символическую ссылку.')
        hosts,scripts=root_files(target) if target.is_dir() else ([],[])
        return dict(hosts=[str(p) for p in hosts],scripts=[str(p) for p in scripts],target=str(target))

    def server_import(self,data):
        from .mini_export import folder
        from .mobile_sources import ready,reconcile,update_hints
        from .mobile_reparse import parse,reopen,reconcile_files
        from .script_input import read_script
        found=self.server_files(data);root=folder(data['folder']);target=Path(found['target'])
        host=str(data.get('host',''));script=str(data.get('script',''))
        if host and host not in found['hosts']:raise ValueError('Выберите запись ведущего из списка файлов.')
        if script and script not in found['scripts']:raise ValueError('Выберите сценарий из списка файлов.')
        with self.lock:
            previous=next((r for r in self.catalog() if Path(r['folder'])==target and r['profile']==data['profile']),None)
            if data.get('id'):
                old=self.load(data['id'])
                if old['profile']!=data['profile']:raise RemoteError('Шаблон папки должен совпадать с текущим черновиком.')
                previous=next(r for r in self.catalog() if r['id']==old['id'])
            else:old=self.load(previous['id']) if previous else None
            if old and not data.get('refresh'):return dict(id=old['id'],count=len(old['blocks']),updated=old.get('script_updated',0),refreshed=False)
            if old and self.active and self.active[0]==old['id']:raise RemoteError('Дождитесь загрузки материалов.',409)
            if not old and (target/'mobile-draft.json').exists():raise RemoteError('В папке уже есть черновик другого выпуска.')
            d=copy.deepcopy(old) if old else dict(id=secrets.token_hex(16),name=target.name,folder=str(target),profile=data['profile'],preset=str(data.get('preset','')),asset_folder='',script='',blocks=[],files=[],created=time.time(),project='',import_notes=[])
            from .mobile_sources import roots
            d['server_roots']=[str(p) for p in roots(d)]+[str(root)]
            update_hints(d);reopen(d)
            if script:
                d=parse(d,read_script(script));reconcile_files(d);d['script_source']=str(Path(script).resolve())
            elif d.get('script'):
                # Refresh hints and discover additional headings from a newly attached root.
                d=parse(d,d['script']);reconcile_files(d)
            d['preset']=str(data.get('preset',d.get('preset','')))
            if host:ready(self,d,host,'host',explicit=True)
            added=reconcile(self,d)
            target=Path(d['folder']);target.mkdir(parents=True,exist_ok=True)
            for section in ('Ведущий','Матчи','Сценарий','Результат'):(target/section).mkdir(exist_ok=True)
            self.save(d)
            if not previous:
                rows=self.catalog();rows.append({k:d[k] for k in ('id','name','folder','profile','created')});storage.write(self.index,rows)
            return dict(id=d['id'],count=len(d['blocks']),updated=d.get('script_updated',time.time()),refreshed=bool(previous),added=added)
    def create(self,data):
        from .profiles import PROFILES
        profile=data.get('profile')
        if profile not in {p for rows in PROFILES.values() for p,_ in rows}:raise RemoteError('Выберите шаблон выпуска.')
        with self.lock:
            request=str(data.get('request',''))
            if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',request):raise RemoteError('Обновите страницу создания выпуска.')
            old=next((r for r in self.catalog() if r.get('request')==request),None)
            if old:return dict(id=old['id'])
            if data.get('folder'):
                from .mini_export import folder
                target=folder(data['folder'])
                existing=next((r for r in self.catalog() if Path(r['folder']).resolve()==target),None)
                if existing:
                    if existing['profile']!=profile:raise RemoteError('В этой папке уже есть выпуск с другим шаблоном. Выберите другую папку.')
                    return dict(id=existing['id'])
                if (target/'mobile-draft.json').exists() or (target/'Выпуск.hockeyproj').exists():raise RemoteError('В папке уже есть проект. Откройте его из истории выпусков.')
            else:target=Path(self.mkdir(data)['path'])
            draft=dict(id=secrets.token_hex(16),name=target.name,folder=str(target),profile=profile,preset=str(data.get('preset','')),asset_folder='',script='',blocks=[],files=[],created=time.time(),project='')
            for p in ('Ведущий','Матчи','Сценарий','Результат'): (target/p).mkdir(exist_ok=True)
            self.save(draft);rows=self.catalog();rows.append({k:draft[k] for k in ('id','name','folder','profile','created')}|{'request':request});storage.write(self.index,rows)
            return dict(id=draft['id'])
    def local(self,data):
        from .mini_export import folder
        from .folder_import import VIDEO
        from .mobile_sources import ready
        p=Path(str(data.get('path',''))).resolve();folder(str(p.parent));role=data.get('role')
        if role not in ('host','match','script') or not p.is_file() or p.is_symlink():raise RemoteError('Выберите существующий файл материала на сервере.')
        if role=='script':
            if p.suffix.lower() not in ('.txt','.docx'):raise RemoteError('Выберите TXT или DOCX.')
            from .script_input import read_script
            result=self.script(dict(id=data['id'],text=read_script(p),reparse=True))
            with self.lock:
                d=self.load(data['id']);d['script_source']=str(p);self.save(d)
            return result
        if p.suffix.lower() not in VIDEO:raise RemoteError('Выберите видеозапись.')
        from .media import probe
        info=probe(p)
        if not info.get('video') or info.get('duration',0)<=0 or role=='host' and not info.get('audio'):raise RemoteError('Проверьте видео; у ведущего должна быть звуковая дорожка.')
        with self.lock:
            d=self.load(data['id']);self.mutable(d)
            added=ready(self,d,p,role,str(data.get('block','')),str(data.get('home','')),str(data.get('away','')),str(data.get('fighter','')),explicit=True)
            self.save(d);return dict(ok=True,added=added)

    def script(self,data):
        from .mobile_reparse import refresh_script
        return refresh_script(self,data)
    def settings(self,data):
        with self.lock:
            d=self.load(data['id']);self.mutable(d)
            for key in ('preset','asset_folder'):d[key]=str(data.get(key,d.get(key,'')))
            titles=data.get('titles')
            if titles is not None:
                if len(titles)!=len(d['blocks']):raise RemoteError('Обновите список разборов.')
                for b,t in zip(d['blocks'],titles):
                    if not str(t).strip() or len(str(t))>200:raise RemoteError('Проверьте названия разборов.')
                    b['title']=str(t).strip()
            self.save(d);return dict(ok=True)
    def new_file(self,d,data):
        self.mutable(d);role=data.get('role')
        if role not in ('host','script','match'):raise RemoteError('Неизвестный тип материала.')
        block=str(data.get('block',''))
        if role=='match' and block not in {b['uid'] for b in d['blocks']}:raise RemoteError('Сначала определите разборы и выберите нужный.')
        if len(d['files'])>=200:raise RemoteError('В черновике слишком много файлов.')
        item=dict(id=secrets.token_hex(16),role=role,block=block,name=str(data.get('name','Видео'))[:100],home=str(data.get('home',''))[:120],away=str(data.get('away',''))[:120],fighter=str(data.get('fighter',''))[:120],status='waiting',message='',received=0,size=0,path='',source='',fingerprint='')
        if role=='match':
            title=next(b['title'] for b in d['blocks'] if b['uid']==block)
            item['subfolder']=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title)[:70].rstrip('. ')+' · '+block[:6]
        d['files'].append(item);return item
    def item(self,d,ident):
        row=next((r for r in d['files'] if r['id']==ident and r['status']!='removed'),None)
        if not row:raise RemoteError('Материал не найден.',404)
        return row
    def path(self,d,item,partial=False):
        section={'host':'Ведущий','match':'Матчи','script':'Сценарий'}[item['role']]
        root=Path(d['folder'])/section
        if item['role']=='match':root=root/item.get('subfolder',item['block'])
        root.mkdir(parents=True,exist_ok=True)
        ext=Path(item['name']).suffix.lower()
        if ext not in ('.mp4','.mov','.mkv','.webm','.m4v','.txt','.docx'):ext='.mp4'
        return root/(('.partial-' if partial else '')+item['id']+ext)
    def upload_init(self,data):
        with self.lock:
            d=self.load(data['id']);self.mutable(d);size=int(data.get('size',0));role=data.get('role');filename=name(data.get('name',''))
            allowed=('.txt','.docx') if role=='script' else ('.mov','.mp4','.m4v','.mkv','.webm')
            if Path(filename).suffix.lower() not in allowed:raise RemoteError('Выберите TXT/DOCX сценарий или MOV/MP4 видео.')
            if not 0<size<=(8*1024**2 if role=='script' else MAX_VIDEO):raise RemoteError('Недопустимый размер файла.')
            fingerprint=str(data.get('fingerprint',''))
            if not re.fullmatch('[a-f0-9]{64}',fingerprint):raise RemoteError('Не удалось проверить выбранный файл.')
            old=next((x for x in d['files'] if x['role']==role and x['block']==str(data.get('block','')) and x['source']=='device' and x['size']==size and x['fingerprint']==fingerprint and x['status']!='removed'),None)
            if old:return dict(file=old['id'],offset=self.path(d,old,True).stat().st_size if self.path(d,old,True).exists() else size if old['status']=='ready' else 0,ready=old['status']=='ready')
            if shutil.disk_usage(d['folder']).free<size+512*1024**2:raise RemoteError('На сервере недостаточно свободного места.')
            item=self.new_file(d,data);item.update(size=size,source='device',fingerprint=fingerprint,status='uploading');self.path(d,item,True).touch(exist_ok=False);self.save(d)
            return dict(file=item['id'],offset=0,ready=False)
    def chunk(self,data,content):
        with self.lock:
            d=self.load(data['id']);self.mutable(d);item=self.item(d,data['file']);offset=int(data['offset'])
            if item['source']!='device' or item['status'] not in ('uploading','error','paused'):raise RemoteError('Загрузка уже завершена или проверяется.',409)
            path=self.path(d,item,True);length=path.stat().st_size
            if not 0<len(content)<=CHUNK or offset<0 or offset+len(content)>item['size']:raise RemoteError('Некорректный блок файла.')
            with path.open('r+b') as out:
                if offset<length:
                    out.seek(offset)
                    if out.read(len(content))!=content:raise RemoteError('Выбран другой файл. Начните новую загрузку.',409)
                elif offset==length:out.seek(offset);out.write(content);out.flush()
                else:raise RemoteError('Повторите загрузку с подтверждённого места.',409)
            item.update(received=path.stat().st_size,status='uploading');self.save(d)
            return dict(offset=item['received'])
    def launch(self,d,item,download=False):
        self.mutable(d)
        if self.worker and self.worker.is_alive():raise RemoteError('Дождитесь текущего скачивания или проверки файла.',409)
        self.active=(d['id'],item['id']);self.cancel.clear();item.update(status='downloading' if download else 'checking',message='Скачивание на сервер' if download else 'Проверка файла');self.save(d)
        def update(**values):
            with self.lock:
                fresh=self.load(d['id']);row=self.item(fresh,item['id']);row.update(values);self.save(fresh);item.update(values)
        def work():
            try:
                partial=self.path(d,item,True)
                final=self.path(d,item)
                recovered=not partial.exists() and final.is_file()
                if recovered:partial=final
                if download and not recovered:
                    from .mobile_downloads import download as fetch
                    fetch(item,partial,update,self.cancel)
                if self.cancel.is_set():raise InterruptedError()
                if item['role']=='script':
                    from .script_input import read_script
                    # The parser dispatches on extension, so validate a named final file.
                    text=read_script(partial);self.script({'id':d['id'],'text':text})
                    final=self.path(d,item)
                    if partial!=final:partial.replace(final)
                else:
                    from .media import probe
                    info=probe(partial)
                    if not info.get('video') or info.get('duration',0)<=0:raise ValueError('В файле не найдено видео.')
                    if item['role']=='host' and not info.get('audio'):raise ValueError('В записи ведущего нет звуковой дорожки.')
                    final=self.path(d,item)
                    if partial!=final:partial.replace(final)
                update(status='ready',message='Готово',path=str(final),received=final.stat().st_size,size=final.stat().st_size)
            except InterruptedError:update(status='paused',message='Остановлено. Можно продолжить.')
            except Exception as e:update(status='error',message=str(e) if isinstance(e,(ValueError,RemoteError)) else 'Не удалось получить файл. Проверьте ссылку, доступ и свободное место; повторите загрузку.')
            finally:self.active=None
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
        return dict(ok=True)
    def finish(self,data):
        with self.lock:
            d=self.load(data['id']);item=self.item(d,data['file'])
            if item['status']=='ready':return dict(ok=True)
            if self.active==(d['id'],item['id']):return dict(ok=True)
            path=self.path(d,item,True)
            if not path.exists():path=self.path(d,item)
            if not path.exists() or path.stat().st_size!=item['size']:raise RemoteError('Файл ещё не загружен полностью.')
            return self.launch(d,item)
    def link(self,data):
        from .mobile_downloads import canonical
        source,url=canonical(data.get('url',''))
        with self.lock:
            d=self.load(data['id']);self.mutable(d)
            if data.get('role')=='host' and source!='drive':raise RemoteError('Для ведущего используйте Google Диск или загрузку с устройства.')
            old=next((r for r in d['files'] if r.get('url')==url and r['role']==data.get('role') and r['block']==data.get('block','') and r['status']!='removed'),None)
            if old:
                if old['status']=='ready':return dict(ok=True)
                return self.launch(d,old,True)
            ready=next((r for r in d['files'] if r.get('url')==url and r['role']=='match' and r['status']=='ready'),None)
            if ready and data.get('role')=='match':return self.reuse(dict(id=d['id'],from_draft=d['id'],file=ready['id'],block=data.get('block')))
            if self.worker and self.worker.is_alive():raise RemoteError('Дождитесь скачивания предыдущего файла.',409)
            item=self.new_file(d,data);item.update(source=source,url=url,profile=d['profile'],name=('Ведущий' if item['role']=='host' else 'Запись')+'.mp4')
            return self.launch(d,item,True)
    def edit_file(self,data):
        with self.lock:
            d=self.load(data['id']);self.mutable(d);item=self.item(d,data['file'])
            if data.get('remove'):
                if self.active==(d['id'],item['id']):raise RemoteError('Сначала остановите загрузку.')
                item['status']='removed' # Keep the actual file; never delete user media.
            else:
                for key in ('home','away','fighter'):item[key]=str(data.get(key,item[key]))[:120]
            self.save(d);return dict(ok=True)
    def reuse(self,data):
        with self.lock:
            d=self.load(data['id']);self.mutable(d)
            other=self.load(data['from_draft']);original=next((r for r in other['files'] if r['id']==data['file'] and (r['status']!='removed' or r.get('unassigned'))),None)
            if not original:raise RemoteError('Исходная запись недоступна.')
            if original['role']!='match' or (original['status']!='ready' and not original.get('unassigned')) or not Path(original['path']).is_file():raise RemoteError('Исходная запись недоступна.')
            if any(r['role']=='match' and r['block']==data.get('block') and r.get('path')==original['path'] and r['status']!='removed' for r in d['files']):return dict(ok=True)
            row=self.new_file(d,dict(role='match',block=data.get('block'),name=original['name'],home=original['home'],away=original['away'],fighter=original['fighter']))
            row.update(path=original['path'],size=Path(original['path']).stat().st_size,received=Path(original['path']).stat().st_size,status='ready',source='reuse',message='Используется запись из выпуска «'+other['name']+'». Сохраните его папку.')
            self.save(d);return dict(ok=True)
    def retry(self,data):
        with self.lock:
            d=self.load(data['id']);item=self.item(d,data['file'])
            if item['source']=='device':return self.finish(data)
            return self.launch(d,item,True)
    def summary(self,d):
        files=[r for r in d['files'] if r['status']!='removed'];hosts=[r for r in files if r['role']=='host' and r['status']=='ready'];problems=[]
        if not d['blocks']:problems.append('Добавьте сценарий и определите разборы.')
        if not hosts:problems.append('Добавьте запись ведущего.')
        if any(r['status']!='ready' for r in files):problems.append('Дождитесь загрузок или уберите ненужные материалы.')
        for r in files:
            if r['status']=='ready' and (not r['path'] or not Path(r['path']).is_file()):problems.append('Файл недоступен: '+r['name'])
            if r['role']=='match' and (not r['fighter'] if d['profile'].startswith(('uz_combat','ru_combat')) else not r['home'] or not r['away']):problems.append('Укажите участников записи: '+r['name'])
        counts={b['uid']:sum(r['role']=='match' and r['block']==b['uid'] and r['status']=='ready' for r in files) for b in d['blocks']}
        notes=d.get('import_notes',[])+[b['title']+': записей нет, останется ведущий.' for b in d['blocks'] if not counts[b['uid']]]
        return dict(problems=problems,notes=notes,hosts=[r['name'] for r in hosts],counts=counts,can_create=not problems)
    def activate(self,data):
        from .model import Project,Block,MatchSource
        from .profiles import apply_profile,kit_path
        from .preferences import apply_preset,restore_folder
        from .material_folder import load_kit,candidates
        from .logos import assign
        bridge=self.bridge;app=bridge.app
        bridge.check_revision(data)
        if bridge.locked() or bridge.media_busy:raise RemoteError('Дождитесь обработки и закройте окно правок на ПК.',409)
        with self.lock:
            d=self.load(data['id'])
            if d.get('project'):project=Project.load(d['project']);target=Path(d['project'])
            else:
                summary=self.summary(d)
                if summary['problems']:raise RemoteError('\n'.join(summary['problems']))
                project=Project();apply_profile(project,d['profile']);project.asset_folder,project.assets=load_kit(kit_path(d['profile']));restore_folder(project)
                if d['preset']:apply_preset(project,d['preset'])
                if d['asset_folder']:
                    choices=candidates(d['asset_folder'])
                    if any(len(v)>1 for v in choices.values()):raise RemoteError('В папке несколько файлов одной роли. Оставьте один дисклеймер, Telegram и подписку.')
                    project.asset_folder=d['asset_folder'];project.assets={k:str(v[0]) for k,v in choices.items() if len(v)==1}
                project.intro=Block(**d['intro']);project.outro=Block(**d['outro']);project.blocks=[Block(**b) for b in d['blocks']]
                # Imported drafts carry IDs from their temporary project. Rebuild
                # those links against the source objects created below.
                for block in project.blocks:block.match_ids=[]
                ready=[r for r in d['files'] if r['status']=='ready'];project.hosts=[r['path'] for r in ready if r['role']=='host'];project.host=project.hosts[0]
                project.full_video=True;project.whole_episode=True;project.settings.use_manual_clips=False
                sport='combat' if d['profile'].startswith(('uz_combat','ru_combat')) else 'football' if 'football' in d['profile'] else 'hockey'
                for r in ready:
                    if r['role']!='match':continue
                    m=MatchSource(r['path'],r['fighter'] if sport=='combat' else r['home'],r['away'],sport=sport,fighter=r['fighter']);project.matches.append(m)
                    next(b for b in project.blocks if b.uid==r['block']).match_ids.append(m.id)
                assign(project);target=Path(d['folder'])/d.get('project_target','Выпуск.hockeyproj')
                if target.exists():raise RemoteError('Файл проекта уже существует. Создайте новый черновик.')
                project.save(target);d['project']=str(target);self.save(d)
            bridge.checkpoint()
            app.project=project;app.project_path=str(target);app.index=0;app.scans={};app.legacy_project=False
            app.invalidate();app.refresh();app.restore_plan();app.status.set('Мобильный выпуск открыт. Можно запустить поиск фрагментов.')
            bridge.history=None;bridge.process.job=None;bridge.process.auto_scope=None;bridge.export.job=None
            bridge.export.last_folder=str(Path(d['folder'])/'Результат')
            return dict(ok=True,project=str(target))


