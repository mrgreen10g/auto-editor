"""One-time Google account connection on the Windows server."""
import queue,threading,tkinter as tk
from tkinter import ttk,filedialog,messagebox
from . import drive_upload as drive

def show(app):
    w=tk.Toplevel(app.root);w.title('Google Диск');w.geometry('650x540');w.transient(app.root)
    body=ttk.Frame(w,padding=16);body.pack(fill='both',expand=True)
    c=drive.public_config();status=tk.StringVar(value=c['account'] or 'Аккаунт не подключён');events=queue.Queue();busy=False
    ttk.Label(body,textvariable=status,wraplength=600).pack(anchor='w',pady=8)
    ttk.Label(body,text='Выберите OAuth JSON типа Desktop app. Вход откроется в браузере на этом сервере. Настройка: docs/GOOGLE_DRIVE_RU.md в исходниках или GOOGLE_DRIVE_RU.txt рядом с программой.',wraplength=600).pack(anchor='w',pady=8)
    def connect():
        nonlocal busy
        if busy:return
        path=filedialog.askopenfilename(parent=w,title='Google OAuth · Desktop app',filetypes=[('JSON','*.json')])
        if not path:return
        busy=True;button.configure(state='disabled');status.set('Завершите вход в браузере сервера…')
        def work():
            try:events.put((True,drive.connect(path)))
            except Exception:events.put((False,'Подключение не завершено. Проверьте OAuth JSON, Google Drive API и вход в браузере; затем повторите.'))
        threading.Thread(target=work,daemon=True).start()
    button=ttk.Button(body,text='Подключить Google-аккаунт…',command=connect);button.pack(anchor='w',pady=6)
    values={}
    for key,label in drive.DESTINATIONS.items():
        ttk.Label(body,text=label+' · ссылка на папку').pack(anchor='w',pady=(8,0))
        values[key]=tk.StringVar(value=c['folders'][key]);ttk.Entry(body,textvariable=values[key]).pack(fill='x')
    auto=tk.BooleanVar(value=c['auto']);ttk.Checkbutton(body,text='Предлагать отправку на Google Диск после рендера',variable=auto).pack(anchor='w',pady=12)
    def save():
        try:drive.save_config(dict(folders={k:v.get() for k,v in values.items()},auto=auto.get()));status.set('Папки сохранены. Они доступны в Mini App.')
        except ValueError as error:messagebox.showerror('Google Диск',str(error),parent=w)
    ttk.Button(body,text='Сохранить папки',command=save).pack(anchor='e')
    def poll():
        nonlocal busy
        if not w.winfo_exists():return
        try:
            ok,message=events.get_nowait();busy=False;button.configure(state='normal');status.set(('Подключён: ' if ok else '')+message)
        except queue.Empty:pass
        w.after(300,poll)
    poll()


def show_upload(app):
    """Desktop controls for the same upload jobs as the Mini App."""
    from pathlib import Path
    import webbrowser,re
    manager=app.mini.results
    if app.result and Path(app.result).is_file():manager.register(app.result)
    w=tk.Toplevel(app.root);w.title('Готовые видео · Google Диск');w.geometry('680x560');w.transient(app.root)
    body=ttk.Frame(w,padding=16);body.pack(fill='both',expand=True)
    ttk.Label(body,text='Готовое видео этого проекта').pack(anchor='w')
    files=ttk.Combobox(body,state='readonly');files.pack(fill='x',pady=6)
    rows=[];keys=list(drive.DESTINATIONS)+['custom'];labels=list(drive.DESTINATIONS.values())+['Другая папка']
    ttk.Label(body,text='Папка назначения').pack(anchor='w',pady=(12,0))
    destination=ttk.Combobox(body,values=labels,state='readonly');destination.pack(fill='x')
    profile=app.project.profile;destination.current(keys.index(('uz' if profile.startswith('uz_') else 'ru')+('_shorts' if profile.endswith('_shorts') else '_long')))
    path=tk.StringVar();ttk.Label(body,text='Ссылка или ID папки').pack(anchor='w',pady=(12,0));ttk.Entry(body,textvariable=path).pack(fill='x')
    def folder_changed(_=None):path.set(drive.public_config()['folders'].get(keys[destination.current()],''))
    destination.bind('<<ComboboxSelected>>',folder_changed);folder_changed()
    status=tk.StringVar();ttk.Label(body,textvariable=status,wraplength=630).pack(anchor='w',pady=12)
    progress=ttk.Progressbar(body,maximum=100);progress.pack(fill='x',pady=6)
    controls=ttk.Frame(body);controls.pack(fill='x',pady=8)
    def selected():return rows[files.current()] if 0<=files.current()<len(rows) else None
    def action(fn):
        try:fn()
        except Exception as e:messagebox.showerror('Google Диск',str(e),parent=w)
    def send():
        row=selected()
        if not row:raise ValueError('Выберите готовое видео.')
        manager.start({'id':row['id'],'folder':path.get()});poll(False)
    send_button=ttk.Button(controls,text='Отправить / продолжить',command=lambda:action(send));send_button.pack(side='left')
    pause_button=ttk.Button(controls,text='Приостановить',command=lambda:action(lambda:manager.pause({'id':selected()['id']})));pause_button.pack(side='left',padx=8)
    def url():
        row=selected();value=(row.get('upload') or {}).get('url','') if row else ''
        return value if re.fullmatch(r'https://drive\.google\.com/file/d/[A-Za-z0-9_-]+/view',value) else ''
    def copy_link():
        value=url()
        if value:w.clipboard_clear();w.clipboard_append(value);status.set('Ссылка скопирована.')
    links=ttk.Frame(body);links.pack(fill='x',pady=8)
    link=ttk.Button(links,text='Открыть на Диске',command=lambda:webbrowser.open(url()) if url() else None);link.pack(side='left')
    copy_button=ttk.Button(links,text='Скопировать ссылку',command=copy_link);copy_button.pack(side='left',padx=8)
    def add():
        filename=filedialog.askopenfilename(parent=w,title='Готовое видео',filetypes=[('MP4','*.mp4')])
        if filename:manager.register(filename);files.set('');poll(False)
    ttk.Button(body,text='Выбрать другой готовый MP4…',command=lambda:action(add)).pack(anchor='w',pady=6)
    ttk.Button(body,text='Аккаунт и постоянные папки…',command=lambda:show(app)).pack(anchor='w')
    def poll(schedule=True):
        nonlocal rows
        if not w.winfo_exists():return
        current=selected();data=manager.status();rows=data['results'];files.configure(values=[(r.get('title') or r['name'])+' · '+r['name'] for r in rows])
        if rows:files.current(next((i for i,r in enumerate(rows) if current and r['id']==current['id']),0))
        row=selected();upload=(row.get('upload') or {}) if row else {}
        status.set(upload.get('message') or ('Выберите папку и отправьте видео.' if data['drive']['connected'] else 'Сначала подключите Google-аккаунт.'))
        progress['value']=upload.get('progress',0)
        send_button.configure(state='normal' if row and row['available'] and data['drive']['connected'] and not data['upload_busy'] else 'disabled')
        pause_button.configure(state='normal' if upload.get('status')=='uploading' else 'disabled')
        for button in (link,copy_button):button.configure(state='normal' if upload.get('status')=='completed' and url() else 'disabled')
        if schedule:w.after(500,poll)
    files.bind('<<ComboboxSelected>>',lambda _:poll(False));poll()

