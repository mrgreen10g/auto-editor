"""Visual source trimming within a validated gameplay interval."""
import queue
import threading
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
from . import ui
from .preview import PreviewPlayer
from .timeline import format_time,parse_time
from .media import run,Cancelled
from .goals import scan_root


class TrimDialog:
    def __init__(self,parent,path,lo,hi,start,end,event,on_apply):
        if hi-lo<.5:raise ValueError('Игровой фрагмент слишком короткий.')
        self.parent=parent;self.lo=lo;self.hi=hi;self.start=start;self.end=end;self.event=event
        self.on_apply=on_apply;self.mode=None;self.closed=False;self.ready=False;self.photos=[]
        self.cancel=threading.Event();self.jobs=queue.Queue()
        self.window=tk.Toplevel(parent);w=self.window;w.title('Границы игрового момента')
        w.geometry(f'820x{min(670,w.winfo_screenheight()-80)}');w.minsize(720,520)
        w.transient(parent);w.grab_set();w.configure(bg=ui.BG);w.protocol('WM_DELETE_WINDOW',self.close)
        ttk.Label(w,text='Тяните бирюзовые края, чтобы обрезать вставку. Жёлтая метка — момент гола.',wraplength=760).pack(padx=16,pady=12)
        self.screen=ttk.Label(w,text='Готовлю видео и кадры…',anchor='center');self.screen.pack(fill='both',expand=True,padx=16)
        self.player=PreviewPlayer(self.screen,self.position,lambda e:self.status.set(e))
        row=ttk.Frame(w);row.pack(fill='x',padx=16,pady=6)
        ttk.Button(row,text='▶ / ❚❚',command=self.toggle).pack(side='left')
        self.clock=ttk.Label(row,text=format_time(start));self.clock.pack(side='left',padx=12)
        self.status=tk.StringVar(value='Границы ограничены проверенной игровой сценой.')
        ttk.Label(row,textvariable=self.status,style='Muted.TLabel').pack(side='left')
        self.canvas=tk.Canvas(w,height=118,bg='#142334',highlightthickness=0);self.canvas.pack(fill='x',padx=16)
        self.canvas.bind('<Configure>',lambda _:self.draw());self.canvas.bind('<Button-1>',self.down)
        self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.up)
        row=ttk.Frame(w);row.pack(fill='x',padx=16,pady=12);self.values=[]
        for label,value in zip(('Начало','Конец','Гол'),(start,end,event)):
            ttk.Label(row,text=label).pack(side='left',padx=(0,4));var=tk.StringVar(value=format_time(value));self.values.append(var)
            entry=ttk.Entry(row,textvariable=var,width=11);entry.pack(side='left',padx=(0,12));entry.bind('<Return>',lambda _:self.read_values())
        bottom=ttk.Frame(w);bottom.pack(fill='x',padx=16,pady=(0,12))
        ttk.Button(bottom,text='Отмена',command=self.close).pack(side='left')
        ttk.Button(bottom,text='Применить границы',command=self.apply,style='Primary.TButton').pack(side='right')
        folder=scan_root()/'trim'/uuid.uuid4().hex[:12];folder.mkdir(parents=True,exist_ok=True)
        self.folder=folder;video=folder/'preview.mp4'
        def work():
            try:
                run(['-y','-ss',lo,'-i',path,'-t',hi-lo,'-an','-vf','scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,fps=15',
                     '-c:v','libx264','-preset','ultrafast','-crf','26',video],self.cancel)
                run(['-y','-i',video,'-vf',f'fps={8/(hi-lo):.8f},scale=96:54','-frames:v','8',folder/'thumb-%02d.jpg'],self.cancel)
                self.jobs.put(('ready',video))
            except Cancelled:pass
            except Exception as error:self.jobs.put(('error',str(error)))
        threading.Thread(target=work,daemon=True).start();self.poll_id=w.after(60,self.poll)

    def x(self,t):return 12+(t-self.lo)/(self.hi-self.lo)*max(1,self.canvas.winfo_width()-24)
    def time_at(self,x):return max(self.lo,min(self.hi,self.lo+(x-12)/max(1,self.canvas.winfo_width()-24)*(self.hi-self.lo)))

    def draw(self):
        c=self.canvas;c.delete('all');width=max(1,c.winfo_width()-24)
        for i,p in enumerate(self.photos):c.create_image(12+i*width/8,24,image=p,anchor='nw')
        x1,x2=self.x(self.start),self.x(self.end)
        c.create_rectangle(12,24,x1,80,fill='#142334',stipple='gray50',outline='')
        c.create_rectangle(x2,24,self.x(self.hi),80,fill='#142334',stipple='gray50',outline='')
        c.create_rectangle(x1,24,x2,80,outline='#50d8be',width=2)
        for x in (x1,x2):c.create_rectangle(x-4,20,x+4,86,fill='#50d8be',outline='')
        x=self.x(self.event);c.create_line(x,17,x,85,fill='#ffc35b',width=2)
        c.create_polygon(x-6,9,x+6,9,x,18,fill='#ffc35b')
        c.create_text(12,103,text=format_time(self.lo),anchor='w',fill='white')
        c.create_text(self.x(self.hi),103,text=format_time(self.hi),anchor='e',fill='white')
        if self.ready:
            x=self.x(self.lo+self.player.position);c.create_line(x,25,x,78,fill='#fa7373',width=2)

    def set_boundary(self,mode,t):
        if mode=='start':self.start=max(self.lo,min(t,self.end-.5));self.event=max(self.event,self.start)
        elif mode=='end':self.end=min(self.hi,max(t,self.start+.5));self.event=min(self.event,self.end)
        elif mode=='event':self.event=max(self.start,min(t,self.end))
        for var,v in zip(self.values,(self.start,self.end,self.event)):var.set(format_time(v))
        self.draw()

    def down(self,e):
        self.player.stop()
        self.mode='start' if abs(e.x-self.x(self.start))<10 else 'end' if abs(e.x-self.x(self.end))<10 else 'event' if e.y<24 else 'cursor'
        self.motion(e)
    def motion(self,e):
        if not self.mode:return
        t=self.time_at(e.x)
        if self.mode!='cursor':self.set_boundary(self.mode,t)
        self.clock.configure(text=format_time(t))
    def up(self,e):
        if self.ready:self.player.seek(self.time_at(e.x)-self.lo)
        self.mode=None
    def position(self,t):
        self.clock.configure(text=format_time(self.lo+t));self.draw()
        if self.player.playing and self.lo+t>=self.end:self.player.stop()
    def toggle(self):
        if self.ready:
            if self.player.playing:self.player.stop()
            else:self.player.seek(self.start-self.lo,True)
    def read_values(self):
        try:
            a,b,t=[parse_time(v.get()) for v in self.values]
            if not self.lo-.001<=a<=t<=b<=self.hi+.001 or b-a<.5:raise ValueError('Границы должны оставаться внутри игровой сцены; длина не меньше 0,5 с.')
            self.start,self.end,self.event=a,b,t;self.draw();return True
        except ValueError as error:self.status.set(str(error));return False
    def apply(self):
        if self.read_values():self.on_apply(self.start,self.end,self.event);self.close()
    def poll(self):
        if self.closed:return
        try:
            while True:
                kind,value=self.jobs.get_nowait()
                if kind=='ready':
                    self.photos=[ImageTk.PhotoImage(Image.open(p).copy()) for p in sorted(self.folder.glob('thumb-*.jpg'))]
                    self.ready=True;self.player.load(value,None,self.hi-self.lo,position=self.start-self.lo);self.draw()
                else:self.status.set(value)
        except queue.Empty:pass
        self.poll_id=self.window.after(60,self.poll)
    def close(self):
        self.closed=True;self.cancel.set();self.player.close();self.window.after_cancel(self.poll_id)
        self.window.destroy()
        if self.parent.winfo_exists():self.parent.grab_set()
