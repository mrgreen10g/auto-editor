"""Bounded montage previews using the same compositor as the final export.

Work on detached snapshots only. Decode short source spans before invoking the
renderer, so a review preview never prepares the entire episode.
"""
import copy,math,threading,tempfile
from pathlib import Path
from .timeline import frame
from .host_media import slice_media
from .mini_server import RemoteError

def snapshot(project,plan,index,task,card,data):
    project=copy.deepcopy(project);plan=copy.deepcopy(plan)
    start=float(data.get('start',card.start));end=float(data.get('end',card.end))
    if not all(math.isfinite(v) for v in (start,end)) or not 0<=start<end<=plan.duration or end-start<.15:
        raise RemoteError('Границы плашки должны находиться внутри дорожки и длиться не менее 0,15 с.')
    selected=next((c for c in plan.cards if c.review_id==task['id']),None)
    if selected is None:
        selected=copy.deepcopy(card);plan.cards.append(selected)
    selected.start=frame(start);selected.end=frame(end)
    selected.text=str(data.get('text',card.text)).strip()
    if not selected.text or len(selected.text)>4000:raise RemoteError('Введите текст плашки (до 4000 символов).')
    owner=str(data.get('owner',selected.forecast_id))
    if owner and owner not in {b.uid for b in project.blocks}:raise RemoteError('Матч для ставки не найден.')
    if data.get('card_type'):
        from .mobile_editing import card_type
        card_type(selected,str(data['card_type']),owner,project)
        if selected.title!='ПРОГНОЗ':owner=''
    selected.forecast_id=owner
    if owner:
        for other in plan.cards:
            if other.forecast_id==owner:other.text=selected.text
    # Keep one second around the card; long cards get a clearly labelled excerpt.
    lo=frame(max(0,start-1));hi=frame(min(plan.duration,end+1,lo+20))
    media=plan.media or [dict(path=project.host,start=plan.source_start+a,end=plan.source_start+b,rotation=plan.rotation or 0,kind='host') for a,b in plan.keep]
    plan.media=slice_media(media,lo,hi)
    plan.duration=frame(sum(m['end']-m['start'] for m in plan.media))
    if plan.duration<.15:raise RemoteError('Недостаточно видео для предпросмотра.')
    plan.source_start=0;plan.source_end=plan.duration;plan.keep=[(0,plan.duration)]
    def crop(items,source=False):
        result=[]
        for item in items:
            a=max(lo,item.start);b=min(hi,item.end)
            if b-a<.15:continue
            if source:item.source_in=frame(item.source_in+a-item.start)
            if hasattr(item,'line'):item.line=-1
            if hasattr(item,'words'):
                offset=a-item.start
                item.words=[{**w,'start':max(0,w['start']-offset),'end':min(b-a,w['end']-offset)} for w in item.words if w['end']>offset and w['start']<b-item.start]
            item.start=frame(a-lo);item.end=frame(b-lo);result.append(item)
        return result
    plan.cards=crop(plan.cards,True);plan.inserts=crop(plan.inserts,True);plan.lines=crop(plan.lines)
    # Section boundaries still prevent transitions from joining different games.
    plan.sections=[{**s,'start':frame(max(lo,s['start'])-lo),'end':frame(min(hi,s['end'])-lo)} for s in plan.sections if min(hi,s['end'])-max(lo,s['start'])>=.15]
    # Tiny clipped section edges can be below the renderer's validation minimum.
    # They affect neither source selection nor the selected card.
    if plan.sections and (plan.sections[0]['start']>.001 or abs(plan.sections[-1]['end']-plan.duration)>.035):plan.sections=[]
    plan.review_items=[];plan.edit_baseline={}
    return dict(mode='context',project=project,plan=plan,index=index,offset=lo)

def render(spec,cache,ident):
    from .media import run
    from .engine import Engine
    target=cache/(ident+'.mp4');plan=copy.deepcopy(spec['plan']);project=spec['project']
    with tempfile.TemporaryDirectory(prefix='context-',dir=cache) as temporary:
        root=Path(temporary)
        for i,span in enumerate(plan.media):
            path=root/f'host-{i}.mp4';duration=span['end']-span['start']
            # Input seeking bounds decoding. FFmpeg applies container rotation;
            # the compositor subsequently applies the recorded manual correction.
            run(['-y','-threads','2','-ss',span['start'],'-t',duration,'-i',span['path'],'-map','0:v:0','-map','0:a:0?',
                 '-vf','scale=1280:1280:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1','-r','30',
                 '-c:v','libx264','-preset','ultrafast','-crf','23','-threads','2','-c:a','aac',path])
            span.update(path=str(path),start=0,end=duration)
        output=root/'preview.mp4'
        Engine(project,spec['index'],root/'render',threading.Event()).render(plan,output,draft=True)
        output.replace(target)
    return dict(file=str(target))

