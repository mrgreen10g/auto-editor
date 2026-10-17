"""Listen, correct, confirm, delete and revisit speech review tasks without ASR."""
import copy
import os
import queue
import threading
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from .timeline import format_time,parse_time,Card
from .editing import EditHistory
from .review import resolve,pending,update_task_times,source_time
from .media import run,Cancelled


class ReviewDialog:
    def __init__(self,parent,project,plan,cache,on_apply):
        self.project=project;self.history=EditHistory(plan);self.cache=Path(cache)/'speech-review'
        self.cache.mkdir(parents=True,exist_ok=True);self.on_apply=on_apply
        self.cancel=threading.Event();self.jobs=queue.Queue();self.closed=False;self.busy=False
        self.window=w=tk.Toplevel(parent);w.title('Ручная проверка речи и плашек')
        width=min(1120,w.winfo_screenwidth()-40);height=min(820,w.winfo_screenheight()-110)
        w.geometry(f'{width}x{height}+10+20');w.minsize(min(640,width),min(360,height));w.transient(parent)
        w.columnconfigure(0,weight=1);w.rowconfigure(2,weight=1)
        w.protocol('WM_DELETE_WINDOW',self.close)
        self.status=tk.StringVar();status_label=ttk.Label(w,textvariable=self.status,wraplength=1000)
        status_label.grid(row=0,column=0,sticky='ew',padx=12,pady=6)
        self.show_all=tk.BooleanVar(value=False)
        ttk.Checkbutton(w,text='Показать также проверенные и удалённые',variable=self.show_all,command=self.refresh).grid(row=1,column=0,sticky='w',padx=12)
        body=ttk.Panedwindow(w,orient='horizontal');body.grid(row=2,column=0,sticky='nsew',padx=12,pady=6)
        from .ui import ScrollPage
        left=ttk.Frame(body);self.details=ScrollPage(body);right=self.details.content
        body.add(left,weight=1);body.add(self.details,weight=2)
        self.table=ttk.Treeview(left,columns=('time','kind','state','text'),show='headings',height=16)
        for key,title,width in [('time','Время',75),('kind','Тип плашки',155),('state','Решение',75),('text','Текст',180)]:
            self.table.heading(key,text=title);self.table.column(key,width=width)
        scroll=ttk.Scrollbar(left,orient='vertical',command=self.table.yview);self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.table.pack(fill='both',expand=True);self.table.bind('<<TreeviewSelect>>',self.select)
        self.reason=tk.StringVar();reason_label=ttk.Label(right,textvariable=self.reason,wraplength=550);reason_label.pack(fill='x')
        self.script=tk.Text(right,height=4,wrap='word');ttk.Label(right,text='Сценарий').pack(anchor='w');self.script.pack(fill='x')
        self.heard=tk.Text(right,height=3,wrap='word');ttk.Label(right,text='Распознано · можно исправить для этой проверки').pack(anchor='w');self.heard.pack(fill='x')
        self.text=tk.Text(right,height=4,wrap='word');ttk.Label(right,text='Текст плашки в видео').pack(anchor='w');self.text.pack(fill='x')
        times=ttk.Frame(right);times.pack(fill='x',pady=6)
        self.start=tk.StringVar();self.end=tk.StringVar()
        for label,var in [('Начало на дорожке',self.start),('Конец на дорожке',self.end)]:
            f=ttk.Frame(times);f.pack(side='left',fill='x',expand=True);ttk.Label(f,text=label).pack(anchor='w');ttk.Entry(f,textvariable=var,width=15).pack(anchor='w')
        self.original=tk.StringVar();ttk.Label(right,textvariable=self.original).pack(anchor='w')
        self.owners=[('', 'Не прогноз')]+[(b.uid,b.title) for b in project.blocks]
        ttk.Label(right,text='Прогноз относится к матчу').pack(anchor='w',pady=(6,0))
        self.owner=ttk.Combobox(right,state='readonly',values=[x[1] for x in self.owners]);self.owner.pack(fill='x')
        actions=ttk.Frame(right);actions.pack(fill='x',pady=8)
        ttk.Button(actions,text='▶ Прослушать участок',command=self.listen).grid(row=0,column=0,sticky='ew')
        ttk.Button(actions,text='■ Стоп',command=self.stop).grid(row=0,column=1,sticky='ew')
        if project.profile.startswith('uz_'):
            ttk.Button(actions,text='Перевод на русский',command=self.translate).grid(row=1,column=0,columnspan=2,sticky='ew',pady=(4,0))
        help_label=ttk.Label(right,text='Звук читается из исходников: пересборка видео не нужна. Время плашек указано на монтажной дорожке.',wraplength=550);help_label.pack(fill='x')
        right.bind('<Configure>',lambda e:[label.configure(wraplength=max(150,e.width-20)) for label in (reason_label,help_label)],add='+')
        # A non-expanding grid row reserves action space even when the form is taller
        # than a remote desktop. Never put these controls inside the scrolled form.
        self.footer=bottom=ttk.Frame(w);bottom.grid(row=3,column=0,sticky='ew',padx=12,pady=8)
        self.action_buttons=[]
        for title,command in [('Подтвердить и далее',lambda:self.decide('confirmed')),('Удалить плашку',lambda:self.decide('deleted')),('Вернуть на проверку',lambda:self.decide('pending')),('Отменить решение',self.undo),('Закрыть',self.close)]:
            button=ttk.Button(bottom,text=title,command=command)
            self.action_buttons.append(button)
        self.footer_columns=0
        def layout(event):
            if event.widget is not w:return
            status_label.configure(wraplength=max(200,event.width-24))
            columns=max(1,min(3,(event.width-24)//max(230,max(b.winfo_reqwidth()+8 for b in self.action_buttons))))
            if columns!=self.footer_columns:
                self.footer_columns=columns
                for i in range(3):bottom.columnconfigure(i,weight=1 if i<columns else 0)
                for i,button in enumerate(self.action_buttons):button.grid(row=i//columns,column=i%columns,sticky='ew',padx=3,pady=3)
        w.bind('<Configure>',layout,add='+')
        # A balanced initial sash keeps the form reachable on small desktops.
        w.after_idle(lambda:body.sashpos(0,max(180,int(body.winfo_width()*.36))) if w.winfo_exists() else None)
        def wheel(event):
            widget=event.widget
            while widget is not None:
                if widget is self.details:
                    if not isinstance(event.widget,tk.Text):self.details.scroll(-1 if event.delta>0 else 1);return 'break'
                    return
                widget=getattr(widget,'master',None)
        w.bind('<MouseWheel>',wheel,add='+')
        self.refresh();self.poll_id=w.after(80,self.poll);w.grab_set()

    @property
    def plan(self):return self.history.plan

    def selected(self):
        ids=self.table.selection()
        return next((x for x in self.plan.review_items if ids and x['id']==ids[0]),None)

    def refresh(self):
        update_task_times(self.plan)
        self.table.delete(*self.table.get_children());cards={c.review_id:c for c in self.plan.cards}
        labels={'pending':'Проверить','confirmed':'Оставить','deleted':'Удалено'}
        for task in self.plan.review_items:
            if task['status']!='pending' and not self.show_all.get():continue
            card=cards.get(task['id']);title=card.text if card else task['script']
            from .review import describe_card
            kind,_=describe_card(card,task,self.project,self.plan)
            self.table.insert('','end',iid=task['id'],values=(format_time(task['start']),kind,labels[task['status']],title.replace('\n',' ')))
        self.status.set(f'Осталось проверить: {len(pending(self.plan))}. Решения применяются к проекту сразу; сохраните проект перед закрытием программы.')
        ids=self.table.get_children()
        if ids:self.table.selection_set(ids[0]);self.select()
        else:self.reason.set('Все спорные плашки проверены. Можно собирать видео.');self.status.set('Проверка завершена. Решения применены.')

    def select(self,event=None):
        task=self.selected()
        if not task:return
        card=next((c for c in self.plan.cards if c.review_id==task['id']),None)
        if card is None and task.get('deleted_card'):card=Card(**task['deleted_card'])
        from .review import describe_card
        kind,where=describe_card(card,task,self.project,self.plan)
        self.reason.set(kind+' · '+where+'\n'+task['reason'])
        from .review import heard_context
        heard=task.get('recognized','') or heard_context(self.plan,task['start'],task['end'])
        for box,value in [(self.script,task['script']),(self.heard,heard),(self.text,card.text if card else '')]:
            box.configure(state='normal');box.delete('1.0','end');box.insert('1.0',value)
        self.script.configure(state='disabled')
        self.start.set(format_time(card.start if card else task['start']));self.end.set(format_time(card.end if card else task['end']))
        self.original.set('В исходной записи: '+format_time(source_time(self.plan,task['start']))+'–'+format_time(source_time(self.plan,task['end'])))
        self.owner.current(next((i for i,(uid,_) in enumerate(self.owners) if card and uid==card.forecast_id),0))
        self.owner.configure(state='readonly' if card and card.title=='ПРОГНОЗ' else 'disabled')

    def decide(self,status):
        task=self.selected()
        if not task:return
        try:
            p=resolve(self.plan,task['id'],status,text=self.text.get('1.0','end').strip(),start=parse_time(self.start.get()),end=parse_time(self.end.get()),owner=self.owners[max(0,self.owner.current())][0])
            next(x for x in p.review_items if x['id']==task['id'])['recognized']=self.heard.get('1.0','end').strip()
            self.history.replace(p);self.on_apply(copy.deepcopy(self.plan));self.refresh()
        except (ValueError,StopIteration) as error:messagebox.showerror('Проверьте правку',str(error),parent=self.window)

    def undo(self):
        if self.history.undo():self.on_apply(copy.deepcopy(self.plan));self.refresh()

    def translate(self):
        if not self.selected():return
        from .review_translation import show
        show(self.window, tuple(box.get('1.0','end').strip() for box in (self.script,self.heard,self.text)), self.cache)

    def listen(self):
        if self.busy:return
        try:
            a=max(0,parse_time(self.start.get())-.8);b=min(self.plan.duration,parse_time(self.end.get())+.8)
            if b<=a:raise ValueError('Конец должен быть позже начала.')
        except ValueError as error:self.status.set(str(error));return
        from .host_media import slice_media
        media=self.plan.media or [{'path':self.project.host,'start':self.plan.source_start+x,'end':self.plan.source_start+y} for x,y in self.plan.keep]
        spans=slice_media(media,a,b);self.cancel.clear();self.busy=True;self.status.set('Готовлю звук выбранного участка…')
        target=self.cache/(uuid.uuid4().hex+'.wav')
        def work():
            try:
                args=['-y'];filters=[]
                for i,m in enumerate(spans):
                    args+=['-ss',m['start'],'-t',m['end']-m['start'],'-i',m['path']]
                    filters.append(f'[{i}:a]aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono,asetpts=PTS-STARTPTS[a{i}]')
                filters.append(''.join(f'[a{i}]' for i in range(len(spans)))+f'concat=n={len(spans)}:v=0:a=1[out]')
                run(args+['-filter_complex',';'.join(filters),'-map','[out]','-c:a','pcm_s16le',target],self.cancel)
                if not self.cancel.is_set():self.jobs.put(('audio',target))
            except Cancelled:pass
            except Exception as error:self.jobs.put(('error',str(error)))
            finally:self.jobs.put(('done',None))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,value=self.jobs.get_nowait()
                if kind=='audio' and not self.cancel.is_set():
                    if os.name=='nt':
                        import winsound
                        winsound.PlaySound(str(value),winsound.SND_FILENAME|winsound.SND_ASYNC)
                        self.status.set('Воспроизведение исходного звука. Плашка не меняет речь ведущего.')
                    else:self.status.set('Встроенное прослушивание доступно в Windows-сборке.')
                elif kind=='error':self.status.set(value)
                elif kind=='done':self.busy=False
        except queue.Empty:pass
        if not self.closed:self.poll_id=self.window.after(80,self.poll)

    def stop(self):
        self.cancel.set()
        if os.name=='nt':
            import winsound
            winsound.PlaySound(None,0)

    def close(self):
        self.stop();self.closed=True;self.window.after_cancel(self.poll_id);self.window.destroy()
