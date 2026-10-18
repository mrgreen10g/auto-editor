"""Google Drive credentials and resumable transfers; no Tk calls in workers."""
import base64,hashlib,json,re,threading,uuid
from pathlib import Path
from urllib.parse import urlsplit

SCOPE='https://www.googleapis.com/auth/drive'
API='https://www.googleapis.com/drive/v3'
UPLOAD='https://www.googleapis.com/upload/drive/v3/files'
DESTINATIONS={'ru_long':'РУ · лонг','ru_shorts':'РУ · Shorts','uz_long':'УЗ · лонг','uz_shorts':'УЗ · Shorts'}
LOCK=threading.RLock()

def location():
    from .preferences import location as prefs
    return prefs().with_name('google-drive.json')

def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');temp.replace(path)
    finally:temp.unlink(missing_ok=True)

def secret(value,decode=False):
    from .notifications import protect
    return protect(base64.b64decode(value),True).decode() if decode else base64.b64encode(protect(value.encode())).decode()

def config():
    with LOCK:return read(location())

def destination(profile):
    return ('uz' if profile.startswith('uz_') else 'ru')+('_shorts' if profile.endswith('_shorts') else '_long')

def folder_id(value):
    value=str(value).strip()
    if not value:return ''
    if value.startswith('https://'):
        parsed=urlsplit(value)
        if parsed.hostname!='drive.google.com' or parsed.username or parsed.password:raise ValueError('Нужна ссылка на папку Google Диска.')
        match=re.fullmatch(r'/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)',parsed.path.rstrip('/'))
        if not match:raise ValueError('Скопируйте ссылку именно на папку Google Диска.')
        value=match[1]
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}',value):raise ValueError('Некорректная ссылка или ID папки Google Диска.')
    return value

def public_config():
    c=config()
    return dict(connected=bool(c.get('credentials')),account=c.get('account',''),auto=bool(c.get('auto')),
                folders={k:c.get('folders',{}).get(k,'') for k in DESTINATIONS},labels=DESTINATIONS)

def save_config(data):
    folders={k:folder_id(data.get('folders',{}).get(k,'')) for k in DESTINATIONS}
    if not isinstance(data.get('auto',False),bool):raise ValueError('Некорректная настройка отправки.')
    with LOCK:
        c=config();c.update(folders=folders,auto=data.get('auto',False));write(location(),c)
    return public_config()

def connect(client_file):
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import AuthorizedSession
    raw=read(client_file).get('installed')
    if not raw or not raw.get('client_id','').endswith('.apps.googleusercontent.com'):
        raise ValueError('Выберите OAuth JSON типа Desktop app из Google Cloud.')
    # Pin endpoints even if the selected JSON contains unrelated URLs.
    raw={k:raw[k] for k in ('client_id','client_secret')}
    raw.update(auth_uri='https://accounts.google.com/o/oauth2/auth',token_uri='https://oauth2.googleapis.com/token')
    flow=InstalledAppFlow.from_client_config({'installed':raw},[SCOPE],autogenerate_code_verifier=True)
    credentials=flow.run_local_server(host='127.0.0.1',port=0,timeout_seconds=180,
        authorization_prompt_message='',success_message='Google Drive connected. You can close this tab.',prompt='consent')
    if not credentials.refresh_token:raise ValueError('Google не выдал разрешение для фоновой работы. Подключите аккаунт повторно.')
    with AuthorizedSession(credentials) as session:
        response=session.get(API+'/about',params={'fields':'user(emailAddress)'},timeout=30)
        check(response);account=response.json()['user']['emailAddress']
    with LOCK:
        c=config();key=c.get('account_key') if c.get('account')==account else None
        c.update(credentials=secret(credentials.to_json()),account=account,account_key=key or uuid.uuid4().hex);write(location(),c)
    return account

def session():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession
    c=config()
    if not c.get('credentials'):raise ValueError('Подключите Google Диск в настройках редактора на сервере.')
    credentials=Credentials.from_authorized_user_info(json.loads(secret(c['credentials'],True)),[SCOPE])
    return AuthorizedSession(credentials),c.get('account_key','')

def check(response):
    if 200<=response.status_code<300:return
    messages={401:'Подключите Google-аккаунт повторно.',403:'Нет доступа, превышена квота или не включён Google Drive API.',404:'Файл или папка недоступны.',429:'Google ограничил запросы. Продолжите отправку позже.'}
    raise ValueError('Google Диск: HTTP '+str(response.status_code)+'. '+messages.get(response.status_code,'Передача прервана. Нажмите «Продолжить отправку».'))

def upload(job,save,cancel,session_factory=session):
    """save persists each checkpoint before the next network mutation."""
    path=Path(job['path']);stat=path.stat()
    if [stat.st_size,stat.st_mtime_ns]!=job['identity']:raise ValueError('Готовый файл изменился. Создайте новый рендер.')
    client,account_key=session_factory()
    try:
        if job.get('account_key') and job['account_key']!=account_key:raise ValueError('Для продолжения нужен тот же Google-аккаунт, с которого начата отправка.')
        job['account_key']=account_key
        def request(method,url,**kw):
            if cancel.is_set():raise InterruptedError('Отправка приостановлена.')
            return client.request(method,url,timeout=60,allow_redirects=False,**kw)
        def metadata():
            return request('GET',API+'/files/'+job['file_id'],params={'fields':'id,size,md5Checksum,webViewLink','supportsAllDrives':'true'})
        def finish(response):
            check(response);value=response.json()
            if str(value.get('size'))!=str(stat.st_size) or value.get('md5Checksum')!=job['md5']:
                raise ValueError('Google ещё не подтвердил целостность файла. Продолжите проверку отправки.')
            job.update(status='completed',progress=100,uploaded=stat.st_size,url='https://drive.google.com/file/d/'+job['file_id']+'/view',message='Видео загружено на Google Диск',session='')
            save(job)
        folder=request('GET',API+'/files/'+job['folder'],params={'fields':'id,name,mimeType,capabilities(canAddChildren)','supportsAllDrives':'true'})
        check(folder);target=folder.json()
        if target.get('mimeType')!='application/vnd.google-apps.folder' or not target.get('capabilities',{}).get('canAddChildren'):
            raise ValueError('Выбранная папка недоступна для загрузки.')
        job.update(folder_name=target['name'],message='Проверяю готовое видео');save(job)
        if not job.get('md5'):
            digest=hashlib.md5()
            with path.open('rb') as source:
                while True:
                    if cancel.is_set():raise InterruptedError('Отправка приостановлена.')
                    chunk=source.read(8*1024*1024)
                    if not chunk:break
                    digest.update(chunk)
            job['md5']=digest.hexdigest();save(job)
        if not job.get('file_id'):
            ids=request('GET',API+'/files/generateIds',params={'count':1,'space':'drive'});check(ids)
            job['file_id']=ids.json()['ids'][0];save(job)
        existing=metadata()
        if existing.status_code==200:finish(existing);return
        if existing.status_code!=404:check(existing)
        uri=secret(job['session'],True) if job.get('session') else ''
        offset=0
        if uri:
            parsed=urlsplit(uri)
            if parsed.scheme!='https' or parsed.netloc!='www.googleapis.com' or parsed.path!='/upload/drive/v3/files':raise ValueError('Некорректная сохранённая сессия загрузки.')
            status=request('PUT',uri,headers={'Content-Length':'0','Content-Range':f'bytes */{stat.st_size}'})
            if status.status_code in (200,201):finish(metadata());return
            if status.status_code in (404,410):uri=''
            elif status.status_code==308:
                match=re.fullmatch(r'bytes=0-(\d+)',status.headers.get('Range',''))
                offset=int(match[1])+1 if match else 0
            else:check(status)
        if not uri:
            response=request('POST',UPLOAD,params={'uploadType':'resumable','supportsAllDrives':'true'},
                json={'id':job['file_id'],'name':path.name,'parents':[job['folder']]},
                headers={'X-Upload-Content-Type':'video/mp4','X-Upload-Content-Length':str(stat.st_size)})
            if response.status_code==409:finish(metadata());return
            check(response);uri=response.headers['Location']
            parsed=urlsplit(uri)
            if parsed.scheme!='https' or parsed.netloc!='www.googleapis.com' or parsed.path!='/upload/drive/v3/files':raise ValueError('Google вернул неожиданный адрес загрузки.')
            job['session']=secret(uri);save(job)
        with path.open('rb') as source:
            while offset<stat.st_size:
                if [path.stat().st_size,path.stat().st_mtime_ns]!=job['identity']:raise ValueError('Файл изменился во время отправки.')
                source.seek(offset);chunk=source.read(min(8*1024*1024,stat.st_size-offset))
                response=request('PUT',uri,data=chunk,headers={'Content-Type':'video/mp4','Content-Length':str(len(chunk)),'Content-Range':f'bytes {offset}-{offset+len(chunk)-1}/{stat.st_size}'})
                if response.status_code in (200,201):finish(metadata());return
                if response.status_code!=308:check(response)
                match=re.fullmatch(r'bytes=0-(\d+)',response.headers.get('Range',''))
                acknowledged=int(match[1])+1 if match else 0
                if not offset<acknowledged<=offset+len(chunk):raise ValueError('Google не подтвердил передачу блока. Продолжите отправку.')
                offset=acknowledged
                job.update(uploaded=offset,progress=round(offset/stat.st_size*100,1),message='Отправляю видео на Google Диск');save(job)
        finish(metadata())
    finally:
        client.close()
