"""Static face-guided portrait crop. Coordinates refer to the displayed, rotated frame."""
import hashlib,json,math
from pathlib import Path
from PIL import Image
from .media import probe,run
from .video_color import sdr_filter

def signature(path,rotation):
 st=Path(path).stat()
 return hashlib.sha256(json.dumps([st.st_size,st.st_mtime_ns,rotation,'portrait-v1']).encode()).hexdigest()

def dimensions(path,rotation=0):
 info=probe(path);w,h=info['width'],info['height']
 if round(info.get('rotation',0))%180:w,h=h,w
 if rotation%180:w,h=h,w
 return w,h

def validate(value):
 out={k:float(value.get(k,v)) for k,v in [('x',.5),('y',.5),('zoom',1.)]}
 if not all(math.isfinite(v) for v in out.values()) or not 0<=out['x']<=1 or not 0<=out['y']<=1 or not 1<=out['zoom']<=2:raise ValueError('Проверьте положение и масштаб кадра.')
 return out

def rectangle(w,h,value):
 v=validate(value);ch=min(h,w*16/9)/v['zoom'];cw=ch*9/16
 cw=max(2,int(cw)//2*2);ch=max(2,int(ch)//2*2)
 x=round(max(0,min(w-cw,v['x']*w-cw/2)))//2*2
 y=round(max(0,min(h-ch,v['y']*h-ch/2)))//2*2
 return x,y,cw,ch

def rotation_filter(rotation):
 return {0:'',90:'transpose=clock,',180:'hflip,vflip,',270:'transpose=cclock,'}[rotation%360]

def detect(path,rotation,cache,cancel=None):
 import cv2,numpy as np
 key=signature(path,rotation);folder=Path(cache)/'portrait'/key;folder.mkdir(parents=True,exist_ok=True)
 saved=folder/'result.json'
 if saved.exists():return json.loads(saved.read_text()),folder/'preview.jpg'
 detector=cv2.CascadeClassifier(str(Path(cv2.data.haarcascades)/'haarcascade_frontalface_default.xml'))
 duration=probe(path)['duration'];votes=[];frames=[]
 for i,t in enumerate([duration*f for f in (.12,.3,.5,.7,.85)]):
  target=folder/f'{i}.jpg'
  run(['-y','-ss',t,'-i',path,'-frames:v','1','-vf',sdr_filter(path)+rotation_filter(rotation)+'scale=640:640:force_original_aspect_ratio=decrease','-q:v','2',target],cancel)
  with Image.open(target) as im:
   rgb=np.array(im.convert('RGB'));h,w=rgb.shape[:2]
  faces=detector.detectMultiScale(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),scaleFactor=1.08,minNeighbors=5,minSize=(35,35))
  if len(faces):
   x,y,fw,fh=max(faces,key=lambda b:b[2]*b[3])
   votes.append(((x+fw/2)/w,(y+fh/2)/h,i))
  frames.append(target)
 if votes:
  x=float(np.median([v[0] for v in votes]));fy=float(np.median([v[1] for v in votes]))
  chosen=min(votes,key=lambda v:abs(v[0]-x))[2]
  y=min(1.,fy+.2);confident=len(votes)>=2
 else:x=y=.5;chosen=2;confident=False
 result=dict(x=x,y=y,zoom=1.,signature=key,rotation=rotation,approved=False,face_found=confident)
 with Image.open(frames[chosen]) as im:im.save(folder/'preview.jpg')
 saved.write_text(json.dumps(result));return result,folder/'preview.jpg'

def entry(project,path,rotation,cache,cancel=None):
 value=project.host_framing.get(path)
 if value and value.get('signature')==signature(path,rotation):
  validate(value);return value
 value,_=detect(path,rotation,cache,cancel);project.host_framing[path]=value
 return value

def filter_for(project,path,rotation,cache,cancel=None,original=None):
 if not project.profile.endswith('_shorts'):return ''
 w,h=dimensions(path,rotation)
 if w<=h:return ''
 original=original or path
 value=entry(project,original,rotation,cache,cancel)
 x,y,cw,ch=rectangle(w,h,value)
 return f'crop={cw}:{ch}:{x}:{y},'

def preview(image,value,mirror=False):
 x,y,w,h=rectangle(image.width,image.height,value)
 result=image.crop((x,y,x+w,y+h)).resize((288,512),Image.Resampling.LANCZOS)
 if mirror:result=result.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
 return result

def pending(project):
 if not project.profile.endswith('_shorts'):return []
 result=[]
 for path in project.host_paths():
  # Automatic orientation is confirmed during detection; display metadata applies here.
  rotation=0 if project.settings.auto_rotate else project.settings.rotate
  if dimensions(path,rotation)[0]<=dimensions(path,rotation)[1]:continue
  value=project.host_framing.get(path,{})
  if not value.get('approved') or value.get('signature')!=signature(path,value.get('rotation',rotation) if project.settings.auto_rotate else rotation):result.append(path)
 return result
