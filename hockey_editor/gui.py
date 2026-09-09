"""Small native Windows UI; all media processing runs away from the UI thread."""
import os,sys,threading,queue,subprocess,hashlib,json,tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox,simpledialog
from .model import Project,Block,Clip
from .engine import Engine
from .media import Cancelled
from . import __version__

VIDEO=[('Видео','*.mp4 *.mov *.mkv *.avi *.webm'),('Все файлы','*.*')]

def open_file(path):
    if os.name=='nt':os.startfile(str(path))
    elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
    else:subprocess.Popen(['xdg-open',str(path)])

class App:
    def __init__(self,root):
        self.root=root;root.title(f'Hockey Auto Editor — первая сборка {__version__}');root.geometry('1100x810');root.minsize(920,680)
        self.project=Project();self.project_path=None;self.index=0;self.plan=None;self.result=None
        self.jobs=queue.Queue();self.cancel=threading.Event();self.busy=False;self.controls=[];self.worker=None
        self.host=tk.StringVar();self.music=tk.StringVar();self.title=tk.StringVar(value='Новый разбор')
        style=ttk.Style()
        if 'vista' in style.theme_names():style.theme_use('vista')
        style.configure('TButton',padding=(10,5));style.configure('Title.TLabel',font=('Segoe UI',18,'bold'))
        self.body=ttk.Frame(root,padding=16);self.body.pack(fill='both',expand=True)
        top=ttk.Frame(self.body);top.pack(fill='x')
        ttk.Label(top,text='Hockey Auto Editor',style='Title.TLabel').pack(side='left')
        ttk.Label(top,text='0.1 • локальный монтаж одного разбора').pack(side='right')
        toolbar=ttk.Frame(self.body);toolbar.pack(fill='x',pady=(10,6))
        for label,cmd in [('Новый проект',self.new),('Открыть проект',self.load),('Сохранить проект',self.save)]:self.button(toolbar,label,cmd).pack(side='left',padx=(0,8))
        media=ttk.LabelFrame(self.body,text='1. Исходные файлы',padding=10);media.pack(fill='x',pady=6)
        self.pathrow(media,'Ведущий',self.host,self.choose_host)
        self.pathrow(media,'Музыка (необязательно)',self.music,self.choose_music)
        notebook=ttk.Notebook(self.body);notebook.pack(fill='both',expand=True,pady=6)
        tab=ttk.Frame(notebook,padding=10);settings=ttk.Frame(notebook,padding=12);review=ttk.Frame(notebook,padding=10)
        notebook.add(tab,text='2. Сценарий и вставки');notebook.add(settings,text='Оформление и звук');notebook.add(review,text='3. Проверка разметки')
        blockbar=ttk.Frame(tab);blockbar.pack(fill='x')
        self.blockbox=ttk.Combobox(blockbar,state='readonly',width=32);self.blockbox.pack(side='left');self.controls.append(self.blockbox)
        self.blockbox.bind('<<ComboboxSelected>>',self.switch_block)
        self.button(blockbar,'Добавить разбор',self.add_block).pack(side='left',padx=8)
        self.button(blockbar,'Удалить разбор',self.delete_block).pack(side='left')
        row=ttk.Frame(tab);row.pack(fill='x',pady=8)
        ttk.Label(row,text='Название матча:').pack(side='left');entry=ttk.Entry(row,textvariable=self.title);entry.pack(side='left',fill='x',expand=True,padx=8);self.controls.append(entry)
        ttk.Label(tab,text='Вставьте текст одного разбора. Таймкоды не нужны; запись ведущего может содержать весь выпуск.').pack(anchor='w')
        self.script=tk.Text(tab,height=10,wrap='word',font=('Segoe UI',11),undo=True);self.script.pack(fill='both',expand=True,pady=6);self.controls.append(self.script)
        ttk.Label(tab,text='В этой сборке: готовые игровые фрагменты. Поиск голов в полной записи матча — следующий этап.').pack(anchor='w',pady=(4,4))
        self.cliptable=ttk.Treeview(tab,columns=('file','phrase'),show='headings',height=4)
        self.cliptable.heading('file',text='Игровой фрагмент');self.cliptable.heading('phrase',text='Слова из сценария / счёт')
        self.cliptable.column('file',width=400);self.cliptable.column('phrase',width=220);self.cliptable.pack(fill='x')
        actions=ttk.Frame(tab);actions.pack(fill='x',pady=(6,0))
        for label,cmd in [('Добавить вставки',self.add_clips),('Изменить привязку',self.edit_clip),('Убрать вставку',self.remove_clip)]:self.button(actions,label,cmd).pack(side='left',padx=(0,8))
        self.rotate=tk.StringVar(value='Без поворота')
        ttk.Label(settings,text='Если кадр ведущего перевёрнут, выберите поворот:').pack(anchor='w')
        c=ttk.Combobox(settings,textvariable=self.rotate,values=['Без поворота','90°','180°','270°'],state='readonly',width=24);c.pack(anchor='w',pady=(5,12));self.controls.append(c)
        self.effect_vars={}
        for key,label in [('zoom','Плавные наезды 100% → 120% с промежутками'),('transitions','Мягкие переходы между ведущим и игровыми вставками'),('animate_cards','Анимированное появление и уход плашек'),('wobble','Лёгкое плавное покачивание плашек'),('cut_pauses','Сокращать паузы, сохраняя окончания слов'),('color','Лёгкая цветокоррекция')]:
            var=tk.BooleanVar(value=True);self.effect_vars[key]=var
            c=ttk.Checkbutton(settings,text=label,variable=var);c.pack(anchor='w',pady=4);self.controls.append(c)
        ttk.Separator(settings).pack(fill='x',pady=12)
        self.noise=tk.StringVar(value='Обычно');self.level=tk.StringVar(value='Тихо');self.resolution=tk.StringVar(value='720p')
        for label,var,values in [('Очистка голоса от шума',self.noise,['Выключено','Мягко','Обычно','Сильнее']),('Громкость музыки',self.level,['Очень тихо','Тихо','Заметнее']),('Размер видео',self.resolution,['720p','1080p'])]:
            r=ttk.Frame(settings);r.pack(fill='x',pady=5);ttk.Label(r,text=label,width=30).pack(side='left')
            c=ttk.Combobox(r,textvariable=var,values=values,state='readonly',width=24);c.pack(side='left');self.controls.append(c)
        ttk.Label(settings,text='Во время речи музыка приглушается. Очистка уменьшает фон; сильное эхо и перегруз записи могут остаться.',wraplength=750).pack(anchor='w',pady=12)
        ttk.Label(review,text='После анализа здесь появятся фразы и время их показа в готовом ролике.').pack(anchor='w',pady=(0,8))
        self.linetable=ttk.Treeview(review,columns=('time','text','check'),show='headings',height=13)
        for k,label,width in [('time','Время',100),('text','Фраза',660),('check','Проверка',100)]:self.linetable.heading(k,text=label);self.linetable.column(k,width=width)
        self.linetable.pack(fill='both',expand=True)
        r=ttk.Frame(review);r.pack(fill='x',pady=8)
        self.button(r,'Текст плашки для выбранной фразы',self.edit_card).pack(side='left')
        self.button(r,'Открыть папку разметки',self.open_cache).pack(side='left',padx=8)
        ttk.Label(review,text='Пустой текст плашки отключает её. Новый анализ применяет изменения без повторного поиска речи.',wraplength=820).pack(anchor='w')
        bottom=ttk.Frame(self.body);bottom.pack(fill='x',pady=(8,4))
        self.button(bottom,'Определить тайминги',lambda:self.start(False)).pack(side='left')
        self.button(bottom,'Собрать MP4',lambda:self.start(True)).pack(side='left',padx=8)
        self.cancelbutton=ttk.Button(bottom,text='Отменить',command=self.cancel.set,state='disabled');self.cancelbutton.pack(side='left')
        self.previewbutton=ttk.Button(bottom,text='Открыть результат',command=self.preview,state='disabled');self.previewbutton.pack(side='right')
        self.progress=ttk.Progressbar(self.body,mode='indeterminate');self.progress.pack(fill='x',pady=5)
        self.status=tk.StringVar(value='Начните с записи ведущего и сценария. Исходники остаются на вашем компьютере.')
        ttk.Label(self.body,textvariable=self.status,wraplength=1000).pack(anchor='w')
        self.logbox=tk.Text(self.body,height=3,wrap='word',state='disabled',font=('Consolas',9));self.logbox.pack(fill='x',pady=(6,0))
        self.refresh();root.after(100,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)

    def button(self,parent,label,command):
        w=ttk.Button(parent,text=label,command=command);self.controls.append(w);return w
    def pathrow(self,parent,label,var,choose):
        r=ttk.Frame(parent);r.pack(fill='x',pady=3);ttk.Label(r,text=label,width=25).pack(side='left')
        e=ttk.Entry(r,textvariable=var);e.pack(side='left',fill='x',expand=True,padx=6);self.controls.append(e)
        self.button(r,'Выбрать…',choose).pack(side='left')
    def choose_host(self):
        f=filedialog.askopenfilename(title='Видео ведущего',filetypes=VIDEO)
        if f:self.host.set(f)
    def choose_music(self):
        f=filedialog.askopenfilename(title='Музыка',filetypes=[('Звук','*.mp3 *.wav *.m4a *.aac *.flac'),('Все файлы','*.*')])
        if f:self.music.set(f)
    def collect(self):
        p=self.project;p.host=self.host.get().strip();p.music=self.music.get().strip()
        b=p.blocks[self.index];b.title=self.title.get().strip() or 'Разбор';b.script=self.script.get('1.0','end').strip()
        for k,v in self.effect_vars.items():setattr(p.settings,k,v.get())
        p.settings.rotate={'Без поворота':0,'90°':90,'180°':180,'270°':270}[self.rotate.get()]
        p.settings.zoom_max=1.20
        p.settings.denoise=self.noise.get()!='Выключено';p.settings.noise_reduction={'Выключено':10,'Мягко':6,'Обычно':10,'Сильнее':14}[self.noise.get()]
        p.settings.music_db={'Очень тихо':-32,'Тихо':-28,'Заметнее':-24}[self.level.get()]
        p.settings.width,p.settings.height=(1920,1080) if self.resolution.get()=='1080p' else (1280,720)
    def refresh(self):
        p=self.project;b=p.blocks[self.index]
        self.host.set(p.host);self.music.set(p.music);self.title.set(b.title)
        self.blockbox['values']=[x.title for x in p.blocks];self.blockbox.current(self.index)
        self.script.delete('1.0','end');self.script.insert('1.0',b.script)
        self.cliptable.delete(*self.cliptable.get_children())
        for i,c in enumerate(b.clips):self.cliptable.insert('','end',iid=str(i),values=(Path(c.path).name,c.phrase))
        self.rotate.set({0:'Без поворота',90:'90°',180:'180°',270:'270°'}[p.settings.rotate])
        for k,var in self.effect_vars.items():var.set(getattr(p.settings,k))
        self.noise.set('Выключено' if not p.settings.denoise else 'Мягко' if p.settings.noise_reduction<8 else 'Сильнее' if p.settings.noise_reduction>12 else 'Обычно')
        self.level.set('Очень тихо' if p.settings.music_db<=-30 else 'Заметнее' if p.settings.music_db>=-26 else 'Тихо')
        self.resolution.set('1080p' if p.settings.width==1920 else '720p')
    def switch_block(self,_=None):
        idx=self.blockbox.current();self.collect();self.index=idx;self.plan=None;self.linetable.delete(*self.linetable.get_children());self.refresh()
    def add_block(self):
        self.collect();self.project.blocks.append(Block(title=f'Разбор {len(self.project.blocks)+1}'));self.index=len(self.project.blocks)-1;self.plan=None;self.refresh()
    def delete_block(self):
        if len(self.project.blocks)==1:return messagebox.showinfo('Разбор','В проекте должен остаться хотя бы один разбор.')
        if messagebox.askyesno('Удалить разбор','Убрать выбранный разбор из проекта? Видео на диске останется.'):
            del self.project.blocks[self.index];self.index=0;self.plan=None;self.refresh()
    def add_clips(self):
        import re
        self.collect()
        for path in filedialog.askopenfilenames(title='Готовые игровые вставки',filetypes=VIDEO):
            name=Path(path).stem
            nums=re.search(r'(\d+)[_:](\d+)(?:$|[^\d])',name)
            phrase=(nums[1]+':'+nums[2]) if nums else simpledialog.askstring('Привязка к речи',f'{Path(path).name}\nКакие слова из сценария сопровождает вставка?')
            script=self.project.blocks[self.index].script
            if 'equaliz' in name.lower():
                phrase=next((line.strip() for line in script.splitlines() if 'сравн' in line.lower()),phrase)
            elif 'overtime' in name.lower():
                phrase=next((line.strip() for line in script.splitlines() if 'овертайм' in line.lower() and any(w in line.lower() for w in ('затем','решил','победный'))),phrase)
            if phrase:self.project.blocks[self.index].clips.append(Clip(path,phrase))
        self.refresh()
    def edit_clip(self):
        sel=self.cliptable.selection()
        if not sel:return
        self.collect();c=self.project.blocks[self.index].clips[int(sel[0])]
        value=simpledialog.askstring('Привязка к речи','Слова из сценария или счёт:',initialvalue=c.phrase)
        if value:c.phrase=value;self.refresh()
    def remove_clip(self):
        sel=self.cliptable.selection()
        if sel:self.collect();del self.project.blocks[self.index].clips[int(sel[0])];self.refresh()
    def edit_card(self):
        sel=self.linetable.selection()
        if not sel or self.plan is None:return
        i=int(sel[0]);self.collect();b=self.project.blocks[self.index]
        text=b.card_overrides.get(str(i),self.plan.lines[i].text)
        value=simpledialog.askstring('Плашка','Текст плашки. Оставьте пустым, чтобы отключить:',initialvalue=text)
        if value is not None:b.card_overrides[str(i)]=value;self.status.set('Плашка изменена. При анализе или экспорте она обновится.')
    def new(self):
        if not messagebox.askyesno('Новый проект','Создать новый проект? Несохраненные изменения текущего проекта будут потеряны.'):return
        self.project=Project();self.index=0;self.project_path=None;self.plan=None;self.refresh()
    def load(self):
        path=filedialog.askopenfilename(filetypes=[('Проект монтажа','*.hockeyproj')])
        if not path:return
        try:self.project=Project.load(path);self.index=0;self.project_path=path;self.plan=None;self.refresh();self.status.set('Проект открыт. Если исходники переместились, выберите их заново.')
        except Exception as e:messagebox.showerror('Не удалось открыть проект',str(e))
    def save(self):
        self.collect();path=filedialog.asksaveasfilename(defaultextension='.hockeyproj',initialfile=Path(self.project_path).name if self.project_path else 'Мой выпуск.hockeyproj',filetypes=[('Проект монтажа','*.hockeyproj')])
        if path:
            try:self.project.save(path);self.project_path=path;self.status.set('Проект сохранён: '+path)
            except Exception as e:messagebox.showerror('Сохранение',str(e))
    def cache_path(self):
        seed=self.project.host+'\n'+self.project.blocks[self.index].title
        key=hashlib.sha256(seed.encode()).hexdigest()[:16]
        base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'Cache'
        return base/key
    def open_cache(self):
        try:path=self.cache_path();path.mkdir(parents=True,exist_ok=True);open_file(path)
        except Exception as e:messagebox.showerror('Папка',str(e))
    def set_busy(self,state):
        self.busy=state
        for w in self.controls:
            if state:w._oldstate=str(w.cget('state'));w.configure(state='disabled')
            else:w.configure(state=getattr(w,'_oldstate','normal'))
        self.cancelbutton.configure(state='normal' if state else 'disabled')
        if state:self.progress.start(15)
        else:self.progress.stop()
    def start(self,render):
        if self.busy:return
        self.collect()
        try:self.project.validate(self.index)
        except Exception as e:return messagebox.showerror('Проверьте материалы',str(e))
        target=None
        if render:
            target=filedialog.asksaveasfilename(title='Готовый ролик — новое имя файла',defaultextension='.mp4',initialfile='Мой разбор.mp4',filetypes=[('Видео MP4','*.mp4')])
            if not target:return
            if Path(target).exists():return messagebox.showinfo('Выберите новое имя','Чтобы сохранить предыдущий результат, укажите новое имя MP4.')
        self.cancel.clear();self.set_busy(True)
        engine=Engine(self.project,self.index,self.cache_path(),self.cancel,lambda msg:self.jobs.put(('log',msg)))
        def work():
            try:
                plan=engine.analyze();self.jobs.put(('plan',plan))
                if render:
                    result=engine.render(plan,target);self.jobs.put(('result',result))
            except Cancelled:self.jobs.put(('log','Отменено. Можно изменить настройки и повторить.'))
            except Exception as e:self.jobs.put(('error',str(e)))
            finally:self.jobs.put(('done',None))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
    def poll(self):
        try:
            while True:
                kind,value=self.jobs.get_nowait()
                if kind=='log':
                    self.status.set(value);self.logbox.configure(state='normal');self.logbox.insert('end',value+'\n');self.logbox.see('end');self.logbox.configure(state='disabled')
                elif kind=='plan':
                    self.plan=value;self.linetable.delete(*self.linetable.get_children())
                    for i,l in enumerate(value.lines):self.linetable.insert('','end',iid=str(i),values=(f'{l.start:.1f}–{l.end:.1f}',l.text,'Проверить' if l.agreement>.8 else ''))
                    if value.warnings:self.jobs.put(('log',' • '.join(value.warnings)))
                elif kind=='result':self.result=value;self.previewbutton.configure(state='normal');messagebox.showinfo('Готово','Видео сохранено. Нажмите «Открыть результат», чтобы посмотреть его.\n\nРядом с MP4 сохранена автоматическая разметка.')
                elif kind=='error':messagebox.showerror('Обработка не завершена',value+'\n\nПодробности находятся в папке разметки.');self.status.set('Обработка не завершена. Исходники сохранены.')
                elif kind=='done':self.set_busy(False)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def preview(self):
        if self.result and Path(self.result).exists():
            try:open_file(self.result)
            except Exception as e:messagebox.showerror('Просмотр',str(e))
    def close(self):
        if self.busy:
            if messagebox.askyesno('Идет обработка','Отменить обработку? После остановки можно закрыть окно.'):self.cancel.set()
            return
        self.root.destroy()

def launch():
    root=tk.Tk();App(root);root.mainloop()
