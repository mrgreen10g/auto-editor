"""Reviewable one-folder setup without replacing the current project on cancel."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import ui
from .folder_import import root_files,build_import,unresolved_sources,presenter_folder


def choose_file(parent,title,files):
    if len(files)==1:return files[0]
    if not files:raise ValueError(title+': в корне папки нет подходящих файлов.')
    w=tk.Toplevel(parent);w.title(title);w.transient(parent);w.grab_set();result=[]
    ttk.Label(w,text='Найдено несколько файлов. Выберите нужный:',padding=12).pack(anchor='w')
    box=ttk.Combobox(w,state='readonly',values=[p.name for p in files],width=65);box.pack(padx=12,pady=8);box.current(0)
    def apply():result.append(files[box.current()]);w.destroy()
    ttk.Button(w,text='Выбрать',command=apply).pack(side='right',padx=12,pady=12)
    ttk.Button(w,text='Отмена',command=w.destroy).pack(side='right',padx=12,pady=12)
    parent.wait_window(w)
    return result[0] if result else None


def import_folder(app):
    if app.busy:return
    root=filedialog.askdirectory(parent=app.root,title='Выберите папку нового выпуска')
    if not root:return
    app.collect()
    try:
        hosts,scripts=root_files(presenter_folder(root,app.project.profile))
        if app.project.profile.endswith('_shorts'):
            preferred=[p for p in scripts if p.name.casefold()=='text.txt']
            if preferred:scripts=preferred
        host=choose_file(app.root,'Запись ведущего · MOV / MP4',hosts)
        if not host:return
        script=choose_file(app.root,'Полный сценарий · TXT / DOCX',scripts)
        if not script:return
        draft,mapping,notes=build_import(app.project,root,host,script)
    except Exception as error:
        messagebox.showerror('Импорт папки',str(error),parent=app.root);return
    w=tk.Toplevel(app.root);w.title('Импорт выпуска из папки');w.transient(app.root)
    w.geometry(f'{min(900,w.winfo_screenwidth()-60)}x{min(650,w.winfo_screenheight()-100)}');w.minsize(760,500)
    ttk.Label(w,text=f'Папка: {root}\nВедущий: {host.name}\nСценарий: {script.name}',wraplength=840,padding=12).pack(fill='x')
    hint='Ведущий и сценарий взяты из shorts, матчи — из папок лонга.' if host.parent.name.casefold()=='shorts' else 'Ведущий и сценарий взяты из выбранной папки, матчи — из вложенных папок.'
    ttk.Label(w,text='Проверьте сопоставление. Настройки голоса, музыки и оформления сохранятся.\n'+hint,wraplength=840,padding=12).pack(fill='x')
    table=ui.table(w,[('kind','Разбор / запись',330),('source','Папка / файл',280),('state','Состояние',220)],10)
    notice=tk.StringVar();ttk.Label(w,textvariable=notice,wraplength=840,padding=12).pack(fill='x')
    footer=ttk.Frame(w,padding=12);footer.pack(side='bottom',fill='x',before=table.master)
    overrides={};custom={};excluded=set()
    def refresh():
        table.delete(*table.get_children())
        for i,b in enumerate(draft.blocks):
            table.insert('','end',iid='block:'+str(i),values=(b.title,Path(mapping[i]).name if i in mapping else 'Не выбрана',f'{len(b.match_ids)} записей'))
            for source in draft.matches:
                if source.id in b.match_ids:
                    table.insert('','end',iid=source.id,values=('    '+(source.title if source not in unresolved_sources(draft) else 'Уточните команды / бойца'),Path(source.path).name,'Уточнить' if source in unresolved_sources(draft) else 'Готово'))
        count=len(unresolved_sources(draft))
        notice.set(f'Разборов: {len(draft.blocks)}. Записей: {len(draft.matches)}. Неясных записей: {count}.\n'+ '\n'.join(notes[:3])+ ('\nОстальные замечания — кнопка «Подробности».' if len(notes)>3 else ''))
    def edit():
        if not table.selection():return
        ident=table.selection()[0];source=next((m for m in draft.matches if m.id==ident),None)
        if source is None:return
        from .match_ui import SourceDialog
        from .graphics import block_teams
        owner=next(b for b in draft.blocks if ident in b.match_ids)
        dialog=SourceDialog(w,source,block_teams(owner.title))
        if dialog.result:
            source.home,source.away,source.date=dialog.result
            if source.sport=='combat':source.fighter=source.home
            custom[source.path]=(source.home,source.away,source.date,source.fighter)
            refresh()
        w.grab_set()
    def exclude():
        if not table.selection():return
        ident=table.selection()[0]
        for m in draft.matches:
            if m.id==ident:excluded.add(m.path)
        draft.matches=[m for m in draft.matches if m.id!=ident]
        for b in draft.blocks:b.match_ids=[v for v in b.match_ids if v!=ident]
        refresh()
    def folder():
        nonlocal draft,mapping,notes
        if not table.selection():return
        ident=table.selection()[0]
        i=int(ident.split(':')[1]) if ident.startswith('block:') else next((i for i,b in enumerate(draft.blocks) if ident in b.match_ids),None)
        if i is None:return
        path=filedialog.askdirectory(parent=w,title='Папка записей: '+draft.blocks[i].title)
        if not path:return
        proposed={**overrides,i:path}
        try:new,mp,nt=build_import(app.project,root,host,script,proposed)
        except Exception as error:messagebox.showerror('Папка матчей',str(error),parent=w);return
        overrides.update(proposed);draft,mapping,notes=new,mp,nt
        removed={m.id for m in draft.matches if m.path in excluded}
        draft.matches=[m for m in draft.matches if m.id not in removed]
        for b in draft.blocks:b.match_ids=[v for v in b.match_ids if v not in removed]
        for m in draft.matches:
            if m.path in custom:m.home,m.away,m.date,m.fighter=custom[m.path]
        refresh()
    def apply():
        if unresolved_sources(draft):
            messagebox.showinfo('Уточните записи','У некоторых файлов не определены команды или боец. Уточните их двойным щелчком или исключите файл.',parent=w);return
        from .material_folder import resolve
        draft.assets=resolve(draft.asset_folder,draft.assets)
        app.project=draft;app.project_path=None;app.index=0;app.scans.clear();app.legacy_project=False
        app.invalidate();app.refresh();w.destroy()
        app.status.set(f'Импортировано: {len(draft.blocks)} разборов, {len(draft.matches)} записей. Можно запускать поиск эпизодов.')
    table.bind('<Double-1>',lambda _:edit())
    actions=ttk.Frame(w,padding=12);actions.pack(side='bottom',fill='x',before=table.master)
    for label,cmd in [('Папка разбора…',folder),('Уточнить запись…',edit),('Исключить файл',exclude),('Подробности',lambda:messagebox.showinfo('Сопоставление папок','\n'.join(notes) or 'Все папки сопоставлены.',parent=w))]:
        ttk.Button(actions,text=label,command=cmd).pack(side='left',padx=(0,5))
    ttk.Button(footer,text='Отмена',command=w.destroy).pack(side='right')
    ttk.Button(footer,text='Импортировать',command=apply).pack(side='right',padx=5)
    app.folder_import_window=w;app.folder_import_apply=apply;app.folder_import_draft=draft
    refresh();w.grab_set()
