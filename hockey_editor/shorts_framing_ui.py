"""Review each landscape presenter before portrait montage; no voice processing."""
import threading,queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from PIL import Image,ImageTk
from . import shorts_framing as framing

def show(app,force=False):
 if not app.project.profile.endswith('_shorts'):
  messagebox.showinfo('Кадрирование','Выберите формат шортса.');return False
 paths=app.project.host_paths() if force else framing.pending(app.project)
 for path in paths:
  rot=0 if app.project.settings.auto_rotate else app.project.settings.rotate
  if framing.dimensions(path,rot)[0]<=framing.dimensions(path,rot)[1]:continue
  if not dialog(app,path):return False
 return True

def dialog(app,path):
 win=tk.Toplevel(app.root);win.title('Кадрирование Shorts · '+Path(path).name);win.transient(app.root)
 win.geometry('650x700');win.grab_set();win.protocol('WM_DELETE_WINDOW',lambda:close(False))
 status=tk.StringVar(value='Определяю положение спикера…')
 ttk.Label(win,textvariable=status,wraplength=610).pack(padx=12,pady=8)
 row=ttk.Frame(win);row.pack(fill='both',expand=True)
 picture=ttk.Label(row);picture.pack(side='left',padx=14)
 controls=ttk.Frame(row);controls.pack(side='left',fill='both',expand=True,padx=10)
 values={k:tk.DoubleVar(value=v) for k,v in [('x',.5),('y',.5),('zoom',1.)]}
 state={};events=queue.Queue();cancel=threading.Event();accepted=False
 def draw(*_):
  if 'image' not in state:return
  value={k:v.get() for k,v in values.items()}
  picture.photo=ImageTk.PhotoImage(framing.preview(state['image'],value,app.project.settings.mirror_host))
  picture.configure(image=picture.photo)
 for k,label,lo,hi in [('x','Положение по горизонтали',0,1),('y','Положение по вертикали',0,1),('zoom','Масштаб (1–2×)',1,2)]:
  ttk.Label(controls,text=label).pack(anchor='w',pady=(14,4))
  ttk.Scale(controls,from_=lo,to=hi,variable=values[k],command=draw).pack(fill='x')
 ttk.Label(controls,text='Кадр заполняется без растяжения лиц. Для смещения вверх/вниз при полном заполнении увеличьте масштаб.',wraplength=270).pack(pady=14)
 def move(dx,dy):
  if app.project.settings.mirror_host:dx=-dx
  values['x'].set(max(0,min(1,values['x'].get()+dx)))
  values['y'].set(max(0,min(1,values['y'].get()+dy)));draw()
 for label,dx,dy in [('←',-.02,0),('→',.02,0),('↑',0,-.02),('↓',0,.02)]:
  ttk.Button(controls,text=label,command=lambda x=dx,y=dy:move(x,y)).pack(fill='x',pady=2)
 def reset():
  for k,v in values.items():v.set(state['automatic'][k])
  draw()
 ttk.Button(controls,text='Автоматическое положение',command=reset).pack(pady=12)
 def close(ok):
  nonlocal accepted
  if ok and 'image' not in state:return
  if ok:
   app.project.host_framing[path]={**state['automatic'],**{k:v.get() for k,v in values.items()},'approved':True}
   app.result=None;accepted=True
   if app.project_path:app.project.save(app.project_path)
  cancel.set();win.destroy()
 bottom=ttk.Frame(win);bottom.pack(fill='x',padx=12,pady=12)
 ttk.Button(bottom,text='Отмена',command=lambda:close(False)).pack(side='right')
 ttk.Button(bottom,text='Применить кадрирование',command=lambda:close(True)).pack(side='right',padx=10)
 def work():
  try:
   from .orientation import detect_rotation
   rot=detect_rotation(path,app.cache_path(),cancel) if app.project.settings.auto_rotate else app.project.settings.rotate
   auto,image=framing.detect(path,rot,app.cache_path(),cancel)
   events.put((auto,image,None))
  except Exception as error:events.put((None,None,str(error)))
 def poll():
  if not win.winfo_exists():return
  try:auto,path_image,error=events.get_nowait()
  except queue.Empty:win.after(100,poll);return
  if error:status.set(error);return
  state['automatic']=auto;state['image']=Image.open(path_image).convert('RGB')
  current=app.project.host_framing.get(path,auto)
  if current.get('signature')!=auto['signature']:current=auto
  for k,v in values.items():v.set(current[k])
  status.set('Спикер найден. Проверьте кадр и при необходимости скорректируйте.' if auto['face_found'] else 'Лицо не определено уверенно. Установите положение вручную.')
  draw()
 threading.Thread(target=work,daemon=True).start();win.after(100,poll)
 app.root.wait_window(win);return accepted
