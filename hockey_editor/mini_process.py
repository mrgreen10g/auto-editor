"""GUI-thread stage controls shared by mobile and desktop workflows."""
import hashlib,json,re,secrets,time
from .mini_server import RemoteError

class Process:
    def __init__(self,bridge):
        self.bridge=bridge;self.job=None;self.requests={};self.auto_scope=None;self.failed_scope=None
        self.scheduled=False;self.scan_received=False;self.plan_received=False

    def blocks(self):
        app=self.bridge.app
        indices=app.selected_indices() if hasattr(app,'selected_indices') else [app.index]
        return [app.project.blocks[i] for i in indices]

    def scope(self):
        from .event_search import search_key
        app=self.bridge.app
        data=[str(app.project_path),app.project.host_paths(),app.project.whole_episode,
              [(b.uid,search_key(b,app.project.matches,app.project.settings.use_manual_clips)) for b in self.blocks()]]
        return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

    def begin(self,stage):
        if stage not in ('goals','analyze','render'):return
        self.auto_scope=None;self.scan_received=False;self.plan_received=False
        self.job=dict(id=secrets.token_hex(16),stage=stage,status='running',started=time.time(),elapsed=0,
                      message={'goals':'Ищем фрагменты','analyze':'Ищем тайминги и плашки','render':'Подготовка и рендер'}[stage],
                      progress=None,error='',scope=self.scope())
        if stage=='goals':self.failed_scope=None

    def status(self):
        from .goals import unresolved
        from .event_search import needs_search
        from .review import pending
        app=self.bridge.app;blocks=self.blocks()
        missing=any(needs_search(b,app.project.matches,app.project.settings.use_manual_clips) for b in blocks)
        clips=sum(len(unresolved(b)) for b in blocks);cards=len(pending(app.plan)) if app.plan else 0
        locked=self.bridge.locked() or self.bridge.media_busy
        if self.job and self.job['status'] in ('running','cancelling'):self.job['elapsed']=round(time.time()-self.job['started'])
        failed=bool(self.job and self.job['scope']==self.scope() and self.job['status'] in ('error','cancelled'))
        steps=[dict(name='Фрагменты',state='Нужен поиск' if missing else 'Нужна проверка' if clips else 'Готово'),
               dict(name='Тайминги и плашки',state='Нужен поиск' if app.plan is None else 'Нужна проверка' if cards else 'Готово'),
               dict(name='Рендер',state='Готово' if app.result else 'Ожидает запуска')]
        if self.job and app.busy:
            index={'goals':0,'analyze':1,'render':2}[self.job['stage']];steps[index]['state']='Обрабатывается'
        return dict(revision=self.bridge.revision(),job=self.job,busy=app.busy,locked=locked,steps=steps,
                    scope='Весь выпуск' if app.project.whole_episode else blocks[0].title if blocks else 'Нет разборов',
                    auto_timing=bool(app.notifier.config.get('auto_timing',True)),clips=clips,cards=cards,
                    can_goals=not locked and any(b.match_ids for b in blocks),
                    can_analyze=not locked and bool(blocks) and not missing and not clips,
                    can_render=not locked and app.plan is not None and not missing and not clips and not cards,
                    can_cancel=bool(app.busy and self.job and self.job['status']=='running'),
                    retry=failed,log=app.log_lines[-15:],message=app.status.get(),
                    next='Дождитесь завершения' if app.busy else 'Поиск фрагментов' if missing else 'Проверка видео' if clips else 'Поиск таймингов' if app.plan is None else 'Проверка плашек' if cards else 'Рендер')

    def start(self,data):
        app=self.bridge.app;stage=data.get('stage');request=str(data.get('request',''))
        if stage not in ('goals','analyze') or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',request):raise RemoteError('Неизвестный этап или запрос.')
        if request in self.requests:return self.status()
        self.bridge.check_revision(data)
        state=self.status()
        if not state['can_'+stage]:raise RemoteError('Завершите текущую обработку, проверьте вставки и материалы. Закройте окно правок на ПК.',409)
        if stage=='goals' and any(b.events for b in self.blocks()) and data.get('replace') is not True:
            raise RemoteError('Подтвердите повторный подбор: существующие вставки и дорожка будут заменены.',409)
        self.bridge.checkpoint()
        self.requests[request]=True
        while len(self.requests)>64:self.requests.pop(next(iter(self.requests)))
        try:
            if stage=='goals':app.search_matches(remote=True,replace=data.get('replace') is True)
            else:app.start(False,remote=True)
        except Exception as error:
            self.requests.pop(request,None)
            if self.job:self.job.update(status='error',error=str(error),message='Не удалось запустить этап')
            raise RemoteError(str(error)) from None
        return self.status()

    def cancel(self,data):
        app=self.bridge.app
        if not self.job or data.get('job')!=self.job['id'] or not app.busy or self.job['status'] not in ('running','cancelling'):
            raise RemoteError('Этот этап уже не выполняется.',409)
        self.auto_scope=None;app.auto_timing_ready=False;app.cancel.set()
        self.job.update(status='cancelling',message='Останавливаем обработку…')
        return self.status()

    def configure(self,data):
        self.bridge.check_revision(data)
        if not isinstance(data.get('auto_timing'),bool):raise RemoteError('Некорректная настройка.')
        from .notifications import save
        app=self.bridge.app;config=dict(app.notifier.config);config['auto_timing']=data['auto_timing']
        save(config);app.notifier.config=config
        if not config['auto_timing']:self.auto_scope=None;app.auto_timing_ready=False
        return self.status()

    def clips_finished(self,errors):
        self.scan_received=True
        if errors:
            self.failed_scope=self.scope();self.auto_scope=None
            if self.job:self.job.update(status='error',error='\n'.join(errors),message='Не все записи удалось обработать')
        else:self.auto_scope=self.scope()

    def approved(self,kind):
        if kind!='clip':return
        state=self.status()
        if state['clips'] or not state['can_analyze'] or self.failed_scope==self.scope():return
        self.auto_scope=self.scope();self.schedule_auto()

    def schedule_auto(self):
        config=self.bridge.app.notifier.config
        if not config.get('mini_enabled') or not config.get('auto_timing',True):return
        if self.scheduled:return
        self.scheduled=True
        self.bridge.app.root.after(500,self.maybe_auto)

    def maybe_auto(self):
        self.scheduled=False;app=self.bridge.app
        if not self.auto_scope or self.auto_scope!=self.scope():self.auto_scope=None;return
        if not app.notifier.config.get('auto_timing',True) or app.cancel.is_set():self.auto_scope=None;return
        state=self.status()
        if state['clips']:return
        if state['locked']:
            self.schedule_auto();return
        if not state['can_analyze']:return
        self.auto_scope=None;app.auto_timing_ready=False
        try:
            self.bridge.checkpoint();app.start(False,remote=True)
        except Exception as error:
            app.log_lines.append('Автоматический поиск таймингов: '+str(error))
            if self.job:self.job.update(status='error',error=str(error),message='Запустите поиск таймингов вручную')

    def event(self,kind,value):
        job=self.job
        if not job:return
        if kind=='done':
            if getattr(self.bridge.app,'stage',job['stage']) not in (job['stage'],'review_required','footage_review_required'):return
            if job['status'] in ('running','cancelling'):
                success=job['stage']=='goals' and self.scan_received or job['stage']=='analyze' and self.plan_received
                job.update(status='completed' if success else 'cancelled' if job['status']=='cancelling' else 'error',message='Этап завершён' if success else 'Этап остановлен')
            job['elapsed']=round(time.time()-job['started'])
            try:self.bridge.checkpoint()
            except Exception as error:
                self.auto_scope=None;self.bridge.app.auto_timing_ready=False
                job.update(status='error',error=str(error),message='Не удалось сохранить результаты. Проверьте место на диске.')
            if job['stage']=='goals' and job['status']=='completed':self.schedule_auto()
            return
        if job['status'] not in ('running','cancelling'):return
        if kind=='log':
            job['message']=str(value);match=re.search(r'(?:Поиск голов|Экспорт|Подготовка ведущего|Кадры): (\d+)%',str(value))
            job['progress']=int(match[1]) if match else None
        elif kind=='plan':self.plan_received=True
        elif kind=='result':job.update(status='completed',message='Видео готово',progress=100)
        elif kind=='error':self.auto_scope=None;job.update(status='error',message='Ошибка обработки',error=str(value))
        elif kind=='cancelled':self.auto_scope=None;job.update(status='cancelled',message='Обработка отменена')
        elif kind in ('review_required','footage_review_required'):job.update(status='review',message='Нужна проверка перед рендером')
