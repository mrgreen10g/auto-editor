"""Embedded FFmpeg video preview with local Windows audio, no codec installation."""
import os
import queue
import subprocess
import threading
import time
import wave
from pathlib import Path
from PIL import Image, ImageTk
from .media import ffmpeg


class PreviewPlayer:
    def __init__(self,widget,on_position=lambda _:None,on_error=lambda _:None):
        self.widget=widget;self.on_position=on_position;self.on_error=on_error
        self.path=None;self.audio=None;self.duration=0;self.position=0
        self.playing=False;self.generation=0;self.proc=None;self.closed=False
        self.queue=queue.Queue(4);self.after=None;self.image=None
        self.started=None;self.base=0;self.index=0;self.pending=None
        self.audio_segment=None

    def load(self,path,audio,duration):
        self.stop();self.path=Path(path);self.audio=Path(audio);self.duration=duration
        self.seek(0)

    def stop(self):
        self.playing=False;self.generation+=1
        if os.name=='nt':
            import winsound
            winsound.PlaySound(None,0)
        if self.proc and self.proc.poll() is None:
            try:self.proc.terminate()
            except OSError:pass
        self.proc=None
        if self.after:
            try:self.widget.after_cancel(self.after)
            except Exception:pass
            self.after=None

    def toggle(self):
        if self.playing:self.stop()
        elif self.path:self.seek(0 if self.position>=self.duration-.1 else self.position,True)

    def seek(self,position,play=False):
        if not self.path or self.closed:return
        self.stop();self.position=max(0,min(float(position),max(0,self.duration-.04)))
        self.base=self.position;self.playing=play;self.started=None;self.index=0;self.pending=None
        generation=self.generation;frames=queue.Queue(4);self.queue=frames
        path,audio=self.path,self.audio;position=self.position
        def put(value):
            while generation==self.generation and not self.closed:
                try:frames.put(value,timeout=.1);return
                except queue.Full:pass
        def decode():
            proc=None;segment=None
            try:
                if play and os.name=='nt' and audio and audio.exists():
                    segment=audio.with_name(f'seek-{generation}.wav')
                    with wave.open(str(audio),'rb') as src, wave.open(str(segment),'wb') as dst:
                        dst.setparams(src.getparams());src.setpos(min(src.getnframes(),round(position*src.getframerate())))
                        while True:
                            chunk=src.readframes(16384)
                            if not chunk:break
                            if generation!=self.generation:return
                            dst.writeframesraw(chunk)
                if generation!=self.generation:return
                flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
                args=[ffmpeg(),'-hide_banner','-loglevel','error','-nostdin','-ss',str(position),'-i',str(path),
                      '-an','-vf','fps=15,scale=640:360','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
                proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=flags)
                if generation!=self.generation:proc.terminate();return
                self.proc=proc
                size=640*360*3
                while generation==self.generation:
                    data=bytearray()
                    while len(data)<size:
                        chunk=proc.stdout.read(size-len(data))
                        if not chunk:break
                        data.extend(chunk)
                    if len(data)<size:break
                    put(('frame',Image.frombytes('RGB',(640,360),bytes(data)),segment))
                    if not play:break
                put(('end',None,None))
            except Exception as error:put(('error',str(error),None))
            finally:
                if proc:
                    if proc.poll() is None:proc.terminate()
                    try:proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                    proc.stdout.close()
        threading.Thread(target=decode,daemon=True).start()
        self.tick(generation)

    def tick(self,generation):
        self.after=None
        if self.closed or generation!=self.generation:return
        if self.pending is None:
            try:self.pending=self.queue.get_nowait()
            except queue.Empty:
                self.after=self.widget.after(15,lambda:self.tick(generation));return
        kind,value,audio=self.pending
        if kind=='error':self.playing=False;self.on_error(value);return
        if kind=='end':
            if self.playing:self.stop();self.position=self.duration;self.on_position(self.position)
            return
        now=time.monotonic()
        if self.started is None:
            self.started=now
            if self.playing and audio:
                import winsound
                winsound.PlaySound(str(audio),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        due=self.started+self.index/15
        if self.playing and now<due:
            self.after=self.widget.after(max(1,int((due-now)*1000)),lambda:self.tick(generation));return
        width,height=self.widget.winfo_width(),self.widget.winfo_height()
        if width>50 and height>50:value.thumbnail((width,height),Image.Resampling.BILINEAR)
        self.image=ImageTk.PhotoImage(value)
        self.widget.configure(image=self.image,text='')
        self.position=min(self.duration,self.base+self.index/15)
        self.on_position(self.position);self.index+=1;self.pending=None
        if self.playing:self.after=self.widget.after(1,lambda:self.tick(generation))

    def close(self):
        self.closed=True;self.stop()
