"""Asynchronous, revision-bound portrait framing review for Mini App."""
import base64,copy,secrets,threading
from pathlib import Path
from .mini_server import RemoteError
from . import shorts_framing as framing

def handle(bridge,kind,data):
 app=bridge.app
 if kind=='portrait-start':
  bridge.check_revision(data)
  if bridge.locked():raise RemoteError('Дождитесь завершения обработки.',409)
  paths=app.project.host_paths() if data.get('force') else framing.pending(app.project)
  rotation=0 if app.project.settings.auto_rotate else app.project.settings.rotate
  paths=[p for p in paths if framing.dimensions(p,rotation)[0]>framing.dimensions(p,rotation)[1]] if app.project.profile.endswith('_shorts') else []
  if not paths:return dict(ready=True,items=[])
  previous=getattr(bridge,'portrait_job',None)
  if previous and previous['status']=='running':return dict(job=previous['id'])
  job=dict(id=secrets.token_hex(16),revision=bridge.revision(),status='running',items=[])
  bridge.portrait_job=job
  project=copy.deepcopy(app.project);cache=app.cache_path()
  def work():
   try:
    from .orientation import detect_rotation
    items=[]
    for path in paths:
     rot=detect_rotation(path,cache,None) if project.settings.auto_rotate else project.settings.rotate
     auto,image=framing.detect(path,rot,cache)
     current=project.host_framing.get(path,auto)
     if current.get('signature')!=auto['signature']:current=auto
     items.append(dict(path=path,name=Path(path).name,automatic=auto,value=current,image='data:image/jpeg;base64,'+base64.b64encode(image.read_bytes()).decode()))
    job['items']=items;job['mirror']=project.settings.mirror_host;job['status']='ready'
   except Exception as error:job['error']=str(error);job['status']='error'
  threading.Thread(target=work,daemon=True).start();return dict(job=job['id'])
 job=getattr(bridge,'portrait_job',None)
 if not job or data.get('job')!=job['id']:raise RemoteError('Предпросмотр устарел. Откройте кадрирование снова.',409)
 if kind=='portrait-status':
  return {k:v for k,v in job.items() if k!='items'}|dict(items=[{k:v for k,v in item.items() if k!='path'} for item in job['items']])
 if kind!='portrait-save':raise RemoteError('Неизвестное действие.')
 bridge.check_revision({'revision':job['revision']})
 if bridge.locked() or job['status']!='ready':raise RemoteError('Дождитесь предпросмотра.',409)
 values=data.get('values')
 if not isinstance(values,list) or len(values)!=len(job['items']):raise RemoteError('Проверьте все части ведущего.')
 clean=[framing.validate(v) for v in values]
 for item,value in zip(job['items'],clean):
  app.project.host_framing[item['path']]={**item['automatic'],**value,'approved':True}
 app.result=None;bridge.checkpoint();job['status']='saved'
 return dict(ok=True,revision=bridge.revision())
