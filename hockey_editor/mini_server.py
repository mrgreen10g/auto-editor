"""Loopback-only Telegram Mini App gateway. No unauthenticated project/media APIs."""
import hashlib,hmac,json,mimetypes,secrets,threading,time,re,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl,urlsplit

PORT=18473

def byte_range(value,size):
    if not value:return 0,size-1,False
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not match or not any(match.groups()):raise RemoteError('Некорректный диапазон.',416)
    a,b=match.groups()
    if not a:
        length=int(b)
        if length<=0:raise RemoteError('Некорректный диапазон.',416)
        start=max(0,size-length);end=size-1
    else:start=int(a);end=min(size-1,int(b)) if b else size-1
    if start>=size or start>end:raise RemoteError('Диапазон вне файла.',416)
    return start,end,True

class RemoteError(Exception):
    def __init__(self,message,status=400):super().__init__(message);self.status=status

def validate_init(raw,token,owner,now=None):
    try:
        if not isinstance(raw,str) or not 1<=len(raw)<=16384:raise ValueError()
        pairs=parse_qsl(raw,keep_blank_values=True,strict_parsing=True)
        if len(dict(pairs))!=len(pairs):raise ValueError()
        data=dict(pairs);signature=data.pop('hash');auth=int(data['auth_date'])
        secret=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
        check='\n'.join(k+'='+v for k,v in sorted(data.items()))
        expected=hmac.new(secret,check.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):raise ValueError()
        now=time.time() if now is None else now
        if not -30<=now-auth<=600:raise ValueError()
        user=json.loads(data['user'])
        if user.get('is_bot') or str(user['id'])!=str(owner) or int(owner)<=0:raise ValueError()
        return str(user['id'])
    except (ValueError,KeyError,TypeError):raise RemoteError('Откройте Mini App заново из личного чата со своим ботом.',401) from None

def validate_url(value):
    url=urlsplit(value.strip())
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.port not in (None,443) or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Введите HTTPS-адрес Funnel без пути и параметров, например https://server.example.ts.net')
    return 'https://'+url.netloc.lower()

class Gateway:
    def __init__(self,bridge,config,port=PORT):
        self.bridge=bridge;self.config=dict(config);self.sessions={};self.lock=threading.Lock();self.attempts=[];self.streams={}
        class BoundedServer(ThreadingHTTPServer):
            daemon_threads=True
            def __init__(self,*args):self.slots=threading.BoundedSemaphore(12);super().__init__(*args)
            def process_request(self,request,address):
                if not self.slots.acquire(blocking=False):self.shutdown_request(request);return
                try:super().process_request(request,address)
                except Exception:self.slots.release();raise
            def process_request_thread(self,request,address):
                try:super().process_request_thread(request,address)
                finally:self.slots.release()
        self.server=BoundedServer(('127.0.0.1',port),self.handler())
        self.server.gateway=self
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):
        with self.lock:self.sessions.clear();self.streams.clear()
        threading.Thread(target=self.server.shutdown,daemon=True).start();self.server.server_close()
    def login(self,raw):
        with self.lock:
            now=time.time();self.attempts=[t for t in self.attempts if now-t<60]
            if len(self.attempts)>=30:raise RemoteError('Слишком много попыток входа. Подождите минуту.',429)
            self.attempts.append(now)
        validate_init(raw,self.config['token'],self.config['chat_id'])
        session=secrets.token_urlsafe(32)
        with self.lock:
            self.sessions={k:v for k,v in self.sessions.items() if v>now}
            if len(self.sessions)>=16:self.sessions.pop(next(iter(self.sessions)))
            self.sessions[session]=now+1800
        return session
    def authorize(self,value):
        token=value.removeprefix('Bearer ')
        with self.lock:
            if not value.startswith('Bearer ') or self.sessions.get(token,0)<time.time():raise RemoteError('Сессия истекла. Закройте и откройте Mini App.',401)
    def handler(self):
        gateway=self
        class Handler(BaseHTTPRequestHandler):
            server_version='AutoEditor';sys_version=''
            def setup(self):super().setup();self.connection.settimeout(15)
            def log_message(self,*args):pass
            def response(self,status,data,kind='application/json; charset=utf-8'):
                if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
                self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; img-src 'self' blob:; media-src 'self' blob:; connect-src 'self'; base-uri 'none'; form-action 'none'")
                self.end_headers();self.wfile.write(data)
            def handle_request(self):
                try:
                    path=urlsplit(self.path).path
                    if len(self.path)>2048:raise RemoteError('Слишком длинный запрос.',414)
                    if self.command in ('GET','HEAD') and path.startswith('/stream/'):
                        with gateway.lock:ticket=gateway.streams.get(path.removeprefix('/stream/'))
                        if not ticket or ticket['expires']<time.time():raise RemoteError('Обновите видео в Mini App.',401)
                        gateway.authorize(ticket['authorization'])
                        with Path(ticket['file']).open('rb') as source:
                            stat=os.fstat(source.fileno())
                            if [stat.st_size,stat.st_mtime_ns]!=ticket['identity']:raise RemoteError('Готовый файл изменился.',409)
                            try:start,end,partial=byte_range(self.headers.get('Range',''),stat.st_size)
                            except RemoteError:
                                self.send_response(416);self.send_header('Content-Range',f'bytes */{stat.st_size}');self.send_header('Content-Length','0');self.end_headers();return
                            self.send_response(206 if partial else 200)
                            self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
                            self.send_header('Content-Length',str(end-start+1));self.send_header('Cache-Control','no-store')
                            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
                            if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{stat.st_size}')
                            self.end_headers()
                            if self.command=='HEAD':return
                            source.seek(start);remaining=end-start+1
                            while remaining>0:
                                chunk=source.read(min(65536,remaining))
                                if not chunk:break
                                self.wfile.write(chunk);remaining-=len(chunk)
                        return
                    if self.command=='GET' and path=='/input.js':
                        return self.response(200,Path(__file__).with_name('mini_web').joinpath('input.js').read_bytes(),'text/javascript; charset=utf-8')
                    if self.command=='GET' and path in ('/','/app.js','/app.css','/input.js','/editor.js','/live.js'):
                        file=Path(__file__).with_name('mini_web')/({'/':'index.html','/app.js':'app.js','/app.css':'app.css','/input.js':'input.js','/editor.js':'editor.js','/live.js':'live.js'}[path])
                        return self.response(200,file.read_bytes(),{'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/app.css':'text/css; charset=utf-8','/input.js':'text/javascript; charset=utf-8','/editor.js':'text/javascript; charset=utf-8','/live.js':'text/javascript; charset=utf-8'}[path])
                    if self.command!='POST':raise RemoteError('Не найдено.',404)
                    origin=self.headers.get('Origin')
                    if origin and origin!=gateway.config['mini_url']:raise RemoteError('Недопустимый источник запроса.',403)
                    if path=='/api/input-chunk':
                        gateway.authorize(self.headers.get('Authorization',''))
                        from .mobile_inputs import CHUNK
                        size=int(self.headers.get('Content-Length','0'))
                        if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type')!='application/octet-stream' or not 0<size<=CHUNK:raise RemoteError('Некорректный блок файла.',413)
                        content=self.rfile.read(size)
                        if len(content)!=size:raise RemoteError('Блок передан не полностью.')
                        return self.response(200,gateway.bridge.inputs.chunk(dict(id=self.headers.get('X-Draft'),file=self.headers.get('X-File'),offset=self.headers.get('X-Offset')),content))
                    if self.headers.get('Transfer-Encoding') or 'application/json' not in self.headers.get('Content-Type',''):raise RemoteError('Нужен JSON.',415)
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=(12*1024*1024 if path=='/api/editor-logo-upload' else 1048576 if path in ('/api/input-script','/api/input-script-save','/api/editor-action') else 65536):raise RemoteError('Некорректный размер запроса.',413)
                    data=json.loads(self.rfile.read(size))
                    if not isinstance(data,dict):raise RemoteError('Нужен объект JSON.')
                    if path=='/api/auth':return self.response(200,{'session':gateway.login(data.get('initData'))})
                    gateway.authorize(self.headers.get('Authorization',''))
                    if path in {'/api/input-'+k for k in ('status','mkdir','create','script','settings','upload','finish','link','retry','edit','reuse','activate','pause','server-files','server-import','script-open','script-save','script-reload','doc-start','doc-status')}:
                        return self.response(200,gateway.bridge.request(path.removeprefix('/api/'),data))
                    if path not in ('/api/live-scene','/api/live-art','/api/editor-logo-upload','/api/preview-stream','/api/editor-files','/api/editor-state','/api/editor-action','/api/result-status','/api/result-stream','/api/drive-config','/api/drive-start','/api/drive-pause','/api/process-status','/api/process-start','/api/process-cancel','/api/process-config','/api/export-status','/api/folders','/api/export-start','/api/export-cancel','/api/state','/api/item','/api/action','/api/prepare','/api/job','/api/media'):raise RemoteError('Не найдено.',404)
                    result=gateway.bridge.request(path.removeprefix('/api/'),data)
                    if path in ('/api/result-stream','/api/preview-stream'):
                        with gateway.lock:
                            now=time.time();gateway.streams={k:v for k,v in gateway.streams.items() if v['expires']>now}
                            while len(gateway.streams)>=32:gateway.streams.pop(next(iter(gateway.streams)))
                            token=secrets.token_urlsafe(32)
                            gateway.streams[token]=dict(result,expires=now+1800,authorization=self.headers.get('Authorization',''))
                        return self.response(200,{'url':'/stream/'+token})
                    if path=='/api/media':
                        file=Path(result['file'])
                        if file.stat().st_size>32*1024*1024:raise RemoteError('Превью слишком большое.')
                        return self.response(200,file.read_bytes(),mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                    return self.response(200,result)
                except RemoteError as error:self.response(error.status,{'error':str(error)})
                except (ValueError,KeyError,TypeError):self.response(400,{'error':'Некорректный запрос.'})
                except (BrokenPipeError,ConnectionResetError,TimeoutError):pass
                except Exception:self.response(500,{'error':'Ошибка сервиса. Проверьте редактор на сервере.'})
            do_GET=handle_request
            do_HEAD=handle_request
            do_POST=handle_request
        return Handler
