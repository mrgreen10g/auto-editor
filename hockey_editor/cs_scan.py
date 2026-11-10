"""Sparse HUD-clock checks, not score or action matching, for archive CS footage."""
from dataclasses import asdict
import re
from PIL import Image
import numpy as np
from .media import probe

def clock(text):
 m=re.fullmatch(r'\s*([0-2])[:.]([0-5]\d)\s*',text)
 return int(m[1])*60+int(m[2]) if m else None

def candidates(points,duration):
 from .goals import Candidate
 result=[];last=-10
 for a,b,c in zip(points,points[1:],points[2:]):
  if a[0]<last or any(p[1] is None or p[2]<.75 for p in (a,b,c)):continue
  if not all(0<q[0]-p[0]<=2.1 and abs((p[1]-q[1])-(q[0]-p[0]))<=.8 for p,q in ((a,b),(b,c))):continue
  start=a[0];end=min(c[0],duration)
  if end-start<3.5:continue
  result.append(Candidate('cs-'+str(len(result)),None,None,(start+end)/2,start,end,.85,'Архив CS: проверен идущий раунд. Не подтверждает названный счёт или конкретное действие.',kind='play'));last=end+6
 return result

def scan(source,scanner):
 from .goals import source_signature
 from .scan_cache import single_frames
 from .processing_cache import read_json,write_json
 from rapidocr_onnxruntime import RapidOCR
 signature=source_signature(source);folder=scanner.root/signature[:24];folder.mkdir(parents=True,exist_ok=True)
 saved=folder/'goals.json';data=read_json(saved,{})
 if data.get('signature')==signature:return data
 duration=probe(source.path)['duration']
 if not 5<=duration<=4*3600:raise ValueError('Нужна запись CS от 5 секунд до 4 часов.')
 scanner.log('CS: ищу архивные игровые кадры по таймеру раунда, без точного счёта.')
 visual=folder/'cs-frames';visual.mkdir(exist_ok=True)
 files=single_frames(source,visual,duration,.5,'960:540',scanner.cancel,scanner.log)
 ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
 checkpoint=folder/'cs-hud.json';points=read_json(checkpoint,[])
 for i in range(len(points),len(files)):
  scanner.check();value=None;certainty=0.
  if i%10<3:
   with Image.open(files[i]) as im:rgb=np.asarray(im.convert('RGB'))
   result,_=ocr(rgb[:125,290:670,::-1].copy(),use_cls=False)
   for _,text,confidence in result or []:
    v=clock(text)
    if v is not None and confidence>certainty:value=v;certainty=float(confidence)
  points.append([i*2,value,certainty])
  if i%100==0:write_json(checkpoint,points)
 write_json(checkpoint,points);clips=candidates(points,duration)
 data=dict(signature=signature,duration=duration,candidates=[asdict(c) for c in clips],observations=[],ranges=[],box=None)
 write_json(saved,data)
 import shutil
 shutil.rmtree(visual,ignore_errors=True)
 scanner.log(f'CS: готово архивных вставок — {len(clips)}.');return data
