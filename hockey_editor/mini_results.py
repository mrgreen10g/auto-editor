"""Completed exports and durable Drive checkpoints; only registered MP4s are served."""
import copy,secrets,threading,time
from pathlib import Path
from .mini_server import RemoteError
from . import drive_upload as drive

class Results:
    def __init__(self,bridge):
        self.bridge=bridge;self.lock=threading.RLock();self.worker=None;self.cancel=threading.Event();self.active=None
    def file(self):
        return Path(self.bridge.app.cache_path())/'mobile-results.json'
    def records(self,path=None):
        value=drive.read(path or self.file())
        return value if isinstance(value,list) else []
    def register(self,path,job=None):
        path=Path(path).resolve()
        if not path.is_file() or path.suffix.lower()!='.mp4':return
        identity=[path.stat().st_size,path.stat().st_mtime_ns]
        with self.lock:
            journal=Path(job['result_journal']) if job and job.get('result_journal') else self.file()
            rows=self.records(journal)
            old=next((r for r in rows if r['path']==str(path) and r['identity']==identity),None)
            if old:return old
            app=self.bridge.app
            from .episode_identity import title,scope
            row=dict(id=secrets.token_hex(16),path=str(path),name=path.name,identity=identity,created=time.time(),
                     profile=job.get('profile',app.project.profile) if job else app.project.profile,duration=app.plan.duration if app.plan else None,upload=None)
            row.update(title=title(app.project),notification_scope=scope(app.project))
            rows.append(row);drive.write(journal,rows)
        if job and job.get('drive_folder'):
            try:self.start({'id':row['id'],'folder':job['drive_folder']},journal=journal)
            except Exception:
                with self.lock:
                    rows=self.records(journal)
                    for r in rows:
                        if r['id']==row['id']:r['upload']=dict(status='error',message='Автоотправка не началась. Нажмите «Отправить на Google Диск».',progress=0,folder=job['drive_folder'])
                    drive.write(journal,rows)
        return row
    def find(self,ident,journal=None):
        row=next((r for r in self.records(journal) if r['id']==ident),None)
        if not row:raise RemoteError('Готовое видео не найдено.',404)
        path=Path(row['path'])
        if not path.is_file() or [path.stat().st_size,path.stat().st_mtime_ns]!=row['identity']:
            raise RemoteError('Готовый файл перемещён или изменён на сервере.',409)
        return row
    def status(self):
        with self.lock:
            rows=copy.deepcopy(self.records())
            public=[]
            for row in reversed(rows[-30:]):
                upload=row.get('upload')
                if upload:
                    upload={k:upload.get(k) for k in ('status','message','progress','uploaded','folder','folder_name','url')}
                    if upload['status']=='uploading' and (not self.worker or not self.worker.is_alive() or self.active!=(str(self.file()),row['id'])):
                        upload.update(status='paused',message='Отправка прервана. Можно продолжить.')
                path=Path(row['path']);available=path.is_file() and [path.stat().st_size,path.stat().st_mtime_ns]==row['identity']
                public.append({k:row.get(k) for k in ('id','name','title','duration','profile','created')}|dict(size=row['identity'][0],available=available,upload=upload))
            return dict(results=public,drive=drive.public_config(),upload_busy=bool(self.worker and self.worker.is_alive()))
    def media(self,data):
        with self.lock:row=self.find(data.get('id'))
        return dict(file=row['path'],identity=row['identity'])
    def start(self,data,journal=None):
        journal=Path(journal or self.file())
        with self.lock:
            row=self.find(data.get('id'),journal)
            folder=drive.folder_id(data.get('folder',''))
            if not folder:raise RemoteError('Выберите папку Google Диска.')
            if not drive.public_config()['connected']:raise RemoteError('Подключите Google Диск в настройках редактора на сервере.')
            previous=row.get('upload') or {}
            if previous.get('folder')==folder and previous.get('status')=='completed':return dict(ok=True)
            if self.worker and self.worker.is_alive():
                if self.active==(str(journal),row['id']):return dict(ok=True)
                raise RemoteError('Дождитесь отправки предыдущего видео.',409)
            job=copy.deepcopy(previous) if previous.get('folder')==folder and previous.get('file_id') else {}
            job.update(path=row['path'],identity=row['identity'],folder=folder,status='uploading',message='Подключаюсь к Google Диску',progress=job.get('progress',0))
            self.cancel.clear();self.active=(str(journal),row['id'])
            def save(value):
                with self.lock:
                    rows=self.records(journal)
                    next(r for r in rows if r['id']==row['id'])['upload']=copy.deepcopy(value)
                    drive.write(journal,rows)
            save(job)
            def work():
                try:drive.upload(job,save,self.cancel)
                except InterruptedError:job.update(status='paused',message='Отправка приостановлена. Можно продолжить.');save(job)
                except Exception as error:
                    # Network exceptions may contain resumable URLs. Never expose them.
                    message=str(error) if isinstance(error,ValueError) else 'Связь с Google Диском прервалась. Проверьте подключение и продолжите отправку.'
                    if type(error).__name__=='RefreshError':message='Google-авторизация истекла или отозвана. Подключите аккаунт повторно в настройках редактора и продолжите отправку.'
                    job.update(status='error',message=message);save(job)
                finally:
                    if job.get('status')=='completed':
                        notifier=getattr(self.bridge.app,'notifier',None)
                        if notifier and hasattr(notifier,'emit'):
                            notifier.emit(row['id']+'-drive-'+folder,'render',(row.get('title') or row['name'])+'\nВидео загружено на Google Диск.\n'+job.get('url',''),scope=row.get('notification_scope'))
            self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
        return dict(ok=True)
    def pause(self,data):
        with self.lock:
            if self.active!=(str(self.file()),data.get('id')):raise RemoteError('Эта отправка не выполняется.',409)
            self.cancel.set()
        return dict(ok=True)

