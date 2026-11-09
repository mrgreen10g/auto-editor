"""Machine-local resource budgets; never alter media quality settings."""
import os
from . import preferences
LABELS={'old':'Старый сервер · 8 ГБ','new':'Новый сервер · Ryzen, 16 ГБ'}
def mode():
    value=preferences.read().get('processing_machine','old')
    return value if value in LABELS else 'old'
def save(value):
    if value not in LABELS:raise ValueError('Неизвестный режим сервера')
    data=preferences.read();data['processing_machine']=value;preferences.write(data)
def budget(kind):
    count=max(1,os.cpu_count() or 2)
    limits={'speech':(6,7),'encode':(4,7),'filters':(2,4),'decode':(2,3)}
    old,new=limits[kind]
    return max(1,min(new if mode()=='new' else old,count-1 if count>1 else 1))
def ffmpeg_args(args):
    args=list(args)
    if mode()!='new':return args
    # Keep per-input thread limits: large montages open many decoders.
    last_input=max((i for i,v in enumerate(args) if v=='-i'),default=-1)
    for i,v in enumerate(args[:-1]):
        if v=='-filter_complex_threads':args[i+1]=str(budget('filters'))
        elif v=='-threads' and i>last_input and str(args[i+1])=='4':args[i+1]=str(budget('encode'))
    return args
