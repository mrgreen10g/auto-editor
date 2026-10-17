"""Opt-in Telegram status messages. Never send media, scripts or raw errors."""
import base64,json,os,queue,re,threading,time,uuid,ssl,socket
from functools import lru_cache
from pathlib import Path
from urllib.request import Request,urlopen,getproxies
from urllib.error import HTTPError,URLError

EVENTS={'started':'Начало этапа','clips':'Фрагменты готовы','cards':'Плашки готовы','attention':'Нужна проверка','render':'Рендер завершён','error':'Ошибка','cancelled':'Отмена'}

def location():
    from .preferences import location as prefs
    return prefs().with_name('telegram.json')

def protect(data,decrypt=False):
    if os.name!='nt':raise ValueError('Защищённое хранение токена доступно в Windows.')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data);src=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));dst=Blob()
    api=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not api(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst)):raise ValueError('Не удалось открыть/сохранить токен в профиле Windows.')
    try:return ctypes.string_at(dst.data,dst.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(dst.data,ctypes.c_void_p))

def load(path=None):
    result=dict(enabled=False,auto_timing=True,token='',chat_id='',events=list(EVENTS))
    try:
        data=json.loads(Path(path or location()).read_text(encoding='utf-8'))
        result.update({k:data[k] for k in ('enabled','auto_timing','chat_id','events') if k in data})
        if data.get('secret'):result['token']=protect(base64.b64decode(data['secret']),True).decode()
    except (OSError,ValueError,TypeError):result['enabled']=False
    return result

def validate(config):
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',config['token']):raise ValueError('Введите токен бота из BotFather.')
    if not re.fullmatch(r'[1-9]\d*',str(config['chat_id'])):raise ValueError('Укажите ID личного чата с ботом.')

def save(config,path=None):
    if config['enabled']:validate(config)
    data={k:config[k] for k in ('enabled','auto_timing','chat_id','events')}
    data['secret']=base64.b64encode(protect(config['token'].encode())).decode() if config['token'] else ''
    target=Path(path or location());target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');temp.replace(target)

class DeliveryError(Exception):
    def __init__(self,message,retry=False,delay=2):super().__init__(message);self.retry=retry;self.delay=delay

@lru_cache(maxsize=1)
def tls_context():
    # Windows stores may lack intermediates/roots present on an ordinary desktop.
    # Keep Windows trust and supplement it with the bundled public CA roots.
    import certifi
    context=ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context

def network_error(error):
    cause=error.reason if isinstance(error,URLError) else error
    proxy=' Обнаружен системный прокси: проверьте его настройки в Windows.' if getproxies().get('https') else ''
    if isinstance(cause,ssl.SSLCertVerificationError):
        return DeliveryError('TLS: не удалось проверить сертификат Telegram (код '+str(cause.verify_code)+'). Проверьте дату Windows и доверенные сертификаты.'+proxy)
    if isinstance(cause,ssl.SSLError):return DeliveryError('TLS: ошибка защищённого соединения с Telegram.'+proxy)
    if isinstance(cause,socket.gaierror):return DeliveryError('DNS: Python не смог определить адрес api.telegram.org.'+proxy,True)
    if isinstance(cause,(TimeoutError,socket.timeout)):return DeliveryError('Тайм-аут: Telegram не ответил за 20 секунд.'+proxy,True)
    number=getattr(cause,'winerror',None) or getattr(cause,'errno',None)
    return DeliveryError('Соединение с Telegram не установлено'+(' (код '+str(number)+')' if isinstance(number,int) else '')+'.'+proxy,True)

def api(token,method,payload):
    request=Request('https://api.telegram.org/bot'+token+'/'+method,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        with urlopen(request,timeout=20,context=tls_context()) as response:data=json.load(response)
    except HTTPError as error:
        delay=2
        if error.code==429:
            try:delay=min(60,max(1,int(json.load(error).get('parameters',{}).get('retry_after',2))))
            except (ValueError,TypeError):pass
        descriptions={401:'Telegram отклонил токен. Скопируйте актуальный токен из BotFather.',403:'Бот не может написать в этот чат. Разблокируйте его и нажмите Start.',404:'Проверьте токен: адрес бота не найден.',409:'Бот занят другим получателем обновлений или webhook. Используйте отдельного бота.',407:'Системный прокси требует авторизацию.',429:'Telegram ограничил частоту запросов. Повторите позже.'}
        raise DeliveryError('Telegram: HTTP '+str(error.code)+'. '+descriptions.get(error.code,'Запрос отклонён; проверьте чат или повторите позже.'),error.code==429 or error.code>=500,delay) from None
    except (URLError,TimeoutError,OSError) as error:raise network_error(error) from None
    except (ValueError,UnicodeError):raise DeliveryError('Ответ от Telegram не является JSON. Возможна подмена ответа прокси или сетевым фильтром.') from None
    if not isinstance(data,dict):raise DeliveryError('Telegram вернул неожиданный формат ответа.')
    if not data.get('ok'):raise DeliveryError('Telegram отклонил запрос. Проверьте подключение.')
    return data.get('result')

def send(config,text):
    validate(config)
    return api(config['token'],'sendMessage',{'chat_id':config['chat_id'],'text':text[:4000]})

class Notifier:
    def __init__(self,report=lambda _:None):
        self.config=load();self.report=report;self.queue=queue.Queue(maxsize=64);self.seen=set();self.lock=threading.Lock();self.worker=None
    def emit(self,job,event,text):
        config=dict(self.config)
        if not config['enabled'] or event not in config['events']:return
        key=(job,event)
        with self.lock:
            if key in self.seen:return
            try:self.queue.put_nowait((config,text,time.monotonic()))
            except queue.Full:self.report('Очередь Telegram заполнена; монтаж продолжается.');return
            if len(self.seen)>2048:self.seen.clear()
            self.seen.add(key)
            if self.worker is None or not self.worker.is_alive():
                self.worker=threading.Thread(target=self._run,daemon=True);self.worker.start()
    def _run(self):
        while True:
            with self.lock:
                try:item=self.queue.get_nowait()
                except queue.Empty:self.worker=None;return
            config,text,created=item
            try:
                for attempt in range(3):
                    if time.monotonic()-created>600:break
                    try:send(config,text);break
                    except DeliveryError as error:
                        if not error.retry or attempt==2:self.report(str(error));break
                        time.sleep(error.delay*(attempt+1))
                    except ValueError:self.report('Telegram не настроен; монтаж продолжается.');break
            finally:self.queue.task_done()

def begin(app,stage):
    app.notification_job=uuid.uuid4().hex
    app.notification_title=(Path(app.project_path).stem if app.project_path else Path(app.project.host).stem or 'Выпуск')+' · '+app.project.profile
    app.notification_started=time.monotonic();app.auto_timing_ready=False
    emit(app,'started',{'goals':'Поиск фрагментов начат.','analyze':'Поиск таймингов и плашек начат.','render':'Подготовка и рендер начаты.'}.get(stage,stage))

def emit(app,event,text):
    notifier=getattr(app,'notifier',None)
    if notifier:
        elapsed=int(time.monotonic()-getattr(app,'notification_started',time.monotonic()))
        notifier.emit(getattr(app,'notification_job','startup'),event,getattr(app,'notification_title','Auto Editor')+'\n'+text+f'\nПрошло: {elapsed//60} мин {elapsed%60} с.')

def clips_finished(app,errors):
    from .goals import unresolved
    from .event_search import needs_search
    blocks=[app.project.blocks[i] for i in app.selected_indices()]
    count=sum(len(unresolved(b)) for b in blocks)
    incomplete=any(needs_search(b,app.project.matches,app.project.settings.use_manual_clips) for b in blocks)
    app.auto_timing_ready=bool(blocks) and not errors and not count and not incomplete and not app.cancel.is_set()
    emit(app,'attention' if errors or count or incomplete else 'clips',f'Поиск фрагментов завершён. Требуют проверки: {count}.'+(' Есть ошибки поиска; откройте журнал на сервере.' if errors or incomplete else ''))

def continue_timing(app):
    ready=getattr(app,'auto_timing_ready',False);app.auto_timing_ready=False
    if ready and not app.cancel.is_set() and app.notifier.config.get('auto_timing',True):app.start(False)
