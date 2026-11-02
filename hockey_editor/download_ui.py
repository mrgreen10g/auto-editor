"""Independent desktop YouTube queue with stable row identities."""
import queue,threading,uuid,unicodedata
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .mobile_downloads import canonical,youtube_download
from .mini_export import filename
from . import ui

def clean_title(value):
    # Clipboard titles may contain line separators, bidi controls and zero-width marks.
    return ''.join(' ' if ch.isspace() else ch for ch in str(value)
                   if ch.isspace() or unicodedata.category(ch) not in ('Cc','Cf'))

class Cancellation:
    def __init__(self,*events):self.events=events
    def is_set(self):return any(e.is_set() for e in self.events)

class Downloads:
    def __init__(self,app):
        self.app=app;self.rows=[];self.messages=queue.Queue();self.running=False;self.cancel=threading.Event()
        page=ttk.Frame(app.deck);page.grid(row=0,column=0,sticky='nsew');app.pages['downloads']=page;self.page=page
        toolbar=ttk.Frame(page,padding=(0,0,0,12));toolbar.pack(fill='x')
        self.add_button=ttk.Button(toolbar,text='+ Добавить видео',command=self.add);self.add_button.pack(side='left')
        ttk.Button(toolbar,text='Скачать очередь',command=self.start).pack(side='left',padx=8)
        ttk.Button(toolbar,text='Остановить скачивание',command=self.cancel.set).pack(side='left')
        self.summary=tk.StringVar();ttk.Label(page,textvariable=self.summary).pack(anchor='w',pady=(0,6))
        self.scroller=ui.ScrollPage(page);self.scroller.pack(fill='both',expand=True);page.scroll=self.scroller.scroll
        self.container=self.scroller.content
        self.add();self.poll()
    def renumber(self):
        for i,row in enumerate(self.rows):row['frame'].configure(text=f'Видео {i+1}')
    def add(self):
        frame=ttk.LabelFrame(self.container,padding=12);frame.pack(fill='x',pady=8)
        row={'id':uuid.uuid4().hex,'frame':frame,'url':tk.StringVar(),'name':tk.StringVar(),'folder':tk.StringVar(),'state':tk.StringVar(value='Ожидает запуска'),'done':False,'cancel':threading.Event(),'widgets':[]}
        ttk.Button(frame,text='Удалить блок',command=lambda:self.remove(row)).pack(anchor='e')
        for key,label in [('url','Ссылка YouTube'),('name','Название файла'),('folder','Папка сохранения')]:
            ttk.Label(frame,text=label).pack(anchor='w');entry=ttk.Entry(frame,textvariable=row[key]);entry.pack(fill='x');row['widgets'].append(entry)
            if key=='name':
                variable=row[key]
                def normalize(*_,var=variable):
                    raw=var.get();clean=clean_title(raw)
                    if clean!=raw:var.set(clean)
                variable.trace_add('write',normalize)
                def paste(event,field=entry):
                    try:text=clean_title(field.clipboard_get())
                    except tk.TclError:return 'break'
                    if field.selection_present():
                        start=field.index('sel.first');field.delete('sel.first','sel.last');field.icursor(start)
                    field.insert('insert',text)
                    return 'break'
                entry.bind('<<Paste>>',paste)
        def browse():
            path=filedialog.askdirectory(parent=self.app.root,title='Куда скачать видео')
            if path:row['folder'].set(path)
        button=ttk.Button(frame,text='Выбрать папку…',command=browse);button.pack(anchor='w',pady=4);row['widgets'].append(button)
        row['bar']=ttk.Progressbar(frame,maximum=100);row['bar'].pack(fill='x');ttk.Label(frame,textvariable=row['state'],wraplength=700).pack(anchor='w')
        self.rows.append(row);self.renumber();return row
    def remove(self,row,ensure=True):
        if row not in self.rows:return
        row['cancel'].set();self.rows.remove(row);row['frame'].destroy();self.renumber()
        if ensure and not self.rows:self.add()
    def start(self):
        if self.running:return
        jobs=[];targets=set()
        try:
            for number,row in enumerate(self.rows,1):
                if row['done'] or not row['url'].get().strip():continue
                source,url=canonical(row['url'].get())
                if source!='youtube':raise ValueError('В этой вкладке нужны ссылки YouTube.')
                folder=Path(row['folder'].get())
                if not row['folder'].get().strip() or not folder.is_dir():raise ValueError('Выберите папку сохранения.')
                row['name'].set(clean_title(row['name'].get()))
                target=folder/filename(row['name'].get())
                if target.exists() or str(target.resolve()).casefold() in targets:raise ValueError('Имя уже занято: '+str(target))
                targets.add(str(target.resolve()).casefold());jobs.append((row['id'],url,target,row['cancel']))
        except Exception as e:messagebox.showerror('Скачивание',f'Видео {number}: {e}',parent=self.app.root);return
        if not jobs:return
        self.running=True;self.cancel.clear();self.summary.set('Идёт скачивание…')
        ids={j[0] for j in jobs}
        for row in self.rows:
            if row['id'] in ids:
                row['cancel'].clear();row['state'].set('В очереди')
                for widget in row['widgets']:widget.configure(state='disabled')
        def worker():
            try:
                for ident,url,target,row_cancel in jobs:
                    if self.cancel.is_set():break
                    if row_cancel.is_set():continue
                    cancel=Cancellation(self.cancel,row_cancel);partial=target.parent/('.autoeditor-'+uuid.uuid4().hex+'.mp4');created=False
                    try:
                        self.messages.put((ident,0,'Скачиваю…',False))
                        def update(**data):
                            size=data.get('size',0);received=data.get('received',0)
                            self.messages.put((ident,min(99,received/size*100) if size else 0,data.get('message','Собираю видео…'),False))
                        youtube_download({'source':'youtube','url':url},partial,update,cancel)
                        if cancel.is_set():raise InterruptedError()
                        with target.open('xb') as out:
                            created=True
                            with partial.open('rb') as inp:
                                while chunk:=inp.read(1024*1024):
                                    if cancel.is_set():raise InterruptedError()
                                    out.write(chunk)
                        self.messages.put((ident,100,'Готово',True));created=False
                    except InterruptedError:self.messages.put((ident,0,'Остановлено',False))
                    except Exception as e:self.messages.put((ident,0,str(e),False))
                    finally:
                        if created:target.unlink(missing_ok=True)
                        for file in partial.parent.glob(partial.name+'*'):
                            if file.is_file():file.unlink(missing_ok=True)
            finally:self.messages.put((None,0,'',False))
        threading.Thread(target=worker,daemon=True).start()
    def finish(self):
        self.running=False;done=sum(row['done'] for row in self.rows)
        for row in self.rows[:]:
            if row['done']:self.remove(row,ensure=False)
            else:
                for widget in row['widgets']:widget.configure(state='normal')
                if row['state'].get()=='В очереди':row['state'].set('Ожидает запуска')
        if not any(any(row[k].get().strip() for k in ('url','name','folder')) for row in self.rows):
            for row in self.rows[:]:self.remove(row,ensure=False)
        if not self.rows:self.add()
        self.summary.set(f'Скачано: {done}. Можно добавить следующие видео.' if done else 'Очередь остановлена или завершилась с ошибкой.')
        self.scroller.canvas.yview_moveto(0)
    def poll(self):
        while True:
            try:ident,value,text,done=self.messages.get_nowait()
            except queue.Empty:break
            if ident is None:self.finish();continue
            row=next((r for r in self.rows if r['id']==ident),None)
            if row is None:continue
            row['bar']['value']=value;row['state'].set(text);row['done']=done
        self.app.root.after(150,self.poll)
