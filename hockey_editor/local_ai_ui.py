"""One-time local model installation and hardware smoke test."""
import queue,threading,time
import tkinter as tk
from tkinter import ttk
from . import local_ai,preferences

def show(app):
    w=tk.Toplevel(app.root);w.title('Локальный ИИ · лёгкий режим');w.geometry('620x380');w.transient(app.root)
    ttk.Label(w,text='Бесплатная перепроверка спорного текста на этом ПК',font=('Segoe UI',12,'bold'),wraplength=580).pack(padx=16,pady=12)
    ttk.Label(w,text='Qwen3 1.7B · CPU, 2 потока. Загрузка модели около 1,3 ГБ.\nПосле установки интернет для анализа не нужен.\nПробный режим: подсказки, без автоматического подтверждения.\nДо 5 спорных фрагментов за проход. При нехватке памяти ИИ пропускается.',wraplength=580).pack(padx=16,anchor='w')
    active=tk.BooleanVar(value=local_ai.enabled())
    def toggle():
        data=preferences.read();data['local_ai_enabled']=active.get();preferences.write(data)
    ttk.Checkbutton(w,text='Перепроверять спорный текст после разметки',variable=active,command=toggle).pack(padx=16,pady=12,anchor='w')
    status=tk.StringVar(value='Компоненты установлены.' if local_ai.ready() else 'Компоненты ещё не установлены.')
    ttk.Label(w,textvariable=status,wraplength=580).pack(padx=16,fill='x')
    messages=queue.Queue();cancel=threading.Event();state={'busy':False,'closed':False}
    row=ttk.Frame(w);row.pack(padx=16,pady=16,fill='x')
    def start(kind):
        if state['busy']:return
        if app.busy:status.set('Дождитесь завершения анализа или рендера.');return
        state['busy']=True;cancel.clear();app.set_busy(True)
        def worker():
            try:
                if kind=='install':local_ai.install(cancel,messages.put)
                else:
                    begin=time.monotonic()
                    with local_ai.Session(cancel) as s:r=s.judge({'script':'Команда не проиграет.','recognized':'Команда не проиграет.','reason':'Проверка запуска.'})
                    messages.put(f'Проверка завершена за {time.monotonic()-begin:.1f} с. '+r['reason'])
            except Exception as e:messages.put(str(e))
            finally:messages.put(None)
        threading.Thread(target=worker,daemon=True).start()
    ttk.Button(row,text='Установить компоненты',command=lambda:start('install')).pack(side='left')
    ttk.Button(row,text='Проверить на этом ПК',command=lambda:start('test')).pack(side='left',padx=8)
    ttk.Button(w,text='Остановить',command=cancel.set).pack(anchor='w',padx=16)
    def poll():
        try:
            while True:
                item=messages.get_nowait()
                if item is None:state['busy']=False;app.set_busy(False)
                elif not state['closed']:status.set(item)
        except queue.Empty:pass
        if state['closed'] and not state['busy']:return
        app.root.after(150,poll)
    def close():state['closed']=True;cancel.set();w.destroy()
    w.protocol('WM_DELETE_WINDOW',close);poll()
