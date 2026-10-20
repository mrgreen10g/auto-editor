"""Owner-selected local script edits and bounded Google Docs imports."""
import hashlib,re,secrets,threading,time
from pathlib import Path
from urllib.parse import urlsplit
from .mini_server import RemoteError
from . import drive_upload as drive

def doc_id(url):
    p=urlsplit(str(url).strip())
    m=re.fullmatch(r'/document/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,200})(?:/.*)?',p.path)
    if p.scheme!='https' or p.hostname!='docs.google.com' or p.username or p.password or p.port not in (None,443) or not m:
        raise RemoteError('Вставьте ссылку Google Документа вида docs.google.com/document/d/…')
    return m[1]

def fetch_document(ident):
    client,_=drive.session()
    try:
        with client.get(drive.API+'/files/'+ident+'/export',params={'mimeType':'text/plain'},stream=True,allow_redirects=False,timeout=30) as response:
            drive.check(response)
            if response.status_code!=200:raise ValueError('Google не отдал текст документа.')
            data=bytearray()
            for part in response.iter_content(65536):
                data.extend(part)
                if len(data)>500000:raise ValueError('Сценарий превышает 500 КБ.')
            text=data.decode('utf-8-sig')
            if not text.strip():raise ValueError('Документ пуст.')
            return text
    finally:client.close()

def start_document(inputs,data):
    ident=doc_id(data.get('url',''))
    with inputs.lock:
        jobs=getattr(inputs,'doc_jobs',{})
        if any(j['status']=='working' for j in jobs.values()):raise RemoteError('Документ уже загружается. Подождите.')
        key=secrets.token_hex(16);jobs={key:dict(status='working')};inputs.doc_jobs=jobs
    def work():
        try:
            text=fetch_document(ident)
            with inputs.lock:jobs[key]=dict(status='ready',text=text)
        except Exception:
            with inputs.lock:jobs[key]=dict(status='error',error='Не удалось прочитать Google Документ. Откройте доступ Google-аккаунту, подключённому в редакторе, и проверьте ссылку.')
    threading.Thread(target=work,daemon=True).start()
    return dict(job=key)

def document_status(inputs,data):
    with inputs.lock:
        result=getattr(inputs,'doc_jobs',{}).get(data.get('job'))
        if not result:raise RemoteError('Импорт документа устарел. Повторите загрузку.')
        return dict(result)

def local_script(inputs,data,save=False):
    from .script_input import read_script
    found=inputs.server_files(data);p=Path(data.get('script','')).resolve()
    if str(p) not in found['scripts']:raise RemoteError('Выберите сценарий из выбранной папки выпуска.')
    raw=p.read_bytes();version=hashlib.sha256(raw).hexdigest()
    if save:
        if data.get('version')!=version:raise RemoteError('Файл изменился на сервере. Откройте его заново перед сохранением.',409)
        text=str(data.get('text',''))
        if not text.strip() or len(text.encode())>500000:raise RemoteError('Сценарий пустой или больше 500 КБ.')
        backups=p.parent/'История сценария';backups.mkdir(exist_ok=True)
        (backups/(time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'-'+p.name)).write_bytes(raw)
        if p.suffix.lower()!='.txt':
            p=p.with_name(p.stem+'-исправленный-'+secrets.token_hex(3)+'.txt')
        temp=p.with_name(p.name+'.'+secrets.token_hex(4)+'.tmp');temp.write_text(text,encoding='utf-8');temp.replace(p)
        return dict(script=str(p),version=hashlib.sha256(p.read_bytes()).hexdigest(),text=text)
    return dict(script=str(p),text=read_script(p),version=version)
