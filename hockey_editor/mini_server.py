"""Loopback-only Telegram Mini App gateway. No unauthenticated project/media APIs."""
import hashlib,hmac,json,mimetypes,secrets,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl,urlsplit

PORT=18473

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
        self.bridge=bridge;self.config=dict(config);self.sessions={};self.lock=threading.Lock();self.attempts=[]
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
        with self.lock:self.sessions.clear()
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
                    if self.command=='GET' and path in ('/','/app.js','/app.css'):
                        file=Path(__file__).with_name('mini_web')/({'/':'index.html','/app.js':'app.js','/app.css':'app.css'}[path])
                        return self.response(200,file.read_bytes(),{'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/app.css':'text/css; charset=utf-8'}[path])
                    if self.command!='POST':raise RemoteError('Не найдено.',404)
                    origin=self.headers.get('Origin')
                    if origin and origin!=gateway.config['mini_url']:raise RemoteError('Недопустимый источник запроса.',403)
                    if self.headers.get('Transfer-Encoding') or 'application/json' not in self.headers.get('Content-Type',''):raise RemoteError('Нужен JSON.',415)
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=65536:raise RemoteError('Некорректный размер запроса.',413)
                    data=json.loads(self.rfile.read(size))
                    if not isinstance(data,dict):raise RemoteError('Нужен объект JSON.')
                    if path=='/api/auth':return self.response(200,{'session':gateway.login(data.get('initData'))})
                    gateway.authorize(self.headers.get('Authorization',''))
                    if path not in ('/api/state','/api/item','/api/action','/api/prepare','/api/job','/api/media'):raise RemoteError('Не найдено.',404)
                    result=gateway.bridge.request(path.removeprefix('/api/'),data)
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
            do_POST=handle_request
        return Handler
