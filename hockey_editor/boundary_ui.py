"""Explicit recording ranges; normal analysis never opens this editor."""
def open_boundaries(app,reason=''):
    import tkinter as tk
    from tkinter import ttk,messagebox
    from .recording_times import parse_times,suggested_times
    if app.busy:return
    win=tk.Toplevel(app.root);win.title('Границы разделов');win.transient(app.root);win.grab_set()
    ttk.Label(win,text=reason or 'Автоматический подбор включён. Ручные границы имеют приоритет.',wraplength=650).pack(padx=12,pady=8)
    ttk.Label(win,text='Начало и конец в исходном видео: 00:00 00:39 Вступление.\nДалее каждый разбор по порядку и заключение. Пусто — вернуть автоматику.').pack(padx=12)
    field=tk.Text(win,width=80,height=14);field.pack(padx=12,pady=8)
    field.insert('1.0',app.project.recording_times or suggested_times(app.project))
    ttk.Label(win,text='Порядок: '+ ' → '.join(b.title for b in [app.project.intro,*app.project.blocks,app.project.outro]),wraplength=650).pack(padx=12)
    def save(resume=False):
        value=field.get('1.0','end').strip()
        try:
            if value:parse_times(value,len(app.project.blocks),allow_promos=app.project.profile.endswith('_shorts'))
        except ValueError as e:return messagebox.showerror('Границы',str(e),parent=win)
        app.project.recording_times=value
        for b in [app.project.intro,*app.project.blocks,app.project.outro]:b.speech_key='';b.edit_key=''
        app.project.episode_key='';app.invalidate();app.refresh()
        if app.project_path:app.project.save(app.project_path)
        win.destroy()
        if resume:app.start(False)
    ttk.Button(win,text='Сохранить',command=save).pack(side='left',padx=12,pady=12)
    ttk.Button(win,text='Подтвердить и найти тайминги',command=lambda:save(True)).pack(side='left',padx=12)
    ttk.Button(win,text='Позже',command=win.destroy).pack(side='right',padx=12)
