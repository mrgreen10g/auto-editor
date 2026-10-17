"""Main-thread review transactions and bounded asynchronous mobile previews."""
import copy,hashlib,json,math,queue,secrets,threading,time
from dataclasses import asdict
from pathlib import Path
from .mini_server import Gateway,RemoteError

class Bridge:
    def __init__(self,app):
        self.app=app;self.gateway=None;self.commands=queue.Queue(maxsize=24);self.history=None
        self.jobs={};self.media_lock=threading.Lock();self.media_busy=False;self.closed=False
        self.instance=secrets.token_hex(16)
    def configure(self):
        if self.gateway:self.gateway.close();self.gateway=None
        config=self.app.notifier.config
        if config.get('mini_enabled'):
            try:self.gateway=Gateway(self,config)
            except OSError:self.app.log_lines.append('Mini App: порт 18473 занят. Закройте второй экземпляр редактора и повторите включение.');raise ValueError('Mini App: порт 18473 занят. Закройте второй экземпляр редактора.') from None
    def close(self):
        self.closed=True
        if self.gateway:self.gateway.close();self.gateway=None
    def request(self,kind,data):
        if self.closed:raise RemoteError('Редактор закрыт.',503)
        command={'kind':kind,'data':data,'event':threading.Event(),'deadline':time.monotonic()+12}
        try:self.commands.put_nowait(command)
        except queue.Full:raise RemoteError('Редактор занят запросами. Повторите позже.',429) from None
        if not command['event'].wait(15):raise RemoteError('Редактор не ответил. Обновите список перед повтором решения.',503)
        if 'error' in command:raise command['error']
        return command['result']
    def drain(self):
        for _ in range(4):
            try:command=self.commands.get_nowait()
            except queue.Empty:break
            try:
                if time.monotonic()>command['deadline']:raise RemoteError('Запрос устарел. Обновите список.',409)
                command['result']=self.handle(command['kind'],command['data'])
            except RemoteError as error:command['error']=error
            except Exception as error:
                self.app.log_lines.append('Mini App · '+command['kind']+': '+type(error).__name__)
                command['error']=RemoteError('Не удалось выполнить действие. Проверьте материалы и журнал на сервере.',400)
            finally:command['event'].set()
    def revision(self):
        app=self.app
        if not app.busy:app.collect()
        identities=[]
        for path in app.project.host_paths()+[m.path for m in app.project.matches]:
            try:
                stat=Path(path).stat()
                with Path(path).open('rb') as stream:
                    sample=stream.read(4096)
                    if stat.st_size>4096:stream.seek(max(4096,stat.st_size-4096));sample+=stream.read(4096)
                identities.append([path,stat.st_size,stat.st_mtime_ns,hashlib.sha256(sample).hexdigest()])
            except OSError:identities.append([path,'missing'])
        content=[self.instance,id(app.project),str(app.project_path),app.index,identities,asdict(app.project),app.plan.to_dict() if app.plan else None]
        return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    def check_revision(self,data):
        if data.get('revision')!=self.revision():raise RemoteError('Проект изменился. Обновите список и проверьте элемент заново.',409)
    def locked(self):
        return self.app.busy or self.app.root.grab_current() is not None
    def find(self,ident):
        app=self.app
        if ident.startswith('clip:'):
            _,uid,number=ident.split(':');block=next(b for b in app.project.blocks if b.uid==uid)
            index=int(number)
            if index<0:raise ValueError()
            return block,block.events[index]
        if ident.startswith('card:') and app.plan:
            task=next(t for t in app.plan.review_items if t['id']==ident[5:])
            card=next((c for c in app.plan.cards if c.review_id==task['id']),None)
            if card is None and task.get('deleted_card'):
                from .timeline import Card
                card=Card(**task['deleted_card'])
            return task,card
        raise RemoteError('Элемент больше не найден.',404)
    def state(self):
        app=self.app;revision=self.revision();items=[]
        for block in app.project.blocks:
            for i,event in enumerate(block.events):
                status='deleted' if event.skipped else 'confirmed' if event.selection and event.selection.accepted else 'pending'
                items.append(dict(id=f'clip:{block.uid}:{i}',kind='clip',title=block.title,text=event.phrase,status=status))
        if app.plan:
            from .review import update_task_times,describe_card
            update_task_times(app.plan)
            for task in app.plan.review_items:
                card=next((c for c in app.plan.cards if c.review_id==task['id']),None)
                title,where=describe_card(card,task,app.project,app.plan)
                items.append(dict(id='card:'+task['id'],kind='card',title=title+' · '+where,text=card.text if card else task['script'],status=task['status']))
        return dict(revision=self.revision(),title=Path(app.project_path or app.project.host or 'Выпуск').stem,profile=app.project.profile,items=items,busy=app.busy,locked=self.locked(),stage=app.status.get(),undo=bool(self.history and self.history['after']==self.revision()),saved=bool(app.project_path),scope='Весь выпуск' if app.project.whole_episode else 'Плашки текущего разбора')
    def options(self,block,event):
        from .goals import source_signature,scan_root
        result=[]
        for source in self.app.project.matches:
            if source.id not in block.match_ids:continue
            if getattr(event,'strict_source',False) and source.id!=event.source_id:continue
            if block.sport=='combat' and event.requested_teams and source.fighter not in event.requested_teams:continue
            try:
                signature=source_signature(source);data=self.app.scans.get(source.id)
                if not data or data.get('signature')!=signature:
                    path=scan_root()/signature[:24]/'goals.json';data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                if data.get('signature')!=signature:data={}
                candidates=list(data.get('candidates',[]))[:200]
                if event.selection and event.source_id==source.id and event.selection.source_signature==signature:
                    sel=event.selection
                    candidates.insert(0,dict(id='__current__',start=sel.source_start,end=sel.source_end,time=sel.event_time,note='Текущая вставка',score=None))
                for c in candidates:
                    score=c.get('score');warning=' · Другой счёт: '+str(score) if event.score and score and list(event.score)!=list(score) else ''
                    result.append(dict(key=source.id+':'+str(c['id']),source=source.id,signature=signature,start=c['start'],end=c['end'],time=c['time'],title=source.title+' · '+str(c.get('note',''))+warning))
            except (OSError,ValueError):continue
        return result
    def item(self,data):
        self.check_revision(data);first,second=self.find(data['id']);app=self.app
        if data['id'].startswith('clip:'):
            options=self.options(first,second);current=next((o for o in options if o['key']==second.source_id+':__current__'),options[0] if options else None)
            return dict(kind='clip',title=first.title,script=second.phrase,recognized='',text='',reason=second.note,options=options,choice=current,language=first.language,voice=False)
        task,card=first,second
        from .review import describe_card,source_time
        title,where=describe_card(card,task,app.project,app.plan)
        return dict(kind='card',title=title,where=where,script=task['script'],recognized=task.get('recognized',''),text=card.text if card else '',reason=task['reason'],start=card.start if card else task['start'],end=card.end if card else task['end'],source_start=source_time(app.plan,task['start']),source_end=source_time(app.plan,task['end']),owner=card.forecast_id if card else '',forecast=bool(card and card.title=='ПРОГНОЗ'),owners=[dict(id=b.uid,title=b.title) for b in app.project.blocks],language='uz' if app.project.profile.startswith('uz_') else 'ru',voice=True)
    def selection(self,block,event,data):
        from .model import EventSelection
        from .media import probe
        choice=next((o for o in self.options(block,event) if o['key']==data.get('choice')),None)
        if not choice:raise RemoteError('Выберите существующий кандидат. Возможно, запись изменилась.',409)
        source=next(s for s in self.app.project.matches if s.id==choice['source'])
        start,end,when=[float(data.get(k,choice[k])) for k in ('start','end','time')]
        if not all(math.isfinite(x) for x in (start,end,when)) or not 0<=start<=when<=end or not .5<=end-start<=60 or end>probe(source.path)['duration']+.05:raise RemoteError('Границы: начало ≤ событие ≤ конец; длина 0,5–60 секунд.')
        label=event.selection.context_label if event.selection and source.id==event.source_id else 'Архивные кадры · '+source.title
        return source,EventSelection(choice['key'].split(':',1)[1],start,end,when,choice['signature'],True,label)
    def checkpoint(self):
        app=self.app
        target=Path(app.project_path) if app.project_path else Path(app.cache_path())/'mobile-review.hockeyproj'
        app.project.save(target)
        return target.name
    def action(self,data):
        app=self.app;self.check_revision(data)
        if self.locked():raise RemoteError('Сейчас идёт обработка или открыто окно правок на ПК. Дождитесь окончания или закройте окно.',409)
        before=(copy.deepcopy(app.project),copy.deepcopy(app.plan));old_result=app.result
        try:
            if data.get('decision')=='undo':
                if not self.history or self.history['after']!=self.revision():raise RemoteError('Отмена недоступна: проект изменился.',409)
                app.project,app.plan=copy.deepcopy(self.history['before']);app.refresh()
                if app.plan:app.display_plan(app.plan)
                else:app.invalidate()
            else:
                first,second=self.find(data['id']);decision=data['decision']
                if decision not in ('confirmed','deleted','pending'):raise RemoteError('Неизвестное решение.')
                if data['id'].startswith('card:'):
                    from .review import resolve
                    owner=str(data.get('owner',second.forecast_id if second else ''))
                    if owner and owner not in {b.uid for b in app.project.blocks}:raise RemoteError('Матч для ставки не найден.')
                    plan=resolve(app.plan,first['id'],decision,text=str(data.get('text',second.text if second else ''))[:4000],start=float(data.get('start',first['start'])),end=float(data.get('end',first['end'])),owner=owner)
                    next(t for t in plan.review_items if t['id']==first['id'])['recognized']=str(data.get('recognized',first.get('recognized','')))[:8000]
                    app.display_plan(plan)
                else:
                    if decision=='confirmed':
                        source,selection=self.selection(first,second,data);second.source_id=source.id;second.selection=selection;second.skipped=False
                    elif decision=='deleted':second.skipped=True
                    else:
                        second.skipped=False
                        if second.selection:second.selection.accepted=False
                    first.edit_plan=None;first.edit_key='';app.project.episode_plan=None;app.project.episode_key=''
                    app.invalidate();app.refresh_events();app.update_summary()
            app.result=None
            saved=self.checkpoint()
            self.history=None if data.get('decision')=='undo' else dict(before=before,after=self.revision())
            return dict(ok=True,saved=saved,revision=self.revision())
        except Exception:
            app.project,app.plan=before;app.result=old_result;app.refresh()
            if app.plan:app.display_plan(app.plan)
            raise
    def prepare(self,data):
        self.check_revision(data)
        if self.app.busy:raise RemoteError('Дождитесь окончания обработки.',409)
        mode=data.get('mode');first,second=self.find(data['id']);spec={};app=self.app
        if mode=='clip' and data['id'].startswith('clip:'):
            source,selection=self.selection(first,second,data);spec=dict(mode=mode,path=source.path,start=selection.source_start,end=selection.source_end)
        elif mode=='voice' and data['id'].startswith('card:'):
            from .host_media import slice_media
            plan=app.plan;a=max(0,first['start']-.8);b=min(plan.duration,first['end']+.8)
            if b-a>90:b=a+90
            media=plan.media or [dict(path=app.project.host,start=plan.source_start+x,end=plan.source_start+y) for x,y in plan.keep]
            spec=dict(mode=mode,spans=slice_media(media,a,b))
        elif mode=='art' and data['id'].startswith('card:') and second:
            spec=dict(mode=mode,card=copy.deepcopy(second),profile=app.project.profile,logos=copy.deepcopy(app.project.team_logos))
        elif mode=='translation':
            from .review_translation import installed,model_folder
            if not installed(model_folder()):raise RemoteError('Модель перевода ещё не установлена. Один раз нажмите «Перевод на русский» в редакторе и завершите установку.')
            detail=self.item(data);spec=dict(mode=mode,texts=[detail[k] for k in ('script','recognized','text')])
        else:raise RemoteError('Этот предпросмотр недоступен.')
        cache=Path(app.cache_path())/'mobile-previews';cache.mkdir(parents=True,exist_ok=True)
        with self.media_lock:
            if self.media_busy:raise RemoteError('Уже готовится предпросмотр. Подождите.',429)
            while len(self.jobs)>=32:self.jobs.pop(next(iter(self.jobs)))
            self.media_busy=True;ident=secrets.token_hex(16);self.jobs[ident]=dict(status='working',revision=data['revision'],created=time.time())
        def work():
            from .mini_media import generate
            try:
                result=generate(spec,cache,ident)
                with self.media_lock:self.jobs[ident].update(status='ready',**result)
            except Exception:
                with self.media_lock:self.jobs[ident].update(status='error',error='Не удалось подготовить предпросмотр. Проверьте доступность исходника на сервере.')
            finally:
                with self.media_lock:self.media_busy=False
        threading.Thread(target=work,daemon=True).start()
        return dict(job=ident)
    def handle(self,kind,data):
        if kind=='state':return self.state()
        if kind=='item':return self.item(data)
        if kind=='action':return self.action(data)
        if kind=='prepare':return self.prepare(data)
        if kind in ('job','media'):
            with self.media_lock:job=copy.deepcopy(self.jobs.get(data.get('job')))
            if not job or time.time()-job['created']>1800:raise RemoteError('Предпросмотр устарел.',404)
            if job['revision']!=self.revision():raise RemoteError('Проект изменился. Подготовьте предпросмотр заново.',409)
            if kind=='media':
                if job['status']!='ready' or 'file' not in job:raise RemoteError('Предпросмотр ещё не готов.',409)
                return dict(file=job['file'])
            return {k:v for k,v in job.items() if k not in ('file','revision','created')}
        raise RemoteError('Неизвестный запрос.',404)
