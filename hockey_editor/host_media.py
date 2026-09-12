"""Ordered source recordings: concatenate PCM for analysis, retain original video."""
from pathlib import Path
import hashlib,json,math
from .media import probe,run
from .timeline import frame


def identity(path):
    if not path:return None
    p=Path(path);st=p.stat()
    return [str(p.resolve()),st.st_size,st.st_mtime_ns]


def sources(project):
    result=[];cursor=0
    for path in project.host_paths():
        info=probe(path)
        if not info['video'] or not info['audio']:raise ValueError('У каждой части ведущего должны быть видео и голос: '+Path(path).name)
        duration=math.floor(info['duration']*30)/30
        result.append({'path':path,'offset':cursor,'duration':duration});cursor=frame(cursor+duration)
    if cursor>1800:raise ValueError('Суммарная запись ведущего должна быть не длиннее 30 минут.')
    return result


def analysis_source(project,cache,cancel,log):
    parts=sources(project)
    if len(parts)==1:return project.host,parts[0]['duration'],parts
    key=hashlib.sha256(json.dumps([identity(p['path']) for p in parts]).encode()).hexdigest()
    root=Path(cache).parent/'host-audio';root.mkdir(exist_ok=True)
    path=root/(key+'.wav')
    if not path.exists():
        log('Соединяю только звук частей для поиска речи. Исходное видео не перекодируется.')
        args=['-y'];filters=[]
        for i,p in enumerate(parts):
            args+=['-i',p['path']]
            filters.append(f'[{i}:a]aresample=16000,aformat=sample_fmts=s16:channel_layouts=mono,apad,atrim=duration={p["duration"]:.6f},asetpts=PTS-STARTPTS[a{i}]')
        filters.append(''.join(f'[a{i}]' for i in range(len(parts)))+f'concat=n={len(parts)}:v=0:a=1[audio]')
        partial=path.with_suffix('.partial.wav')
        try:
            run(args+['-filter_complex',';'.join(filters),'-map','[audio]','-c:a','pcm_s16le',partial],cancel)
            partial.replace(path)
        finally:partial.unlink(missing_ok=True)
    return str(path),frame(sum(p['duration'] for p in parts)),parts


def media_ranges(project,plan,parts,cache,cancel,log):
    from .orientation import detect_rotation
    result=[];rotations={}
    for a,b in plan.keep:
        a+=plan.source_start;b+=plan.source_start
        for part in parts:
            lo=max(a,part['offset']);hi=min(b,part['offset']+part['duration'])
            if hi-lo<.001:continue
            path=part['path']
            if path not in rotations:
                rotations[path]=detect_rotation(path,cache,cancel,log) if project.settings.auto_rotate else project.settings.rotate
            result.append({'path':path,'start':frame(lo-part['offset']),'end':frame(hi-part['offset']),
                           'rotation':rotations[path],'kind':'host'})
    return result


def slice_media(media,start,end):
    result=[];cursor=0
    for m in media:
        n=m['end']-m['start'];lo=max(cursor,start);hi=min(cursor+n,end)
        if hi>lo+.001:result.append({**m,'start':frame(m['start']+lo-cursor),'end':frame(m['start']+hi-cursor)})
        cursor+=n
    return result


def prepare_base(engine,plan,base):
    """Decode original files into one concat filter, with per-part orientation."""
    p=engine.project;s=p.settings
    groups=[]
    for segment in plan.media:
        if groups and all(segment.get(k)==groups[-1][-1].get(k) for k in ('path','rotation','kind')) and segment['start']>=groups[-1][-1]['end']-.001:
            groups[-1].append(segment)
        else:groups.append([segment])
    paths=[g[0]['path'] for g in groups];args=['-y'];fl=[]
    for j,group in enumerate(groups):
        m=group[0];path=m['path'];args+=['-threads','2','-i',path]
        select='+'.join(f'between(n,{round(v["start"]*30)},{round(v["end"]*30)-1})' for v in group)
        video="fps=30,select='"+select+"',setpts=N/(30*TB)"
        rot=m.get('rotation',0)
        if rot==180:video+=',hflip,vflip'
        elif rot==90:video+=',transpose=clock'
        elif rot==270:video+=',transpose=cclock'
        video+=',scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p'
        if s.color and m.get('kind')!='disclaimer':video+=',eq=contrast=1.045:saturation=1.035:brightness=-0.004'
        duration=sum(v['end']-v['start'] for v in group)
        # One video stream per source keeps memory bounded, even with hundreds of speech cuts.
        video+=f',tpad=stop_mode=clone:stop_duration=0.05,trim=duration={duration:.6f}'
        fl.append(f'[{j}:v]{video}[v{j}]')
        if probe(path)['audio']:
            fl.append(f'[{j}:a]asplit={len(group)}'+''.join(f'[raw{j}_{k}]' for k in range(len(group))))
            for k,v in enumerate(group):
                fl.append(f'[raw{j}_{k}]atrim=start={v["start"]:.6f}:end={v["end"]:.6f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={v["end"]-v["start"]:.6f}[cut{j}_{k}]')
            fl.append(''.join(f'[cut{j}_{k}]' for k in range(len(group)))+f'concat=n={len(group)}:v=0:a=1[a{j}]')
        else:fl.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={duration:.6f}[a{j}]')
    n=len(groups)
    fl.append(''.join(f'[v{j}][a{j}]' for j in range(n))+f'concat=n={n}:v=1:a=1[video][joined]')
    # Apply continuous voice processing once, not independently per word/kept span.
    head=next((m['end']-m['start'] for m in plan.media if m.get('kind')=='disclaimer'),0)
    if head:
        fl+=['[joined]asplit=2[rawhead][rawvoice]',f'[rawhead]atrim=duration={head:.6f},asetpts=PTS-STARTPTS[head]']
        voice=f'[rawvoice]atrim=start={head:.6f},asetpts=PTS-STARTPTS,highpass=f=70'
    else:voice='[joined]highpass=f=70'
    if s.denoise:voice+=f',afftdn=nr={s.noise_reduction}:nf=-40:tn=1'
    voice+=',loudnorm=I=-16:TP=-2:LRA=9,aresample=48000[processed]';fl.append(voice)
    if head:fl.append('[head][processed]concat=n=2:v=0:a=1[voice]')
    else:fl.append('[processed]anull[voice]')
    if p.music:
        args+=['-stream_loop','-1','-i',p.music];idx=len(paths)
        fl.append(f'[{idx}:a]atrim=duration={plan.duration:.6f},asetpts=PTS-STARTPTS,loudnorm=I={s.music_db}:TP=-9:LRA=7,aresample=48000,afade=t=in:d=1,afade=t=out:st={max(0,plan.duration-2)}:d=2[bed]')
        fl+=['[voice]asplit=2[vmain][vside]','[bed][vside]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=350[duck]',
             '[vmain][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.85:level=false:latency=true[audio]']
    else:fl.append('[voice]alimiter=limit=0.85:level=false:latency=true[audio]')
    graph=engine.cache/'multi-base-filter.txt';graph.write_text(';\n'.join(fl),encoding='utf-8')
    key=hashlib.sha256(json.dumps([plan.media,fl,[identity(path) for path in paths],identity(p.music)]).encode()).hexdigest()
    ready=engine.cache/'multi-base-ready.txt'
    if base.exists() and ready.exists() and ready.read_text()==key:return
    ready.unlink(missing_ok=True)
    run(args+['-filter_complex_threads','2','-filter_complex_script',graph,'-map','[video]','-map','[audio]',
              '-c:v','libx264','-preset','fast','-crf','19','-threads','4','-pix_fmt','yuv420p','-r','30',
              '-c:a','aac','-b:a','160k','-ar','48000','-t',plan.duration,base],engine.cancel,engine.cache/'base-render.log',
        lambda t:engine.log(f'Подготовка ведущего: {min(100,int(t/plan.duration*100))}%'))
    ready.write_text(key)
