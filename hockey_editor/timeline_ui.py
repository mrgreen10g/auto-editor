"""Editable video/card lanes, undo/redo and a rendered in-app audiovisual preview."""
import copy
import json
import queue
import threading
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from . import ui
from .editing import EditHistory,store_plan
from .timeline import Insert,Card,frame
from .preview import PreviewPlayer
from .engine import Engine
from .media import run,Cancelled
from .goals import scan_root,source_signature


class TimelineEditor:
    def __init__(self,app):
        self.app=app;self.history=EditHistory(app.plan)
        self.project=copy.deepcopy(app.project);self.index=app.index
        self.selected=None;self.cursor=0.;self.drag=None;self.dirty=False
        self.busy=False;self.closing=False;self.closed=False;self.preview_current=False
        self.cancel=threading.Event();self.jobs=queue.Queue();self.worker=None
        self.window=tk.Toplevel(app.root);w=self.window
        w.title('Монтажная дорожка · Auto Editor')
        w.geometry(f'{min(1180,w.winfo_screenwidth()-50)}x{min(900,w.winfo_screenheight()-80)}')
        w.minsize(920,650);w.configure(bg=ui.BG);w.transient(app.root)
        w.protocol('WM_DELETE_WINDOW',self.close)
        self.status=tk.StringVar(value='Выберите элемент. Перетаскивайте середину для сдвига, края — для обрезки.')
        top=ttk.Frame(w,padding=10);top.pack(fill='x')
        self.buttons=[]
        def button(parent,text,command):
            b=ttk.Button(parent,text=text,command=command);b.pack(side='left',padx=3);self.buttons.append(b);return b
        button(top,'↶ Отменить',self.undo);button(top,'↷ Повторить',self.redo)
        button(top,'+ Игра',lambda:self.pick_clip(True));button(top,'+ Плашка',self.add_card)
        button(top,'Удалить',self.delete)
        self.build_button=button(top,'Собрать предпросмотр',self.build_preview)
        self.cancel_button=ttk.Button(top,text='Остановить',command=self.cancel.set,state='disabled');self.cancel_button.pack(side='right')
        upper=ttk.Frame(w,padding=(12,0));upper.pack(fill='both',expand=True)
        left=ttk.Frame(upper);left.pack(side='left',fill='both',expand=True)
        self.screen=ttk.Label(left,text='Здесь появится видео со звуком, переходами и плашками.\nНажмите «Собрать предпросмотр».',anchor='center')
        self.screen.pack(fill='both',expand=True)
        self.player=PreviewPlayer(self.screen,self.position_changed,lambda e:self.status.set('Предпросмотр: '+e))
        playbar=ttk.Frame(left);playbar.pack(fill='x')
        self.play_button=ttk.Button(playbar,text='▶ / ❚❚',command=self.player.toggle);self.play_button.pack(side='left')
        self.seekvar=tk.DoubleVar()
        self.seekbar=ttk.Scale(playbar,from_=0,to=self.plan.duration,variable=self.seekvar)
        self.seekbar.pack(side='left',fill='x',expand=True,padx=8)
        self.seekbar.bind('<ButtonRelease-1>',lambda _:self.seek(self.seekvar.get()))
        self.clock=ttk.Label(playbar,text='00:00');self.clock.pack(side='right')
        inspector=ttk.Frame(upper,padding=(14,0,0,0),width=260);inspector.pack(side='right',fill='y');inspector.pack_propagate(False)
        ttk.Label(inspector,text='Выбранный элемент',style='CardTitle.TLabel').pack(anchor='w',pady=8)
        self.kind=tk.StringVar(value='Не выбран');ttk.Label(inspector,textvariable=self.kind,wraplength=240).pack(anchor='w')
        self.fields=[]
        for text in ('Начало на дорожке, с','Конец на дорожке, с','Начало в исходнике, с'):
            ttk.Label(inspector,text=text).pack(anchor='w',pady=(8,2))
            var=tk.StringVar();entry=ttk.Entry(inspector,textvariable=var);entry.pack(fill='x');self.fields.append((var,entry))
        ttk.Label(inspector,text='Текст плашки / подпись в редакторе').pack(anchor='w',pady=(8,2))
        self.text=tk.Text(inspector,height=4,wrap='word',font=('Segoe UI',10));self.text.pack(fill='x')
        self.apply_button=ttk.Button(inspector,text='Применить правку',command=self.edit);self.apply_button.pack(fill='x',pady=6);self.buttons.append(self.apply_button)
        b=ttk.Button(inspector,text='Заменить игровой момент',command=self.pick_clip);b.pack(fill='x');self.buttons.append(b)
        ttk.Label(inspector,text='Речь остаётся синхронной. Изменяются игровые вставки и плашки. Правки сохраняются в проекте.',wraplength=240,style='Muted.TLabel').pack(anchor='w',pady=10)
        area=ttk.Frame(w,padding=(12,8));area.pack(fill='x')
        self.canvas=tk.Canvas(area,height=155,bg='#142334',highlightthickness=0)
        self.canvas.pack(fill='x')
        bar=ttk.Scrollbar(area,orient='horizontal',command=self.canvas.xview);bar.pack(fill='x');self.canvas.configure(xscrollcommand=bar.set)
        self.scale=max(7,min(24,1000/self.plan.duration));self.offset=95
        self.canvas.bind('<Button-1>',self.down);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.up)
        bottom=ttk.Frame(w,padding=(12,0,12,10));bottom.pack(fill='x')
        label=ttk.Label(bottom,textvariable=self.status,wraplength=720,style='Muted.TLabel');label.pack(side='left',fill='x',expand=True)
        button(bottom,'Применить к проекту',self.apply)
        self.draw();self.poll_id=w.after(80,self.poll);w.grab_set()
        w.bind('<Control-z>',lambda _:self.undo());w.bind('<Control-y>',lambda _:self.redo())

    @property
    def plan(self):return self.history.plan

    def draw(self,plan=None):
        plan=plan or self.plan;c=self.canvas;c.delete('all')
        width=self.offset+plan.duration*self.scale+25;c.configure(scrollregion=(0,0,width,155))
        for t in range(0,int(plan.duration)+1,5):
            x=self.offset+t*self.scale;c.create_line(x,22,x,152,fill='#304359')
            c.create_text(x,11,text=ui.timecode(t),fill='#a9bbce',font=('Segoe UI',8))
        for y,text in ((43,'Речь'),(88,'Игра'),(132,'Плашки')):
            c.create_text(8,y,text=text,fill='#dce7f1',anchor='w',font=('Segoe UI',10))
        c.create_rectangle(self.offset,28,width-25,59,fill='#304c66',outline='')
        c.create_text(self.offset+8,43,text='Ведущий · голос',anchor='w',fill='#e0ebf5')
        for name,items,y,color in (('insert',plan.inserts,68,'#238f94'),('card',plan.cards,112,'#a87835')):
            for i,item in enumerate(items):
                x1=self.offset+item.start*self.scale;x2=self.offset+item.end*self.scale
                tag=f'{name}:{i}';selected=self.selected==(name,i)
                c.create_rectangle(x1,y,x2,y+31,fill=color,outline='#fff' if selected else '',width=2,tags=(tag,))
                text=item.label if name=='insert' else item.text
                room=max(0,int((x2-x1-8)/7))
                c.create_text(x1+4,y+15,text=text.replace('\n',' ')[:room],anchor='w',fill='white',font=('Segoe UI',8),tags=(tag,))
                if selected:
                    for x in (x1+3,x2-3):c.create_line(x,y+5,x,y+26,fill='white',width=2,tags=(tag,))
        x=self.offset+self.cursor*self.scale;c.create_line(x,20,x,152,fill='#fa7373',width=2,tags=('cursor',))

    def item(self,plan=None):
        if self.selected is None:return None
        name,i=self.selected;items=(plan or self.plan).inserts if name=='insert' else (plan or self.plan).cards
        return items[i] if i<len(items) else None

    def select(self,selected):
        self.selected=selected;item=self.item()
        self.text.delete('1.0','end')
        if item:
            self.kind.set(('Игра · '+Path(item.path).name) if selected[0]=='insert' else item.title)
            for (var,_),value in zip(self.fields,(item.start,item.end,getattr(item,'source_in',0))):var.set(f'{value:.2f}')
            self.text.insert('1.0',item.label if selected[0]=='insert' else item.text)
            self.fields[2][1].configure(state='normal' if selected[0]=='insert' else 'disabled')
            if getattr(item,'context_label',''):self.status.set(item.context_label+' · только в редакторе, не в видео')
        else:self.kind.set('Не выбран')
        self.draw()

    def position_changed(self,t):
        self.cursor=t;self.seekvar.set(t);self.clock.configure(text=ui.timecode(t));self.draw()

    def seek(self,t):
        self.cursor=max(0,min(self.plan.duration,t));self.position_changed(self.cursor)
        if self.preview_current:self.player.seek(self.cursor)
        else:self.status.set('После правок соберите новый предпросмотр. Курсор используется для добавления элементов.')

    def down(self,event):
        if self.busy:return
        x=self.canvas.canvasx(event.x);tags=self.canvas.gettags('current')
        tag=next((v for v in tags if v.startswith(('insert:','card:'))),None)
        if not tag:self.seek((x-self.offset)/self.scale);return
        name,i=tag.split(':');self.select((name,int(i)));item=self.item()
        lo=self.offset+item.start*self.scale;hi=self.offset+item.end*self.scale
        mode='left' if abs(x-lo)<7 else 'right' if abs(x-hi)<7 else 'move'
        self.drag=(x,mode,copy.deepcopy(self.plan))

    def dragged(self,x):
        initial,mode,original=self.drag;plan=copy.deepcopy(original);item=self.item(plan)
        delta=frame((x-initial)/self.scale)
        if mode=='move':
            delta=max(-item.start,min(delta,plan.duration-item.end));item.start+=delta;item.end+=delta
        elif mode=='left':
            delta=max(-item.start,min(delta,item.end-item.start-.2));item.start+=delta
            if self.selected[0]=='insert':item.source_in+=delta
        else:item.end=frame(max(item.start+.2,min(plan.duration,item.end+delta)))
        return plan

    def motion(self,event):
        if self.drag and not self.busy:self.draw(self.dragged(self.canvas.canvasx(event.x)))

    def up(self,event):
        if self.drag and not self.busy:
            plan=self.dragged(self.canvas.canvasx(event.x));self.drag=None;self.change(plan)

    def change(self,plan):
        try:self.history.replace(plan)
        except Exception as error:
            self.status.set(str(error));self.draw();return False
        self.dirty=True;self.preview_current=False;self.player.stop()
        self.status.set('Правки внесены. Соберите предпросмотр, затем примените дорожку к проекту.')
        self.select(self.selected);return True

    def edit(self):
        if self.busy or self.item() is None:return
        plan=copy.deepcopy(self.plan);item=self.item(plan)
        try:
            start,end,source=[float(var.get().replace(',','.')) for var,_ in self.fields]
            item.start=frame(start);item.end=frame(end)
            text=self.text.get('1.0','end').strip()
            if self.selected[0]=='insert':item.source_in=frame(source);item.label=text
            else:item.text=text
            self.change(plan)
        except ValueError as error:self.status.set('Проверьте числа и текст: '+str(error))

    def delete(self):
        if self.busy or not self.selected:return
        plan=copy.deepcopy(self.plan);name,i=self.selected
        (plan.inserts if name=='insert' else plan.cards).pop(i);self.selected=None;self.change(plan)

    def undo(self):
        if not self.busy and self.history.undo():self.after_history()
    def redo(self):
        if not self.busy and self.history.redo():self.after_history()
    def after_history(self):
        self.selected=None;self.dirty=True;self.preview_current=False;self.player.stop();self.select(None)
        self.status.set('Дорожка изменена. Предпросмотр нужно обновить.')

    def add_card(self):
        if self.busy:return
        value=simpledialog.askstring('Новая плашка','Краткий текст:',parent=self.window)
        if not value:return
        plan=copy.deepcopy(self.plan);start=min(self.cursor,max(0,plan.duration-.3))
        plan.cards.append(Card(start,min(start+5,plan.duration),'ИНФОРМАЦИЯ',value))
        self.selected=('card',len(plan.cards)-1);self.change(plan)

    def pick_clip(self,add=False):
        if self.busy:return
        if not add and (not self.selected or self.selected[0]!='insert'):
            self.status.set('Выберите игровую вставку на дорожке или нажмите «+ Игра».');return
        sources=[m for m in self.project.matches if m.id in self.project.blocks[self.index].match_ids and Path(m.path).is_file()]
        choices=[]
        for source in sources:
            data=self.app.scans.get(source.id)
            if not data:
                signature=source_signature(source);path=scan_root()/signature[:24]/'goals.json'
                if path.exists():data=json.loads(path.read_text(encoding='utf-8'))
            for c in (data or {}).get('candidates',[]):
                if c['end']-c['start']>=.5:choices.append((source,c))
        if not choices:
            self.status.set('Сначала выполните «Найти голы» в исходных матчах, затем откройте дорожку.');return
        dialog=tk.Toplevel(self.window);dialog.title('Выбрать игровой момент');dialog.geometry('820x460');dialog.transient(self.window);dialog.grab_set()
        table=ui.table(dialog,[('source','Матч',270),('score','Счёт / игра',140),('time','В исходнике',150)],12)
        for i,(source,c) in enumerate(choices):
            score=':'.join(map(str,c['score'])) if c.get('score') else 'Игра'
            table.insert('','end',iid=str(i),values=(source.title,score,f'{ui.timecode(c["start"])}–{ui.timecode(c["end"])}'))
        def use():
            if not table.selection():return
            source,c=choices[int(table.selection()[0])];plan=copy.deepcopy(self.plan)
            if add:
                start=frame(self.cursor);end=min(plan.duration,start+5)
                following=[v.start for v in plan.inserts if v.start>=start]
                if following:end=min(end,min(following))
            else:old=self.item();start,end=old.start,old.end
            end=min(end,start+c['end']-c['start'])
            length=end-start;source_in=max(c['start'],min(c['time']-length*.6,c['end']-length))
            clip=Insert(source.path,start,frame(end),source_in,source.title,'',c['start'],c['end'])
            if add:plan.inserts.append(clip);self.selected=None
            else:plan.inserts[self.selected[1]]=clip
            if self.change(plan):dialog.destroy();self.window.grab_set()
        ttk.Button(dialog,text='Использовать',command=use).pack(pady=12)
        table.bind('<Double-1>',lambda _:use())
        dialog.protocol('WM_DELETE_WINDOW',lambda:(dialog.destroy(),self.window.grab_set()))

    def apply(self):
        if self.busy:return
        try:
            store_plan(self.app.project,self.index,self.plan)
            self.app.display_plan(copy.deepcopy(self.plan));self.app.result=None
            self.app.previewbutton.configure(state='disabled');self.app.folderbutton.configure(state='disabled')
            self.app.output_label.set('Монтажная дорожка изменена. Экспорт создаст новый ролик.')
            self.dirty=False;self.status.set('Дорожка применена. Сохраните проект через Ctrl+S в основном окне.')
        except Exception as error:messagebox.showerror('Дорожка',str(error),parent=self.window)

    def build_preview(self):
        if self.busy:return
        self.player.stop();self.busy=True;self.cancel.clear();self.preview_current=False
        for b in self.buttons:b.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('Собираю полный предпросмотр 640×360 со звуком. Это может занять несколько минут.')
        project=copy.deepcopy(self.project);plan=copy.deepcopy(self.plan)
        root=self.app.cache_path()/'timeline-preview';root.mkdir(parents=True,exist_ok=True)
        target=root/f'preview-{uuid.uuid4().hex[:10]}.mp4';audio=target.with_suffix('.wav')
        def work():
            try:
                Engine(project,self.index,root,self.cancel,lambda s:self.jobs.put(('log',s))).render(plan,target,draft=True)
                run(['-y','-i',target,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',audio],self.cancel)
                self.jobs.put(('ready',(target,audio,plan.duration)))
            except Cancelled:self.jobs.put(('log','Сборка предпросмотра остановлена. Правки сохранены в окне.'))
            except Exception as error:self.jobs.put(('log','Предпросмотр не собран: '+str(error)))
            finally:self.jobs.put(('done',None))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()

    def poll(self):
        if self.closed:return
        try:
            while True:
                kind,value=self.jobs.get_nowait()
                if kind=='log':self.status.set(value)
                elif kind=='ready' and not self.closing:
                    self.preview_current=True;self.player.load(*value);self.status.set('Предпросмотр готов. Нажмите ▶ или выберите время на дорожке.')
                elif kind=='done':
                    self.busy=False
                    for b in self.buttons:b.configure(state='normal')
                    self.cancel_button.configure(state='disabled')
                    if self.closing:self.closing=False;self.close();return
        except queue.Empty:pass
        self.poll_id=self.window.after(80,self.poll)

    def close(self):
        if self.busy:
            self.closing=True;self.cancel.set();self.status.set('Останавливаю подготовку предпросмотра…');return
        if self.dirty:
            answer=messagebox.askyesnocancel('Правки дорожки','Применить правки к проекту перед закрытием?',parent=self.window)
            if answer is None:return
            if answer:self.apply()
        self.closed=True;self.player.close();self.window.after_cancel(self.poll_id);self.window.grab_release();self.window.destroy()
