"""Validated per-draft overrides; omitted values inherit the selected preset."""
from dataclasses import fields
from .model import Settings
import math

def validate(values):
    if not isinstance(values,dict):raise ValueError('Ожидается список настроек.')
    defaults=Settings();allowed={f.name for f in fields(defaults)}
    ranges={'zoom_max':(1,1.4),'noise_reduction':(1,20),'music_db':(-60,-15)}
    choices={'rotate':(0,90,180,270),'insert_frequency':('low','normal','high'),'width':(720,1080,1280,1920),'height':(720,1080,1280,1920),'fps':(30,)}
    for key,value in values.items():
        if key not in allowed:raise ValueError('Неизвестная настройка: '+key)
        old=getattr(defaults,key)
        if type(value)!=type(old) and not(type(old)==float and type(value)==int):raise ValueError('Неверное значение: '+key)
        if type(value) in (int,float) and not math.isfinite(value):raise ValueError('Некорректное число.')
        if key in ranges and not ranges[key][0]<=value<=ranges[key][1]:raise ValueError('Значение вне диапазона: '+key)
        if key in choices and value not in choices[key]:raise ValueError('Недопустимое значение: '+key)
    return dict(values)


def apply(settings, values, profile):
    from dataclasses import replace
    candidate=replace(settings,**validate(values))
    sizes=((720,1280),(1080,1920)) if profile.endswith('_shorts') else ((1280,720),(1920,1080))
    if (candidate.width,candidate.height) not in sizes:
        raise ValueError('Выберите согласованные ширину и высоту: '+', '.join(f'{w}×{h}' for w,h in sizes))
    return candidate
