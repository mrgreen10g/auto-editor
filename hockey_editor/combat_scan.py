"""Reviewable fight proposals require a running round clock and local action."""
from dataclasses import asdict
import json,re,shutil
import numpy as np
from PIL import Image
from .media import probe,run

DETECTOR_VERSION='combat-selective-review-v4'


def clock_value(text):
    m=re.fullmatch(r'\s*(0?[0-5])\s*[:.]\s*([0-5]\d)\s*',text)
    return int(m[1])*60+int(m[2]) if m else None


def live_ranges(observations,duration):
    intervals=[]
    for a,b in zip(observations,observations[1:]):
        if a[1] is None or b[1] is None:continue
        delta=b[0]-a[0]
        if 0<delta<=2.1 and 0<abs(a[1]-b[1])<=delta+1:
            if intervals and abs(intervals[-1][1]-a[0])<.01:intervals[-1][1]=b[0]
            else:intervals.append([a[0],b[0]])
    return [[a+.5,min(duration,b)-.5] for a,b in intervals if b-a>=5]


def motion_score(previous,current):
    import cv2
    flow=cv2.calcOpticalFlowFarneback(previous,current,None,.5,2,12,2,5,1.1,0)
    flow-=np.median(flow.reshape(-1,2),axis=0)
    return float(np.percentile(np.linalg.norm(flow,axis=2),85))


def scan(source,scanner):
    import cv2
    from .goals import Candidate,source_signature
    scanner.check();signature=source_signature(source);folder=scanner.root/signature[:24];folder.mkdir(parents=True,exist_ok=True)
    saved=folder/'goals.json'
    if saved.exists():
        data=json.loads(saved.read_text(encoding='utf-8'))
        if data.get('signature')==signature and data.get('detector_version')==DETECTOR_VERSION and data.get('fighter')==source.fighter:return data
    info=probe(source.path);duration=info['duration']
    if not info['video'] or not 5<=duration<=4*3600:raise ValueError('Нужна видеозапись боя от 5 секунд до 4 часов.')
    visual=folder/'combat-frames';visual.mkdir(exist_ok=True)
    scanner.log('Бои: ищу идущие раунды по таймеру и активные размены. Уверенные фрагменты будут выбраны автоматически.')
    try:
        from rapidocr_onnxruntime import RapidOCR
        import onnxruntime
        onnxruntime.disable_telemetry_events()
        ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1,det_limit_type='max',det_limit_side_len=960)
        run(['-y','-i',source.path,'-an','-vf','fps=2,scale=960:540','-q:v','3','-start_number','0',visual/'%06d.jpg'],scanner.cancel)
        files=sorted(visual.glob('*.jpg'));observations=[];motion=[];cuts=[];previous=None;clock_box=None
        for i,path in enumerate(files):
            scanner.check()
            with Image.open(path) as im:rgb=np.asarray(im.convert('RGB'))
            gray=cv2.cvtColor(cv2.resize(rgb,(240,135)),cv2.COLOR_RGB2GRAY)
            movement=motion_score(previous,gray) if previous is not None else 0.
            cut=previous is not None and np.abs(gray.astype(float)-previous).mean()>45
            if cut:movement=0.
            cuts.append(bool(cut))
            motion.append(movement);previous=gray
            if i%4:continue
            bgr=rgb[:,:,::-1].copy();value=None;certainty=0.
            if clock_box:
                x1,y1,x2,y2=clock_box;result,_=ocr(bgr[y1:y2,x1:x2],use_det=False,use_cls=False)
                if result and float(result[0][1])>=.6:value=clock_value(result[0][0]);certainty=float(result[0][1])
            if value is None:
                for y1,y2 in ((350,540),(0,145)):
                    result,_=ocr(bgr[y1:y2],use_cls=False)
                    for box,text,confidence in result or []:
                        found=clock_value(text)
                        if found is None or confidence<.7:continue
                        xs=[p[0] for p in box];ys=[p[1]+y1 for p in box]
                        clock_box=(max(0,int(min(xs))-5),max(0,int(min(ys))-3),min(960,int(max(xs))+5),min(540,int(max(ys))+3));value=found;certainty=float(confidence);break
                    if value is not None:break
            observations.append([i/2,value,certainty])
            if i%120==0:scanner.log(f'Боевая запись: проверено {i/2:.0f} с')
        ranges=live_ranges(observations,duration);candidates=[]
        for lo,hi in ranges:
            start=lo
            while hi-start>=2.5:
                end=min(hi,start+3.5);indices=list(range(int((start+.5)*2),min(len(motion),int((end-.5)*2)+1)))
                peak=max(indices,key=lambda i:motion[i]) if indices else None
                if peak is not None and motion[peak]>=.8:
                    strong=confident_action(start,end,observations,motion,cuts)
                    note='Идущий раунд, устойчивый таймер и активное движение без смены кадра.' if strong else 'Активное движение найдено, но таймер или непрерывность сцены требуют проверки.'
                    candidates.append(Candidate(f'combat-{len(candidates)}',None,None,peak/2,start,end,.86 if strong else .7,note,kind='play'))
                start=end+2
        data={'detector_version':DETECTOR_VERSION,'fighter':source.fighter,'signature':signature,'duration':duration,'candidates':[asdict(c) for c in candidates],'observations':observations,'gameplay_ranges':ranges,'ranges':ranges,'box':None,'note':'Если таймер не виден, задайте фрагмент вручную. Уверенные активные фрагменты выбираются автоматически; сомнительные требуют проверки.'}
        tmp=saved.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');tmp.replace(saved)
        scanner.log(f'Боевых фрагментов для просмотра: {len(candidates)}');return data
    finally:shutil.rmtree(visual,ignore_errors=True)


def confident_action(start,end,observations,motion,cuts):
    """Evidence for generic active-fight B-roll, not a claim of a landed punch."""
    points=[o for o in observations if start-2.1<=o[0]<=end+2.1]
    if len(points)<3 or points[0][0]>start or points[-1][0]<end:return False
    if any(len(o)<3 or o[1] is None or o[2]<.8 for o in points):return False
    direction=None
    for a,b in zip(points,points[1:]):
        dt=b[0]-a[0];dv=b[1]-a[1]
        if not 0<dt<=2.1 or abs(abs(dv)-dt)>1 or dv==0:return False
        sign=1 if dv>0 else -1
        if direction is not None and sign!=direction:return False
        direction=sign
    lo=max(0,int(start*2));hi=min(len(motion),int(end*2)+1)
    local=motion[lo:hi]
    return bool(len(local)>=5 and not any(cuts[lo:hi]) and max(local)>=1.2 and sum(v>=.8 for v in local)/len(local)>=.5)
