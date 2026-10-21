"""Stage one: a reusable video bed and export-generated live card artwork.

The bed key deliberately excludes text cards/logos. It includes all actual
video/audio inputs and settings. No client-supplied path is served.
"""
import base64,copy,hashlib,json
from dataclasses import asdict
from pathlib import Path
from .live_cards import base_key,base_plan
from .mini_server import RemoteError


def identity(path):
    if not path:return None
    p=Path(path)
    try:
        s=p.stat()
        with p.open('rb') as f:
            sample=f.read(4096)
            if s.st_size>4096:f.seek(max(4096,s.st_size-4096));sample+=f.read(4096)
        return [str(p.resolve()),s.st_size,s.st_mtime_ns,hashlib.sha256(sample).hexdigest()]
    except OSError:return [str(p),'missing']


def key(project,plan):
    paths=set(project.host_paths()+[project.music])
    paths.update(m['path'] for m in plan.media)
    paths.update(v.path for v in plan.inserts)
    paths.update(c.asset for c in plan.cards if c.asset)
    settings=asdict(project.settings)
    # Animation of text is evaluated live; transitions also affect video.
    settings.pop('animate_cards',None)
    content=['live-bed-v1',project.profile,settings,base_key(plan,project),[identity(p) for p in sorted(paths)]]
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def scene(bridge,data):
    bridge.check_revision(data);app=bridge.app
    if not app.plan:raise RemoteError('Сначала определите тайминги.')
    from .timeline import game_transitions
    from .shorts import panel_intervals
    p=app.plan;s=app.project.settings
    return dict(key=key(app.project,p),width=720 if app.project.profile.endswith('_shorts') else 1280,
                height=1280 if app.project.profile.endswith('_shorts') else 720,duration=p.duration,
                settings=dict(transitions=s.transitions,animate_cards=s.animate_cards,wobble=s.wobble),
                panels=panel_intervals(p) if app.project.profile.endswith('_shorts') else [],
                games=[(v.start,v.end+tail) for v,tail,_,_ in game_transitions(p)],
                cards=[dict(id=f'card:{i}',index=i,**asdict(c)) for i,c in enumerate(p.cards) if not c.asset and c.title not in ('АРХИВНЫЕ КАДРЫ','КАДРЫ МАТЧА')])


def artwork(bridge,data):
    bridge.check_revision(data);app=bridge.app
    try:
        kind,index=str(data['id']).split(':');index=int(index)
        if kind!='card' or index<0:raise ValueError()
        c=copy.deepcopy(app.plan.cards[index])
    except (ValueError,IndexError,AttributeError):raise RemoteError('Плашка не найдена.',404) from None
    if c.asset:raise RemoteError('Этот элемент относится к видеослою.')
    # A draft text preview never mutates the project. Geometry stays in the
    # manifest, so drag/scale requires neither PNG generation nor a request.
    if 'text' in data:
        c.text=str(data['text']).strip()
        if not c.text or len(c.text)>4000:raise RemoteError('Введите текст до 4000 символов.')
    c.offset_x=c.offset_y=0;c.scale=1
    digest=hashlib.sha256(json.dumps([c.title,c.text,c.fixture,app.project.profile,
        {k:identity(v) for k,v in app.project.team_logos.items()}],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    cache=Path(app.cache_path())/'mobile-live-art';cache.mkdir(parents=True,exist_ok=True)
    path=cache/(digest+'.png');meta=cache/(digest+'.json')
    from .graphics import card_image
    from PIL import Image
    if not path.exists() or not meta.exists():
        x,y=card_image(c,path,app.project.team_logos,app.project.profile)
        with Image.open(path) as im:width,height=im.size
        meta.write_text(json.dumps(dict(x=x,y=y,width=width,height=height)))
    result=json.loads(meta.read_text())
    return dict(**result,image=base64.b64encode(path.read_bytes()).decode())


def prepare(bridge,data):
    app=bridge.app
    if not app.plan:raise RemoteError('Сначала определите тайминги.')
    digest=key(app.project,app.plan)
    from .mini_preview import snapshot
    from .timeline import Card
    marker=Card(0,app.plan.duration,'','Предпросмотр',review_id='__mobile_preview__')
    spec=snapshot(app.project,app.plan,app.index,dict(id=marker.review_id),marker,
                  dict(start=0,end=app.plan.duration,timeline=True))
    spec['plan']=base_plan(spec['plan'])
    spec['live_key']=digest
    return spec,digest
