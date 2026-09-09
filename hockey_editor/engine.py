"""A cancellable local pipeline. Source media and accepted exports are immutable."""
from pathlib import Path
import hashlib,json,re,math,os,shutil
from . import __version__
from .media import probe,run,audio_extract,Cancelled
from .alignment import align
from .timeline import Plan,Line,Card,keep_ranges,map_time,placements,zoom_windows,frame
from .graphics import card_image

class Engine:
    def __init__(self,project,index,cache,cancel,log=lambda _:None):
        self.project=project;self.index=index;self.cancel=cancel;self.log=log
        self.cache=Path(cache).resolve();self.cache.mkdir(parents=True,exist_ok=True)

    def check(self):
        if self.cancel.is_set():raise Cancelled('Отменено.')

    def signature(self):
        def stat(p):
            s=Path(p).stat();return [str(Path(p).resolve()),s.st_size,s.st_mtime_ns]
        data={'version':__version__+'-align2','host':stat(self.project.host),'script':self.project.blocks[self.index].script}
        return hashlib.sha256(json.dumps(data,ensure_ascii=False).encode()).hexdigest()

    def analyze(self):
        p=self.project;p.validate(self.index);self.check()
        from .goals import montage_block
        block=montage_block(p,self.index,self.cache,self.cancel)
        info=probe(p.host)
        if not info['audio'] or not info['video']:raise ValueError('У записи ведущего должны быть и видео, и звук.')
        if info['duration']>900:raise ValueError('Первая версия поддерживает записи ведущего длительностью до 15 минут.')
        key=self.signature();cached=self.cache/'alignment.json'
        saved=json.loads(cached.read_text(encoding='utf-8')) if cached.exists() else {}
        if saved.get('key')==key:
            self.log('Использую сохраненную разметку речи.')
            source=[Line(**l) for l in saved['lines']];warnings=saved['warnings']
        else:
            self.log('Извлекаю голос ведущего…')
            audio=self.cache/'host.wav';audio_extract(p.host,audio,self.cancel)
            source,warnings=align(audio,p.blocks[self.index].script,self.cache,self.cancel,self.log)
            cached.write_text(json.dumps({'key':key,'lines':[vars(l) for l in source],'warnings':warnings},ensure_ascii=False,indent=2),encoding='utf-8')
        if not source or any(l.end<=l.start for l in source):
            raise ValueError('Некорректная разметка: проверьте, что сценарий соответствует записи.')
        start=max(0,math.floor((source[0].start-.15)*30)/30)
        end=min(math.floor(info['duration']*30)/30,math.ceil((source[-1].end+.15)*30)/30)
        self.log(f'Найден разбор в исходнике: {start:.2f}–{end:.2f} с.')
        silence_log=run(['-ss',start,'-t',end-start,'-i',p.host,'-vn','-af','silencedetect=noise=-35dB:d=0.30','-f','null','-'],self.cancel)
        spans=[(float(a),float(b)) for a,b in re.findall(r'silence_start: ([\d.]+).*?silence_end: ([\d.]+)',silence_log,re.S)]
        keep=keep_ranges(end-start,spans,enabled=p.settings.cut_pauses)
        duration=sum(b-a for a,b in keep)
        lines=[Line(l.text,frame(map_time(l.start-start,keep)),frame(map_time(l.end-start,keep)),l.agreement) for l in source]
        meta={c.path:probe(c.path) for c in block.clips}
        if any(not x['video'] for x in meta.values()):raise ValueError('Игровая вставка должна содержать видео.')
        inserts,cards,extra=placements(block,lines,meta,duration)
        from .orientation import detect_rotation
        rotation=detect_rotation(p.host,self.cache,self.cancel,self.log) if p.settings.auto_rotate else p.settings.rotate
        plan=Plan(start,end,keep,lines,inserts,cards,list(warnings)+extra,duration,rotation)
        self.save_plan(plan)
        self.log(f'Разметка готова: {len(lines)} фраз, {len(inserts)} вставок, {duration:.1f} с.')
        return plan

    def save_plan(self,plan):
        (self.cache/'edit-plan.json').write_text(json.dumps(plan.to_dict(),ensure_ascii=False,indent=2),encoding='utf-8')
        def stamp(t):
            ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
        (self.cache/'timing.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(l.start)} --> {stamp(l.end)}\n{l.text}' for i,l in enumerate(plan.lines))+'\n',encoding='utf-8')

    def render(self,plan,target):
        self.check();self.project.validate(self.index)
        target=Path(target).resolve();p=self.project;s=p.settings
        protected=[p.host,p.music]+[c.path for b in p.blocks for c in b.clips]+[m.path for m in p.matches]+list(p.team_logos.values())
        if any(target==Path(f).resolve() for f in protected if f):raise ValueError('Нельзя записывать результат поверх исходного файла.')
        if target.exists():raise ValueError('Файл результата уже существует. Выберите новое имя.')
        target.parent.mkdir(parents=True,exist_ok=True)
        self.log('Готовлю ведущего: паузы, очистка голоса и цвет…')
        base=self.cache/'host-prepared.mp4';n=len(plan.keep)
        video="select='"+'+'.join(f'between(n,{round(a*30)},{round(b*30)-1})' for a,b in plan.keep)+"',setpts=N/(30*TB)"
        # Normalize VFR sources before frame-index selection.
        video='fps=30,'+video
        from .orientation import detect_rotation
        rotation=(plan.rotation if plan.rotation is not None else detect_rotation(p.host,self.cache,self.cancel,self.log)) if s.auto_rotate else s.rotate
        if rotation==180:video+=',hflip,vflip'
        elif rotation==90:video+=',transpose=clock'
        elif rotation==270:video+=',transpose=cclock'
        video+=',scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1'
        if s.color:video+=',eq=contrast=1.045:saturation=1.035:brightness=-0.004'
        fl=[f'[0:v]{video}[video]','[0:a]asplit='+str(n)+''.join(f'[s{i}]' for i in range(n))]
        for i,(a,b) in enumerate(plan.keep):fl.append(f'[s{i}]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS[a{i}]')
        voice=f'concat=n={n}:v=0:a=1,highpass=f=70'
        if s.denoise:voice+=f',afftdn=nr={s.noise_reduction}:nf=-40:tn=1'
        voice+=',loudnorm=I=-16:TP=-2:LRA=9,aresample=48000'
        fl.append(''.join(f'[a{i}]' for i in range(n))+voice+'[voice]')
        args=['-y','-threads','2','-ss',plan.source_start,'-t',plan.source_end-plan.source_start,'-i',p.host]
        if p.music:
            args+=['-stream_loop','-1','-i',p.music]
            fl.append(f'[1:a]atrim=duration={plan.duration:.6f},asetpts=PTS-STARTPTS,loudnorm=I={s.music_db}:TP=-9:LRA=7,aresample=48000,afade=t=in:d=1,afade=t=out:st={max(0,plan.duration-2)}:d=2[bed]')
            fl.append('[voice]asplit=2[vmain][vside]')
            fl.append('[bed][vside]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=350[duck]')
            fl.append('[vmain][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.85:level=false:latency=true[audio]')
        else:fl.append('[voice]alimiter=limit=0.85:level=false:latency=true[audio]')
        graph=self.cache/'base-filter.txt';graph.write_text(';\n'.join(fl),encoding='utf-8')
        args+=['-filter_complex_threads','2','-filter_complex_script',graph,'-map','[video]','-map','[audio]',
               '-c:v','libx264','-preset','fast','-crf','19','-threads','4','-pix_fmt','yuv420p','-r','30',
               '-c:a','aac','-b:a','160k','-ar','48000','-t',plan.duration,base]
        run(args,self.cancel,self.cache/'base-render.log',lambda t:self.log(f'Подготовка ведущего: {min(100,int(t/plan.duration*100))}%'))
        self.check();self.log('Собираю игровые вставки, наезды до 120% и анимацию…')
        args=['-y','-threads','2','-i',base];fl=[];v='0:v';inputs=1
        windows=zoom_windows(plan.duration,plan.inserts) if s.zoom else []
        if windows:
            parts=[]
            for a,b,c,d in windows:
                a,b,c,d=[round(t*30) for t in (a,b,c,d)]
                parts.append(f'if(between(on,{a},{b}),(1-cos(PI*(on-{a})/{b-a}))/2,if(between(on,{b},{c}),1,if(between(on,{c},{d}),(1+cos(PI*(on-{c})/{d-c}))/2,0)))')
            z='1+'+str(s.zoom_max-1)+'*('+'+'.join(parts)+')'
            fl.append(f"[0:v]scale=2560:1440,zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1280x720:fps=30[zv]");v='zv'
        for i,c in enumerate(plan.inserts):
            meta=probe(c.path);fade=.20 if s.transitions else 0
            pre=min(fade,c.source_in,c.start);post=min(fade,max(0,meta['duration']-(c.source_in+c.end-c.start)),max(0,plan.duration-c.end))
            start=c.start-pre;length=c.end-c.start+pre+post
            args+=['-threads','1','-i',c.path]
            filt=f'trim=start={c.source_in-pre:.6f}:duration={length:.6f},setpts=PTS-STARTPTS,fps=30,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,format=rgba'
            if fade:
                fin=pre or min(fade,length/4);fout=post or min(fade,length/4)
                filt+=f',fade=t=in:st=0:d={fin:.6f}:alpha=1,fade=t=out:st={length-fout:.6f}:d={fout:.6f}:alpha=1'
            fl.append(f'[{inputs}:v]{filt},setpts=PTS+{start:.6f}/TB[clip{i}]');inputs+=1
            nv=f'ins{i}';fl.append(f"[{v}][clip{i}]overlay=0:0:eof_action=pass:enable='gte(t,{start:.6f})*lt(t,{start+length:.6f})'[{nv}]");v=nv
        for i,card in enumerate(plan.cards):
            length=card.end-card.start
            if length<.15:continue
            image=self.cache/f'card-{i}.png';x,y=card_image(card,image,p.team_logos)
            args+=['-loop','1','-framerate','30','-i',image]
            filt=f'trim=duration={length:.6f},setpts=PTS-STARTPTS,format=rgba'
            edge=min(.25,length/3)
            if s.animate_cards:filt+=f',fade=t=in:d={edge:.6f}:alpha=1,fade=t=out:st={length-edge:.6f}:d={edge:.6f}:alpha=1'
            if s.wobble:filt+=f",rotate='0.00349*sin(2*PI*t/4+{i})':ow=iw:oh=ih:c=none"
            fl.append(f'[{inputs}:v]{filt},setpts=PTS+{card.start:.6f}/TB[card{i}]');inputs+=1
            xpos=str(x);ypos=str(y)
            if s.wobble:
                xpos+=f'+3*sin(2*PI*(t-{card.start:.6f})/3.7+{i})'
                ypos+=f'+2*sin(2*PI*(t-{card.start:.6f})/4.3+{i})'
            if s.animate_cards:ypos+=f'+16*pow(max(0,1-(t-{card.start:.6f})/{edge:.6f}),2)+16*pow(max(0,1-({card.end:.6f}-t)/{edge:.6f}),2)'
            nv=f'panel{i}';fl.append(f"[{v}][card{i}]overlay=x='{xpos}':y='{ypos}':eof_action=pass:enable='gte(t,{card.start:.6f})*lt(t,{card.end:.6f})'[{nv}]");v=nv
        fl.append(f'[{v}]scale={s.width}:{s.height},format=yuv420p[final]')
        graph=self.cache/'final-filter.txt';graph.write_text(';\n'.join(fl),encoding='utf-8')
        temp=target.with_name(target.stem+'.partial.mp4')
        if temp.exists():temp.unlink()
        args+=['-filter_complex_threads','2','-filter_complex_script',graph,'-map','[final]','-map','0:a:0','-c:v','libx264','-preset','fast','-crf','19','-threads','4','-c:a','copy','-r','30','-t',plan.duration,'-movflags','+faststart',temp]
        try:
            run(args,self.cancel,self.cache/'final-render.log',lambda t:self.log(f'Экспорт: {min(100,int(t/plan.duration*100))}%'))
            self.check()
            if target.exists():raise ValueError('Файл с выбранным именем появился во время экспорта. Выберите другое имя.')
            # Rename only a successfully closed MP4. Existing exports are never overwritten.
            temp.rename(target)
        finally:
            if temp.exists():temp.unlink()
        self.save_plan(plan)
        shutil.copy2(self.cache/'timing.srt',target.with_suffix('.srt'))
        shutil.copy2(self.cache/'edit-plan.json',target.with_suffix('.timing.json'))
        self.log('Готово: '+str(target))
        return target
