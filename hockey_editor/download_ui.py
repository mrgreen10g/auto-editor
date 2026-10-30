"""Independent desktop YouTube queue; never shares the montage worker."""
import queue,threading,uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .mobile_downloads import canonical,youtube_download
from .mini_export import filename

class Downloads:
    def __init__(self,app):
        self.app=app;self.rows=[];self.messages=queue.Queue();self.running=False;self.cancel=threading.Event()
        page=app.scrollable('downloads');self.page=page
        ttk.Label(page,text='Очередь работает независимо от поиска кадров и рендера.').pack(anchor='w',pady=8)
        ttk.Button(page,text='+ Добавить видео',command=self.add).pack(anchor='w')
        self.container=ttk.Frame(page);self.container.pack(fill='both',expand=True)
        ttk.Button(page,text='Скачать очередь',command=self.start).pack(anchor='w',pady=12)
        ttk.Button(page,text='Остановить скачивание',command=self.cancel.set).pack(anchor='w')
        self.add();self.poll()
    def add(self):
        frame=ttk.LabelFrame(self.container,text=f'Видео {len(self.rows)+1}',padding=12);frame.pack(fill='x',pady=8)
        row={'url':tk.StringVar(),'name':tk.StringVar(),'folder':tk.StringVar(),'state':tk.StringVar(value='Ожидает запуска'),'done':False}
        for key,label in [('url','Ссылка YouTube'),('name','Название файла'),('folder','Папка сохранения')]:
            ttk.Label(frame,text=label).pack(anchor='w');ttk.Entry(frame,textvariable=row[key]).pack(fill='x')
        def browse():
            path=filedialog.askdirectory(parent=self.app.root,title='Куда скачать видео')
            if path:row['folder'].set(path)
        ttk.Button(frame,text='Выбрать папку…',command=browse).pack(anchor='w',pady=4)
        row['bar']=ttk.Progressbar(frame,maximum=100);row['bar'].pack(fill='x');ttk.Label(frame,textvariable=row['state'],wraplength=700).pack(anchor='w')
        self.rows.append(row)
    def start(self):
        if self.running:return
        jobs=[];targets=set()
        try:
            for i,row in enumerate(self.rows):
                if row['done'] or not row['url'].get().strip():continue
                source,url=canonical(row['url'].get())
                if source!='youtube':raise ValueError('В этой вкладке нужны ссылки YouTube.')
                folder=Path(row['folder'].get())
                if not folder.is_dir():raise ValueError('Выберите папку сохранения.')
                target=folder/filename(row['name'].get())
                if target.exists() or str(target.resolve()).casefold() in targets:raise ValueError('Имя уже занято: '+str(target))
                targets.add(str(target.resolve()).casefold());jobs.append((i,url,target))
        except Exception as e:messagebox.showerror('Скачивание',str(e));return
        if not jobs:return
        self.running=True;self.cancel.clear()
        def worker():
            try:
                for i,url,target in jobs:
                    if self.cancel.is_set():break
                    partial=target.parent/('.autoeditor-'+uuid.uuid4().hex+'.mp4')
                    try:
                        self.messages.put((i,0,'Скачиваю…',False))
                        def update(**data):
                            size=data.get('size',0);received=data.get('received',0)
                            self.messages.put((i,min(99,received/size*100) if size else 0,data.get('message','Собираю видео…'),False))
                        youtube_download({'source':'youtube','url':url},partial,update,self.cancel)
                        if self.cancel.is_set():raise InterruptedError()
                        # Exclusive destination creation: never replace an existing video.
                        with target.open('xb') as out,partial.open('rb') as inp:
                            import shutil
                            shutil.copyfileobj(inp,out)
                        self.messages.put((i,100,'Готово: '+str(target),True))
                    except InterruptedError:self.messages.put((i,0,'Остановлено',False));break
                    except Exception as e:self.messages.put((i,0,str(e),False))
                    finally:
                        for file in partial.parent.glob(partial.name+'*'):
                            if file.is_file():file.unlink(missing_ok=True)
            finally:self.messages.put((-1,0,'',False))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        while True:
            try:i,value,text,done=self.messages.get_nowait()
            except queue.Empty:break
            if i<0:self.running=False;continue
            row=self.rows[i];row['bar']['value']=value;row['state'].set(text);row['done']=done
        self.app.root.after(150,self.poll)
