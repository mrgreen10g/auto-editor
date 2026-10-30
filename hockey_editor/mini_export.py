"""Owner-only local output browsing and render lifecycle on the GUI thread."""
import os,re,secrets,shutil,time
from pathlib import Path
from .mini_server import RemoteError

def folder(value):
    raw=str(value)
    if not raw or raw.startswith(('\\\\','//')) or '\x00' in raw:
        raise RemoteError('Выберите локальную папку сервера.')
    path=Path(raw)
    if not path.is_absolute():raise RemoteError('Нужен полный путь к папке сервера.')
    path=path.resolve()
    if str(path).startswith(('\\\\','//')) or not path.is_dir():raise RemoteError('Папка недоступна.')
    return path

def filename(value):
    name=str(value).strip()
    if not name or len(name)>160 or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.endswith(('.', ' ')):
        raise RemoteError('Укажите имя файла без пути и символов <>:"/\\|?*.')
    if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:
        raise RemoteError('Это имя зарезервировано Windows.')
    return name if name.lower().endswith('.mp4') else name+'.mp4'

class Export:
    def __init__(self,bridge):
        self.bridge=bridge;self.job=None;self.last_folder=''
    def browse(self,data):
        if not data.get('path'):
            roots=[Path(f'{letter}:/') for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] if os.name=='nt' else [Path('/')]
            return dict(path='',parent='',folders=[dict(name=str(p),path=str(p)) for p in roots if p.is_dir()],free=None)
        path=folder(data['path']);offset=max(0,int(data.get('offset',0)))
        try:
            from .folder_import import VIDEO
            suffixes=set(VIDEO)|{'.mp3','.wav','.m4a','.aac','.flac'} if data.get('files')=='mic' else {'.txt','.docx'} if data.get('files')=='script' else VIDEO
            children=sorted((p for p in path.iterdir() if p.is_dir() or (data.get('files') in ('host','match','script','mic') and p.is_file() and not p.is_symlink() and p.suffix.lower() in suffixes)),key=lambda p:(not p.is_dir(),p.name.casefold()))
            free=shutil.disk_usage(path).free
        except OSError:raise RemoteError('Нет доступа к этой папке.') from None
        return dict(path=str(path),parent=str(path.parent) if path.parent!=path else '',free=free,folders=[dict(name=p.name,path=str(p),file=p.is_file()) for p in children[offset:offset+200]],next=offset+200 if offset+200<len(children) else None)
    def status(self):
        app=self.bridge.app
        if self.job and self.job['status'] in ('running','cancelling'):self.job['elapsed']=round(time.time()-self.job['started'])
        from .review import pending
        from .goals import unresolved
        indices=app.selected_indices() if hasattr(app,'selected_indices') else [app.index]
        clips=sum(len(unresolved(app.project.blocks[i])) for i in indices)
        cards=len(pending(app.plan)) if app.plan else 0
        default=self.last_folder or str(Path(app.project_path or app.project.host or Path.home()).resolve().parent)
        return dict(job=self.job,busy=app.busy,locked=self.bridge.locked(),stage=app.status.get(),folder=default,
                    cards=cards,clips=clips,has_plan=app.plan is not None,
                    scope='Весь выпуск' if app.project.whole_episode else app.project.blocks[app.index].title,
                    profile=app.project.profile,revision=self.bridge.revision())
    def start(self,data):
        bridge=self.bridge;app=bridge.app
        # A repeated delivery must never start a second render.
        request=str(data.get('request',''))
        if not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',request):raise RemoteError('Обновите экран рендера.')
        if self.job and self.job['request']==request:return self.status()
        bridge.check_revision(data)
        if bridge.locked() or bridge.media_busy:raise RemoteError('Дождитесь обработки и закройте окно правок на ПК.',409)
        status=self.status()
        if status['cards'] or status['clips']:raise RemoteError('Сначала подтвердите спорные плашки и видео-вставки.',409)
        path=folder(data.get('folder',''));target=path/filename(data.get('name',''))
        for candidate in (target,target.with_suffix('.srt'),target.with_suffix('.timing.json'),target.with_name(target.stem+'.partial.mp4')):
            if candidate.exists():raise RemoteError('Файл с таким именем уже существует. Выберите другое имя.',409)
        try:
            # Probe write permission without touching the requested output.
            test=path/('.auto-editor-'+secrets.token_hex(12)+'.tmp')
            with test.open('xb'):pass
            test.unlink()
        except OSError:raise RemoteError('Нет разрешения на запись в эту папку.') from None
        bridge.checkpoint()
        self.job=dict(id=secrets.token_hex(16),request=request,status='starting',target=str(target),started=time.time(),elapsed=0,progress=None,message='Запуск рендера',error='')
        from .drive_upload import folder_id,public_config
        destination=folder_id(data.get('drive_folder','')) if data.get('drive_upload') is True else ''
        if data.get('drive_upload') is True and (not destination or not public_config()['connected']):
            self.job=None;raise RemoteError('Подключите Google Диск и выберите папку результата.')
        self.job.update(drive_folder=destination,profile=app.project.profile,result_journal=str(bridge.results.file()))
        self.last_folder=str(path)
        try:app.start(True,target=str(target),remote=True)
        except Exception as error:
            self.job.update(status='error',error=str(error),message='Не удалось запустить рендер')
            raise RemoteError(str(error)) from None
        self.job['status']='running';return self.status()
    def cancel(self,data):
        if not self.job or data.get('job')!=self.job['id'] or self.job['status'] not in ('running','cancelling'):
            raise RemoteError('Этот рендер уже не выполняется.',409)
        self.bridge.app.cancel.set();self.job.update(status='cancelling',message='Останавливаем рендер…')
        return self.status()
    def event(self,kind,value):
        job=self.job
        if kind=='result':
            try:self.bridge.results.register(value,job if job and job['status'] in ('running','cancelling') else None)
            except Exception:self.bridge.app.log_lines.append('Видео готово, но не удалось сохранить мобильный список результатов. Проверьте доступ к папке разметки.')
        if not job or job['status'] not in ('running','cancelling'):return
        job['elapsed']=round(time.time()-job['started'])
        if kind=='log':
            job['message']=str(value)
            match=re.search(r'(?:Экспорт|Подготовка ведущего|Кадры): (\d+)%',str(value))
            job['progress']=int(match[1]) if match else None
        elif kind=='result':job.update(status='completed',target=str(value),message='Видео готово',progress=100)
        elif kind=='error':job.update(status='error',error=str(value),message='Рендер остановлен с ошибкой')
        elif kind=='cancelled':job.update(status='cancelled',message='Рендер отменён')
        elif kind in ('review_required','footage_review_required'):job.update(status='review',message='Найдены спорные элементы. Откройте проверку, затем запустите рендер снова.')
        elif kind=='done':job.update(status='error',message='Обработка завершилась без готового видео. Проверьте журнал.')

