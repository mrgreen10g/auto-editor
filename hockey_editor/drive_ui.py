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
