"""Conservative wide football shots; no score inference or crowd fallback."""
from pathlib import Path
from dataclasses import asdict
import json,shutil
import numpy as np
from PIL import Image
from .media import probe,run,Cancelled


def frame_features(path):
    import cv2
    with Image.open(path) as im:rgb=np.asarray(im.convert('RGB').resize((240,135)))
    roi=rgb[32:121,9:231];hsv=cv2.cvtColor(roi,cv2.COLOR_RGB2HSV)
    grass=((hsv[:,:,0]>=25)&(hsv[:,:,0]<=95)&(hsv[:,:,1]>45)&(hsv[:,:,2]>35)).astype(np.uint8)
    coverage=float(grass.mean());wide=coverage>.53 and (grass.mean(axis=0)>.38).mean()>=.78 and (grass.mean(axis=1)>.5).mean()>=.5
    _,_,objects,_=cv2.connectedComponentsWithStats(1-grass,8)
    closeup=any(s[3]>=50 and s[2]<roi.shape[1]*.7 and s[4]>250 for s in objects[1:])
    wide=wide and not closeup
    filled=cv2.morphologyEx(grass,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
    holes=(filled>grass).astype(np.uint8);_,_,stats,_=cv2.connectedComponentsWithStats(holes,8)
    players=sum(2<=s[4]<=95 and 2<=s[3]<=20 and s[2]<=2.5*s[3] for s in stats[1:])
    return rgb.mean(axis=2),bool(wide and players>=3),coverage,int(players)


def gameplay_ranges(files,duration,cancel,step=.25):
    states=[];previous=None
    for file in files:
        if cancel.is_set():raise Cancelled('Отменено.')
        gray,valid,_,_=frame_features(file)
        motion=float(np.abs(gray-previous).mean()/255) if previous is not None else 0
        states.append((valid,motion));previous=gray
    ranges=[];start=None
    for i in range(len(states)+1):
        valid=i<len(states) and states[i][0]
        if valid and start is None:start=i
        if not valid and start is not None:
            lo=start*step+step;hi=min(duration,(i-1)*step)-step
            motion=np.mean([s[1] for s in states[start+1:i]]) if i-start>1 else 0
            if hi-lo>=2.5 and motion>=.0025:ranges.append([round(lo,3),round(hi,3)])
            start=None
    return ranges


def scan(source,scanner):
    from .goals import source_signature
    from .gameplay import candidates_from_ranges
    scanner.check();signature=source_signature(source);folder=scanner.root/signature[:24];folder.mkdir(parents=True,exist_ok=True)
    saved=folder/'goals.json'
    if saved.exists():
        data=json.loads(saved.read_text(encoding='utf-8'))
        if data.get('signature')==signature:return data
    info=probe(source.path);duration=info['duration']
    if not info['video'] or not 5<=duration<=4*3600:raise ValueError('Нужна запись матча от 5 секунд до 4 часов.')
    scanner.log('Футбол: ищу непрерывную игру на поле, исключаю заставки, трибуны и крупные планы…')
    visual=folder/'football-frames';visual.mkdir(exist_ok=True)
    try:
        run(['-y','-i',source.path,'-an','-vf','fps=4,scale=480:270','-q:v','3','-start_number','0',visual/'%06d.jpg'],scanner.cancel)
        ranges=gameplay_ranges(sorted(visual.glob('*.jpg')),duration,scanner.cancel)
        candidates=candidates_from_ranges(ranges)
        data={'signature':signature,'duration':duration,'candidates':[asdict(c) for c in candidates],'observations':[], 'note':'Футбольные игровые сцены; счёт не используется.','gameplay_ranges':ranges,'ranges':ranges,'box':None}
        tmp=saved.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(saved)
        scanner.log(f'Найдено игровых сцен: {len(candidates)}.');return data
    finally:shutil.rmtree(visual,ignore_errors=True)
