"""Local bot setup; account pairing is explicit and read-only."""
import queue,secrets,threading
import tkinter as tk
from tkinter import ttk,messagebox
from .notifications import EVENTS,api,save,send

def show(app):
    w=tk.Toplevel(app.root);w.title('Telegram · уведомления и автоматизация');w.transient(app.root)
    w.geometry(f'650x{min(720,w.winfo_screenheight()-110)}');w.columnconfigure(0,weight=1);w.rowconfigure(0,weight=1)
    from .ui import ScrollPage
    page=ScrollPage(w);page.grid(row=0,column=0,sticky='nsew');body=page.content
    config=dict(app.notifier.config);jobs=queue.Queue();closed=False;busy=False
    enabled=tk.BooleanVar(value=config['enabled']);auto=tk.BooleanVar(value=config['auto_timing'])
    token=tk.StringVar(value=config['token']);chat=tk.StringVar(value=config['chat_id']);status=tk.StringVar()
    ttk.Checkbutton(body,text='Отправлять уведомления в Telegram',variable=enabled).pack(anchor='w',pady=8)
    ttk.Label(body,text='Создайте отдельного бота через @BotFather (/newbot). Вставьте токен ниже.\nТокен сохраняется защищённо в текущем профиле Windows, не в проекте.',wraplength=580).pack(fill='x')
    ttk.Label(body,text='Токен бота').pack(anchor='w');ttk.Entry(body,textvariable=token,show='•').pack(fill='x',pady=4)
    code='/start '+secrets.token_hex(4)
    ttk.Label(body,text='Откройте своего бота в Telegram и отправьте ему эту команду:').pack(anchor='w')
    command=ttk.Entry(body);command.insert(0,code);command.configure(state='readonly');command.pack(fill='x',pady=4)
    ttk.Label(body,text='Затем нажмите «Найти мой чат». Чужие сообщения не используются.').pack(anchor='w')
    ttk.Label(body,text='ID личного чата').pack(anchor='w');ttk.Entry(body,textvariable=chat).pack(fill='x',pady=4)
    def values():return dict(enabled=enabled.get(),auto_timing=auto.get(),token=token.get().strip(),chat_id=chat.get().strip(),events=[k for k,v in choices.items() if v.get()])
    def work(kind):
        nonlocal busy
        if busy:return
        data=values();busy=True;status.set('Подключаюсь к Telegram…')
        def task():
            try:
                if kind=='pair':
                    from .notifications import validate
                    validate({**data,'chat_id':'1'})
                    updates=api(data['token'],'getUpdates',{'timeout':0,'limit':100})
                    chats={str(m['chat']['id']) for u in updates for m in [u.get('message',{})] if m.get('text')==code and m.get('chat',{}).get('type')=='private'}
                    if len(chats)!=1:raise ValueError('Команда не найдена однозначно. Отправьте указанную команду своему боту и повторите. Для редактора нужен отдельный бот без webhook.')
                    jobs.put(('pair',chats.pop()))
                else:send(data,'Auto Editor: тестовое уведомление. Подключение работает.');jobs.put(('ok','Тестовое сообщение отправлено.'))
            except Exception as error:
                # Only our sanitized exceptions may reach the UI; never URLs/tokens.
                from .notifications import DeliveryError
                jobs.put(('error',str(error) if isinstance(error,(ValueError,DeliveryError)) else 'Не удалось подключиться к Telegram.'))
            finally:jobs.put(('done',None))
        threading.Thread(target=task,daemon=True).start()
    row=ttk.Frame(body);row.pack(fill='x',pady=4)
    ttk.Button(row,text='Найти мой чат',command=lambda:work('pair')).pack(side='left')
    ttk.Button(row,text='Тестовое уведомление',command=lambda:work('test')).pack(side='left',padx=6)
    choices={k:tk.BooleanVar(value=k in config['events']) for k in EVENTS}
    for k,label in EVENTS.items():ttk.Checkbutton(body,text=label,variable=choices[k]).pack(anchor='w')
    ttk.Separator(body).pack(fill='x',pady=8)
    ttk.Checkbutton(body,text='Автоматически искать тайминги после успешного поиска фрагментов',variable=auto).pack(anchor='w')
    ttk.Label(body,text='При спорных фрагментах, ошибке или отмене автоматический переход не выполняется.\nРендер запускается вручную. Настройка работает и без Telegram.',wraplength=580).pack(fill='x')
    ttk.Label(body,textvariable=status,wraplength=580).pack(fill='x',pady=8)
    footer=ttk.Frame(w);footer.grid(row=1,column=0,sticky='ew',padx=10,pady=8)
    def close():
        nonlocal closed
        closed=True;w.after_cancel(timer[0]);w.destroy()
    def apply():
        try:
            data=values();save(data);app.notifier.config=data;close()
        except (OSError,ValueError) as error:messagebox.showerror('Telegram',str(error),parent=w)
    ttk.Button(footer,text='Сохранить',command=apply).pack(side='left')
    ttk.Button(footer,text='Закрыть',command=close).pack(side='right')
    def poll():
        nonlocal busy
        while not jobs.empty():
            kind,value=jobs.get_nowait()
            if kind=='pair':chat.set(value);status.set('Чат найден. Отправьте тест и сохраните настройки.')
            elif kind=='done':busy=False
            else:status.set(value)
        if not closed:timer[0]=w.after(100,poll)
    timer=[w.after(100,poll)];w.protocol('WM_DELETE_WINDOW',close);w.grab_set()
    return w
