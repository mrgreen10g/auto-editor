"""Machine-local resource budgets; never alter media quality settings."""
import os
from . import preferences
LABELS={'old':'Старый сервер · 8 ГБ','new':'Новый сервер · 8 vCPU, 16 ГБ'}
def mode():
    value=preferences.read().get('processing_machine','old')
    return value if value in LABELS else 'old'
def save(value):
    if value not in LABELS:raise ValueError('Неизвестный режим сервера')
    data=preferences.read();data['processing_machine']=value;preferences.write(data)
def budget(kind):
    count=max(1,os.cpu_count() or 2)
    limits={'speech':(6,7),'encode':(6,7),'filters':(3,4),'decode':(2,3)}
    old,new=limits[kind]
    if getattr(_local,'scan',False):return max(1,min(2,count-1 if count>1 else 1))
    return max(1,min(new if mode()=='new' else old,count-1 if count>1 else 1))
def ffmpeg_args(args):
    args=list(args)
    if getattr(_local,'scan',False):
        for i,v in enumerate(args[:-1]):
            if v=='-filter_complex_threads':args[i+1]='2'
        return args
    # Keep per-input thread limits: large montages open many decoders.
    last_input=max((i for i,v in enumerate(args) if v=='-i'),default=-1)
    for i,v in enumerate(args[:-1]):
        if v=='-filter_complex_threads':args[i+1]=str(budget('filters'))
        elif v=='-threads' and i>last_input and str(args[i+1])=='4':args[i+1]=str(budget('encode'))
    return args

# Each parallel scanner owns its OCR instance. Avoid multiplying four OCR
# threads by every scan, and avoid nested video-filter oversubscription.
import threading
from contextlib import contextmanager
_local=threading.local()
def scan_workers():
    if (os.cpu_count() or 1)<4:return 1
    if os.name=='nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        state=Memory();state.length=ctypes.sizeof(state)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)) and state.available<3*1024**3:return 1
    return 2
@contextmanager
def scan_budget():
    previous=getattr(_local,'scan',False);_local.scan=True
    try:yield
    finally:_local.scan=previous
