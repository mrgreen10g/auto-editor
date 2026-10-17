"""Small on-demand previews; original files are never served by the gateway."""
import threading,time
from .media import run

def generate(spec,cache,ident):
    # Clean only generated previews, not original media or translation caches.
    for path in cache.iterdir():
        if path.is_file() and path.suffix in ('.mp4','.m4a','.png') and time.time()-path.stat().st_mtime>86400:path.unlink(missing_ok=True)
    mode=spec['mode'];target=cache/(ident+('.png' if mode=='art' else '.m4a' if mode=='voice' else '.mp4'))
    if mode=='translation':
        from .review_translation import translate
        return dict(texts=translate(spec['texts'],cache,threading.Event(),lambda _:None))
    if mode=='art':
        from .graphics import card_image
        card_image(spec['card'],target,logos=spec['logos'],profile=spec['profile'])
    elif mode=='clip':
        run(['-y','-ss',spec['start'],'-i',spec['path'],'-t',spec['end']-spec['start'],'-map','0:v:0','-map','0:a:0?','-vf','scale=640:640:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1','-r','24','-c:v','libx264','-preset','veryfast','-crf','28','-pix_fmt','yuv420p','-c:a','aac','-b:a','80k','-movflags','+faststart',target])
    elif mode=='voice':
        args=['-y'];filters=[]
        for i,span in enumerate(spec['spans']):
            args+=['-ss',span['start'],'-t',span['end']-span['start'],'-i',span['path']]
            filters.append(f'[{i}:a]aresample=16000,aformat=sample_fmts=fltp:channel_layouts=mono,asetpts=PTS-STARTPTS[a{i}]')
        filters.append(''.join(f'[a{i}]' for i in range(len(spec['spans'])))+f'concat=n={len(spec["spans"])}:v=0:a=1[out]')
        run(args+['-filter_complex',';'.join(filters),'-map','[out]','-c:a','aac','-b:a','64k',target])
    return dict(file=str(target))
