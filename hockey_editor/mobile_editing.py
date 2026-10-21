"""Revision-checked mobile montage edits and durable undo/redo snapshots."""
import copy,hashlib,json,math,secrets,time
from dataclasses import asdict,fields
from pathlib import Path
from .mini_server import RemoteError
from .timeline import Card,Insert,Plan,frame,parse_time
from .editing import validate_plan,store_plan
from . import drive_upload as storage

CARD_TYPES=['СТАТИСТИКА','ВАЖНЫЙ ФАКТ','ВОПРОС ЗРИТЕЛЮ','ПРОГНОЗ','ОЖИДАЕМЫЙ СЧЁТ','УСЛОВИЯ ПРОГНОЗА','СОСТАВ КОМАНДЫ','РЕЗУЛЬТАТ ВСТРЕЧИ','РАЗБОР МАТЧА','КОЭФФИЦИЕНТ ИЗ РАЗБОРА']

def card_type(card,title,owner,project):
    if title==card.title:return
    if card.asset or card.title in ('СМЕНА МАТЧА','ИТОГИ ВЫПУСКА'):raise RemoteError('Тип анимации или перехода менять нельзя. Можно изменить время или удалить элемент.')
    if title not in CARD_TYPES:raise RemoteError('Выберите тип плашки из списка.')
    card.title=title;card.forecast_id=owner if title=='ПРОГНОЗ' else '';card.fixture='';card.line=-1
    if title=='ПРОГНОЗ' and owner not in {b.uid for b in project.blocks}:raise RemoteError('Выберите разбор для ставки.')

def cut_range(plan,a,b):
    a,b=frame(parse_time(a)),frame(parse_time(b));p=copy.deepcopy(plan)
    if not 0<=a<b<=p.duration or b-a<.15 or p.duration-(b-a)<.15:raise RemoteError('Выберите участок внутри дорожки, оставив не менее 0,15 секунды видео.')
    if any(s['end']-s['start']-max(0,min(b,s['end'])-max(a,s['start']))<.15 for s in p.sections):raise RemoteError('Нельзя вырезать весь раздел выпуска. Оставьте хотя бы 0,15 секунды или измените состав разделов.')
    delta=b-a
    def mapped(t):return frame(t if t<=a else a if t<b else t-delta)
    def pieces(lo,hi):return [(x,y) for x,y in [(lo,min(hi,a)),(max(lo,b),hi)] if y>x+.0001]
    keep=[];cursor=0
    for lo,hi in p.keep:
        for x,y in pieces(cursor,cursor+hi-lo):keep.append((frame(lo+x-cursor),frame(lo+y-cursor)))
        cursor+=hi-lo
    p.keep=keep
    if p.media:
        from .host_media import slice_media
        p.media=slice_media(p.media,0,a)+slice_media(p.media,b,p.duration)
    for name in ('lines','cards','inserts'):
        output=[]
        for item in getattr(p,name):
            spans=pieces(item.start,item.end)
            # Static overlays remain continuous across the removed speech.
            if (name=='lines' or name=='cards' and not item.asset) and spans:spans=[(spans[0][0],spans[-1][1])]
            for n,(lo,hi) in enumerate(spans):
                v=copy.deepcopy(item);v.start=mapped(lo);v.end=mapped(hi)
                if v.end-v.start<(.015 if name=='lines' else .15):continue
                if name=='inserts' or name=='cards' and v.asset:v.source_in=frame(item.source_in+lo-item.start)
                if name=='cards':
                    v.line=-1
                    if n:v.review_id=''
                if name=='lines':
                    v.words=[]
                    for w in item.words:
                        wa,wb=item.start+w['start'],item.start+w['end']
                        if wa>=lo and wb<=hi and not (wa<b and wb>a):v.words.append(dict(w,start=mapped(wa)-v.start,end=mapped(wb)-v.start))
                    if v.words:v.text=' '.join(w.get('word',w.get('text','')).strip() for w in v.words)
                    if n:v.review_id=''
                output.append(v)
        setattr(p,name,output)
    for s in p.sections:
        old_start,old_end=s['start'],s['end'];cursor=old_start;local_keep=[]
        for lo,hi in s.get('keep',[(0,old_end-old_start)]):
            for x,y in pieces(cursor,cursor+hi-lo):local_keep.append((frame(lo+x-cursor),frame(lo+y-cursor)))
            cursor+=hi-lo
        s['keep']=local_keep
        s['start']=mapped(s['start']);s['end']=mapped(s['end']);s['line_start']=sum(l.start<s['start']-.001 for l in p.lines);s['line_count']=sum(s['start']-.001<=l.start<s['end']-.001 for l in p.lines)
    for task in p.review_items:
        task['start']=mapped(task['start']);task['end']=mapped(task['end']);task.pop('deleted_card',None)
    from .review import update_task_times
    update_task_times(p);p.duration=frame(p.duration-delta)
    # No stale source-time baseline may reinsert a removed fragment.
    p.edit_baseline={};p.warnings.append('Участок речи вырезан вручную. Повторный поиск таймингов пересоберёт дорожку.')
    return validate_plan(p)

class Editor:
    def __init__(self,bridge):self.bridge=bridge
    @property
    def app(self):return self.bridge.app
    def root(self):
        # A renamed block changes cache_path; history must stay with the project.
        if self.app.project_path:return Path(self.app.project_path).with_suffix('.mobile-history')
        key=hashlib.sha256(self.app.project.host.encode()).hexdigest()[:16]
        return Path(self.app.cache_path()).parent/('mobile-history-'+key)
    def history(self):
        result=storage.read(self.root()/'index.json');return result if isinstance(result,dict) and 'undo' in result else dict(undo=[],redo=[])
    def fingerprint(self):
        def canonical(value,key=''):
            if isinstance(value,dict):return {k:canonical(v,k) for k,v in value.items()}
            if isinstance(value,list):return [canonical(v,'path' if key=='hosts' else '') for v in value]
            if isinstance(value,str) and value and key in ('path','host','music','asset','origin_path','asset_folder','logo_folder'):return str(Path(value).resolve())
            return value
        project=asdict(self.app.project)
        for field in ('assets','team_logos'):project[field]={k:str(Path(v).resolve()) if v else '' for k,v in project[field].items()}
        return hashlib.sha256(json.dumps(canonical([project,self.app.plan.to_dict() if self.app.plan else None,self.app.index]),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    def snapshot(self,project=None,plan=None,index=None):
        root=self.root();root.mkdir(parents=True,exist_ok=True);key=secrets.token_hex(16)
        (project or self.app.project).save(root/(key+'.hockeyproj'))
        storage.write(root/(key+'.json'),dict(plan=plan.to_dict() if plan else None,index=self.app.index if index is None else index))
        return key
    def record(self,before,label):
        h=self.history();entry=dict(before=before,after=self.snapshot(plan=self.app.plan),fingerprint=self.fingerprint(),label=label,time=time.time())
        h['undo']=(h['undo']+[entry])[-30:];h['redo']=[];storage.write(self.root()/'index.json',h)
        live={x[k] for group in ('undo','redo') for x in h[group] for k in ('before','after')}
        for p in self.root().iterdir():
            if p.stem not in live and len(p.stem)==32 and p.suffix in ('.json','.hockeyproj'):p.unlink(missing_ok=True)
    def state(self):
        b=self.bridge;app=self.app;revision=b.revision();p=app.plan;h=self.history();stamp=self.fingerprint()
        rows=[]
        if p:
            for kind,items in [('card',p.cards),('insert',p.inserts)]:
                for i,c in enumerate(items):
                    s=next((s for s in p.sections if s['start']<=c.start<s['end']),{})
                    rows.append(dict(id=f'{kind}:{i}',kind=kind,start=c.start,end=c.end,text=c.text if kind=='card' else c.label,title=c.title if kind=='card' else 'Видео-вставка',source_in=c.source_in,source_min=getattr(c,'source_min',0),source_max=getattr(c,'source_max',None),block=s.get('block_id',''),block_title=s.get('title',''),owner=getattr(c,'forecast_id',''),asset=bool(getattr(c,'asset','')),offset_x=getattr(c,'offset_x',0),offset_y=getattr(c,'offset_y',0),scale=getattr(c,'scale',1),review_id=getattr(c,'review_id','')))
        from .graphics import block_teams
        teams=list(dict.fromkeys(n for block in app.project.blocks for n in block_teams(block.title) if n))
        logos=[dict(team=n,path=app.project.team_logos.get(n,''),available=bool(app.project.team_logos.get(n) and Path(app.project.team_logos[n]).is_file())) for n in teams]
        return dict(logo_folder=app.project.logo_folder,logos=logos,revision=revision,locked=b.locked(),duration=p.duration if p else 0,items=sorted(rows,key=lambda r:(r['start'],r['kind'])),sections=p.sections if p else [],types=CARD_TYPES,blocks=[dict(uid=x.uid,title=x.title,script=x.script,kind=x.kind) for x in [app.project.intro,*app.project.blocks,app.project.outro]],settings=asdict(app.project.settings),music=app.project.music,recording_times=app.project.recording_times,matches=[dict(id=m.id,title=m.title,score_box=m.score_box) for m in app.project.matches],history=[dict(label=x['label'],time=x['time']) for x in reversed(h['undo'])],undo=bool(h['undo'] and h['undo'][-1]['fingerprint']==stamp),redo=bool(h['redo'] and h['redo'][-1]['fingerprint']==stamp))
    def apply(self,data):
        b=self.bridge;app=self.app;b.check_revision(data)
        if b.locked() or b.media_busy:raise RemoteError('Дождитесь завершения обработки/предпросмотра и закройте окно правок на ПК.',409)
        before=(copy.deepcopy(app.project),copy.deepcopy(app.plan),app.index,app.result);snapshot=self.snapshot(plan=app.plan);op=data.get('op');label='Правка монтажа';uploaded=None
        try:
            if op in ('undo','redo'):
                h=self.history();stack=h[op]
                if not stack or stack[-1]['fingerprint']!=self.fingerprint():raise RemoteError('Проект изменился вне этой истории. Обновите данные.',409)
                entry=stack.pop();key=entry['before' if op=='undo' else 'after']
                from .model import Project
                app.project=Project.load(self.root()/(key+'.hockeyproj'));saved=storage.read(self.root()/(key+'.json'));app.index=saved['index'];app.plan=Plan.from_dict(saved['plan']) if saved['plan'] else None
                app.refresh()
                if app.plan:app.display_plan(app.plan)
                else:app.invalidate()
                app.result=None;b.checkpoint();entry['fingerprint']=self.fingerprint();h['redo' if op=='undo' else 'undo'].append(entry)
                # Earlier entries become valid again after an exact rollback.
                if h[op]:h[op][-1]['fingerprint']=self.fingerprint()
                storage.write(self.root()/'index.json',h);return dict(ok=True)
            if op=='logos':
                from .mini_export import folder
                from .logos import assign
                from .graphics import block_teams
                teams={n for block in app.project.blocks for n in block_teams(block.title) if n}
                if 'image' in data:
                    if str(data.get('team','')) not in teams:raise RemoteError('Выберите команду выпуска для нового логотипа.')
                    from .mobile_logos import save_upload
                    uploaded=save_upload(data);data={**data,'path':str(uploaded)}
                    if not app.project.logo_folder:app.project.logo_folder=str(uploaded.parent)
                elif 'folder' in data:
                    app.project.logo_folder=str(folder(data['folder']));app.project.team_logos={};assign(app.project)
                if 'team' in data:
                    name=str(data['team']);path=str(data.get('path',''))
                    if name not in teams:raise RemoteError('Команда не найдена в выпуске.')
                    if path:
                        source=Path(path)
                        folder(str(source.parent))
                        if not source.is_file() or source.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise RemoteError('Выберите изображение логотипа на сервере.')
                        from PIL import Image
                        with Image.open(source) as image:image.verify()
                    app.project.team_logos[name]=path
                label='Логотипы команд'
                if app.plan:store_plan(app.project,app.index,app.plan)
                app.refresh()
            elif op=='project':
                self.project_changes(data);label='Сценарий / настройки выпуска'
            else:
                if not app.plan:raise RemoteError('Сначала определите тайминги.')
                p=copy.deepcopy(app.plan)
                if op=='cut':p=cut_range(p,data.get('start'),data.get('end'));label='Вырезан участок речи'
                elif op=='add-insert':
                    source=next((m for m in app.project.matches if m.id==data.get('source')),None)
                    if not source:raise RemoteError('Выберите запись из проекта.')
                    from .media import probe
                    duration=probe(source.path)['duration'];start=frame(parse_time(data['start']));end=frame(parse_time(data['end']));source_in=frame(parse_time(data.get('source_in',0)))
                    p.inserts.append(Insert(source.path,start,end,source_in,source.title,source_min=0,source_max=duration));label='Добавлена видео-вставка'
                elif op=='add':
                    p.cards.append(Card(frame(parse_time(data['start'])),frame(parse_time(data['end'])),'СТАТИСТИКА',str(data.get('text','Новая плашка'))));label='Добавлена плашка'
                else:
                    kind,index=str(data['id']).split(':');items=p.cards if kind=='card' else p.inserts if kind=='insert' else [];i=int(index)
                    if not 0<=i<len(items):raise RemoteError('Элемент не найден. Обновите монтаж.')
                    item=items[i]
                    if op=='delete':items.pop(i);label='Удалён элемент монтажа'
                    elif op=='save':
                        item.start=frame(parse_time(data['start']));item.end=frame(parse_time(data['end']))
                        text=str(data.get('text','')).strip()
                        if not text or len(text)>4000:raise RemoteError('Введите текст до 4000 символов.')
                        if kind=='card':
                            card_type(item,data.get('title',item.title),str(data.get('owner','')),app.project)
                            item.text=text;item.line=-1
                            if not item.asset:
                                for field,lo,hi in [('offset_x',-1280,1280),('offset_y',-1280,1280),('scale',.25,2)]:
                                    value=float(data.get(field,getattr(item,field)))
                                    if not math.isfinite(value) or not lo<=value<=hi:raise RemoteError('Недопустимое положение или размер плашки.')
                                    setattr(item,field,value)
                            if item.title=='ПРОГНОЗ':
                                owner=str(data.get('owner',''))
                                if owner not in {x.uid for x in app.project.blocks}:raise RemoteError('Выберите разбор для ставки.')
                                item.forecast_id=owner
                                for other in p.cards:
                                    if other.forecast_id==owner:other.text=text
                            for task in p.review_items:
                                if task['id']==item.review_id:task['status']='confirmed'
                        else:
                            item.label=text;item.source_in=frame(parse_time(data.get('source_in',item.source_in)))
                            from .media import probe
                            if item.source_in+item.end-item.start>probe(item.path)['duration']+.034:raise RemoteError('Вставка выходит за конец исходного видео.')
                    else:raise RemoteError('Неизвестная правка.')
                from .review import update_task_times
                update_task_times(p);validate_plan(p);store_plan(app.project,app.index,p);app.display_plan(p)
            app.result=None;b.checkpoint();self.record(snapshot,label);b.history=None;return dict(ok=True)
        except Exception:
            if uploaded:uploaded.unlink(missing_ok=True)
            app.project,app.plan,app.index,app.result=before;app.refresh()
            if app.plan:app.display_plan(app.plan)
            raise
    def project_changes(self,data):
        app=self.app;project=app.project;structural=False
        if 'blocks' in data:
            old={x.uid:x for x in [project.intro,*project.blocks,project.outro]};rows=data['blocks']
            if len(rows)!=len(old) or {r['uid'] for r in rows}!=set(old):raise RemoteError('Состав блоков изменился. Обновите страницу.')
            order=[]
            for r in rows:
                x=old[r['uid']];title=str(r['title']).strip();script=str(r['script'])
                if not title or len(title)>200 or len(script.encode())>500000:raise RemoteError('Проверьте название и размер сценария.')
                if x.title!=title or x.script!=script:
                    structural=True;x.title=title;x.script=script;x.asr_lines=[];x.speech_key='';x.speech_cards={};x.events=[];x.event_search_key='';x.archive_pool=[]
                if x.kind=='analysis':order.append(x)
            if [x.uid for x in order]!=[x.uid for x in project.blocks]:structural=True
            project.blocks=order
        values=data.get('settings',{})
        for key,value in values.items():
            if key not in {f.name for f in fields(project.settings)}:raise RemoteError('Неизвестная настройка.')
            old=getattr(project.settings,key)
            if type(value)!=type(old) and not (type(old)==float and type(value)==int):raise RemoteError('Неверное значение настройки '+key)
            if isinstance(value,(float,int)) and not math.isfinite(value):raise RemoteError('Некорректное число.')
            if old!=value and key in ('cut_pauses','insert_frequency','auto_rotate','rotate','mirror_host','use_manual_clips','allow_other_matches'):structural=True
            setattr(project.settings,key,value)
        if 'recording_times' in data and data['recording_times']!=project.recording_times:
            from .recording_times import parse_times
            value=str(data['recording_times']);parse_times(value,len(project.blocks),allow_promos=project.profile.endswith('_shorts')) if value.strip() else None
            project.recording_times=value;structural=True
        if 'music' in data:
            music=str(data['music']).strip()
            if music and not Path(music).is_file():raise RemoteError('Музыкальный файл не найден на сервере.')
            project.music=music
        for row in data.get('matches',[]):
            m=next((x for x in project.matches if x.id==row['id']),None);box=row.get('score_box')
            if m is None:raise RemoteError('Запись не найдена.')
            if box is not None and (len(box)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in box) or not 0<=box[0]<box[2]<=1 or not 0<=box[1]<box[3]<=1):raise RemoteError('Область табло: x1,y1,x2,y2 от 0 до 1.')
            if m.score_box!=box:m.score_box=box;structural=True
        # Validate settings without requiring a finished script/source analysis.
        s=project.settings
        sizes=[(720,1280),(1080,1920)] if project.profile.endswith('_shorts') else [(1280,720),(1920,1080)]
        if not 1<=s.zoom_max<=1.4 or not 1<=s.noise_reduction<=20 or not -60<=s.music_db<=-15 or s.rotate not in (0,90,180,270) or s.insert_frequency not in ('low','normal','high') or (s.width,s.height) not in sizes or s.fps!=30:raise RemoteError('Проверьте настройки изображения и звука.')
        if structural:
            for x in [project.intro,*project.blocks,project.outro]:x.edit_plan=None;x.edit_key=''
            project.episode_plan=None;project.episode_key='';app.invalidate()
        elif app.plan:store_plan(project,app.index,app.plan)
        app.refresh()
