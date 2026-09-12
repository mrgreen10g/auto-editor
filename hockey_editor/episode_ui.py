"""Full-episode settings and ordered presenter sources, without timeline jargon."""
from pathlib import Path
import copy,json,os,re
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import ui
from .model import Block


from .framing import split_full_script


def kit_path():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.cache')))/'HockeyAutoEditor'/'asset-kit.json'


class EpisodeMixin:
    def edit_hosts(self):
        if self.busy:return
        self.collect();paths=[p for p in self.project.host_paths() if p]
        w=tk.Toplevel(self.root);w.title('Части записи ведущего');w.geometry('800x400');w.transient(self.root)
        ttk.Label(w,text='Расположите файлы от начала к продолжению. Склеивать видео заранее не нужно.',wraplength=740).pack(anchor='w',padx=16,pady=16)
        table=ui.table(w,[('order','Порядок',80),('file','Запись ведущего',620)],7);table.master.pack_configure(padx=16)
        def refresh(selected=0):
            table.delete(*table.get_children())
            for i,path in enumerate(paths):table.insert('','end',iid=str(i),values=(f'Часть {i+1}',Path(path).name))
            if paths:table.selection_set(str(min(selected,len(paths)-1)))
        def add():
            values=filedialog.askopenfilenames(parent=w,title='Добавить части в порядке записи',filetypes=[('Видео','*.mp4 *.mov *.mkv *.avi *.webm')])
            for path in values:
                if path not in paths:paths.append(path)
            refresh(len(paths)-1)
        def move(delta):
            if not table.selection():return
            i=int(table.selection()[0]);j=i+delta
            if 0<=j<len(paths):paths[i],paths[j]=paths[j],paths[i];refresh(j)
        def remove():
            if table.selection():paths.pop(int(table.selection()[0]));refresh()
        bar=ttk.Frame(w,padding=16);bar.pack(fill='x')
        for text,cmd in [('+ Добавить части',add),('↑ Выше',lambda:move(-1)),('↓ Ниже',lambda:move(1)),('Убрать',remove)]:ttk.Button(bar,text=text,command=cmd).pack(side='left',padx=(0,8))
        def apply():
            if not paths:return messagebox.showinfo('Запись','Добавьте хотя бы одну часть.',parent=w)
            self.project.hosts=paths[:];self.project.host=paths[0];self.invalidate();self.refresh();w.destroy()
        ttk.Button(w,text='Сохранить порядок',command=apply).pack(anchor='e',padx=16,pady=(0,12))
        refresh();w.grab_set()

    def edit_framing(self):
        if self.busy:return
        self.collect();draft=copy.deepcopy(self.project)
        w=tk.Toplevel(self.root);w.title('Начало и завершение выпуска');w.geometry(f'{min(850,w.winfo_screenwidth()-60)}x{min(740,w.winfo_screenheight()-100)}');w.minsize(700,600);w.transient(self.root)
        bottom=ttk.Frame(w,padding=12);bottom.pack(side='bottom',fill='x')
        enabled=tk.BooleanVar(value=draft.full_video)
        ttk.Checkbutton(w,text='Добавлять начало и завершение в режиме «Все разборы»',variable=enabled).pack(anchor='w',padx=16,pady=12)
        tabs=ttk.Notebook(w);tabs.pack(fill='both',expand=True,padx=16)
        fields={};asset_vars={}
        for key,label in [('intro','Начало'),('outro','Итоги и прощание')]:
            page=ttk.Frame(tabs,padding=12);tabs.add(page,text=label)
            hint='Пары команд — под слова ведущего. Telegram — ровно на фразу о канале и ссылке.' if key=='intro' else 'Повтор прогнозов, Telegram и подписка. Последняя строка — полное прощание. Игровых вставок здесь нет.'
            ttk.Label(page,text=hint,wraplength=720).pack(anchor='w',pady=(0,10))
            area=ttk.Frame(page);area.pack(fill='both',expand=True)
            field=tk.Text(area,wrap='word',font=('Segoe UI',11),undo=True,padx=10,pady=10)
            scroll=ttk.Scrollbar(area,command=field.yview);field.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right',fill='y');field.pack(fill='both',expand=True);field.insert('1.0',getattr(draft,key).script);fields[key]=field
        page=ttk.Frame(tabs,padding=16);tabs.add(page,text='Постоянные материалы')
        for key,label in [('disclaimer','Дисклеймер · целиком в начале'),('telegram','Telegram · слева, под речь'),('subscribe','Подписка · полная анимация')]:
            ttk.Label(page,text=label,style='CardTitle.TLabel').pack(anchor='w',pady=(14,5))
            row=ttk.Frame(page);row.pack(fill='x');var=tk.StringVar(value=draft.assets.get(key,''));asset_vars[key]=var
            ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
            def choose(v=var):
                path=filedialog.askopenfilename(parent=w,filetypes=[('Видео / прозрачная анимация','*.mp4 *.mov *.mkv *.webm')])
                if path:v.set(path)
            ttk.Button(row,text='Выбрать',command=choose).pack(side='left',padx=(8,0))
        ttk.Label(page,text='MOV с прозрачностью поддерживается. Звук Telegram и подписки отключён; звук дисклеймера сохранён. Для новых проектов можно сохранить этот набор.',wraplength=720).pack(anchor='w',pady=22)
        remember=tk.BooleanVar(value=True);ttk.Checkbutton(page,text='Запомнить эти материалы для новых проектов',variable=remember).pack(anchor='w')
        def import_script():
            path=filedialog.askopenfilename(parent=w,title='Полный сценарий',filetypes=[('Текст UTF-8','*.txt')])
            if not path:return
            try:
                intro,blocks,outro=split_full_script(Path(path).read_text(encoding='utf-8-sig'))
                if not messagebox.askyesno('Импорт сценария',f'Найдено разборов: {len(blocks)}. Заменить тексты начала, разборов и завершения?\nМатчи и настройки совпадающих пар сохранятся.',parent=w):return
                old={b.title.casefold():b for b in draft.blocks};updated=[]
                for title,script in blocks:
                    b=old.get(title.casefold(),Block(title=title))
                    if b.script!=script:b.events=[];b.edit_plan=None;b.edit_key=''
                    b.script=script;updated.append(b)
                draft.blocks=updated
                for key,value in [('intro',intro),('outro',outro)]:fields[key].delete('1.0','end');fields[key].insert('1.0',value)
                enabled.set(True);messagebox.showinfo('Сценарий разделён','Начало, разборы и завершение заполнены. После сохранения добавьте матчи для новых разборов.',parent=w)
            except Exception as error:messagebox.showerror('Сценарий',str(error),parent=w)
        def apply():
            for key,field in fields.items():getattr(draft,key).script=field.get('1.0','end').strip()
            draft.assets={k:v.get().strip() for k,v in asset_vars.items()};draft.full_video=enabled.get()
            if draft.full_video:
                if any(len(getattr(draft,k).script)<30 for k in fields):return messagebox.showerror('Тексты','Заполните начало и завершение.',parent=w)
                if any(not v or not Path(v).is_file() for v in draft.assets.values()):return messagebox.showerror('Материалы','Выберите дисклеймер, Telegram и подписку.',parent=w)
                draft.whole_episode=True
            if remember.get():
                try:
                    path=kit_path();path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(draft.assets,ensure_ascii=False),encoding='utf-8');tmp.replace(path)
                except OSError as error:return messagebox.showerror('Материалы','Не удалось сохранить набор: '+str(error),parent=w)
            self.project=draft;self.index=min(self.index,len(draft.blocks)-1);self.invalidate();self.refresh();w.destroy()
        ttk.Button(bottom,text='Загрузить полный сценарий .txt',command=import_script).pack(side='left')
        ttk.Button(bottom,text='Сохранить',command=apply).pack(side='right')
        ttk.Button(bottom,text='Отмена',command=w.destroy).pack(side='right',padx=8)
        self.framing_window=w;self.framing_fields=fields;self.framing_assets=asset_vars;self.framing_enabled=enabled;self.apply_framing=apply
        w.grab_set()
