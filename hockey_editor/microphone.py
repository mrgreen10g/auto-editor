"""Optional external voice, measured against camera audio across the recording."""
import hashlib,json,subprocess,threading
from pathlib import Path
import numpy as np
from scipy.signal import correlate
from .media import run,probe,Cancelled

REVISION='mic-sync-v1'

def envelope(path,work,cancel):
    target=work/(hashlib.sha256(str(path).encode()).hexdigest()[:16]+'.wav')
    run(['-y','-i',path,'-vn','-ac','1','-ar','8000','-c:a','pcm_s16le',target],cancel)
    from scipy.io import wavfile
    rate,data=wavfile.read(target);data=data.astype(np.float64)/32768
    n=len(data)//80
    env=np.sqrt(np.mean(data[:n*80].reshape(n,80)**2,axis=1))
    env=np.log1p(env*100);env-=np.mean(env)
    return env

def measure(camera,mic):
    """Estimate microphone_time = rate * camera_time + offset using many anchors."""
    size=1200;anchors=[]
    if min(len(camera),len(mic))<size:raise ValueError('Для синхронизации нужно хотя бы 12 секунд общей речи.')
    sums=np.r_[0,np.cumsum(mic)];sq=np.r_[0,np.cumsum(mic*mic)]
    variance=np.maximum(sq[size:]-sq[:-size]-(sums[size:]-sums[:-size])**2/size,1e-12)
    for start in np.linspace(0,len(camera)-size,min(25,max(5,len(camera)//size)),dtype=int):
        sample=camera[start:start+size];sample=sample-sample.mean()
        energy=np.sum(sample*sample)
        if energy<.01:continue
        scores=correlate(mic,sample,mode='valid',method='fft')/np.sqrt(variance*energy)
        best=int(np.argmax(scores));score=float(scores[best])
        if score>=.55:anchors.append((start/100+6,best/100+6,score))
    if len(anchors)<4:raise ValueError('Не удалось уверенно сопоставить микрофон с камерой. Проверьте, что выбрана та же запись.')
    a=np.array(anchors);best=None
    for i in range(len(a)):
        for j in range(i+1,len(a)):
            if a[j,0]-a[i,0]<20:continue
            rate=(a[j,1]-a[i,1])/(a[j,0]-a[i,0]);offset=a[i,1]-rate*a[i,0]
            if not .98<rate<1.02:continue
            keep=np.abs(a[:,1]-(rate*a[:,0]+offset))<.08
            if best is None or keep.sum()>best.sum():best=keep
    if best is None or best.sum()<4:raise ValueError('Записи расходятся: возможны монтажные разрывы или другая запись микрофона.')
    rate,offset=np.polyfit(a[best,0],a[best,1],1)
    residual=np.abs(a[best,1]-(rate*a[best,0]+offset))
    coverage=(a[best,0].max()-a[best,0].min())/(len(camera)/100)
    if coverage<.65 or residual.max()>.06 or best.sum()<len(a)*.75:
        raise ValueError('Не подтверждена синхронизация по всей записи. Проверьте отсутствие вырезанных фрагментов.')
    return dict(rate=float(rate),offset=float(offset),max_error=float(residual.max()),anchors=int(best.sum()),coverage=float(coverage))

def prepare(camera,microphone,cache,cancel,log):
    from .host_media import identity
    key=hashlib.sha256(json.dumps([REVISION,identity(camera),identity(microphone)]).encode()).hexdigest()
    root=Path(cache).parent/'microphone';root.mkdir(parents=True,exist_ok=True)
    target=root/(key+'.mp4');report=root/(key+'.json')
    if target.exists() and report.exists():return str(target)
    work=root/key;work.mkdir(exist_ok=True)
    log('Сопоставляю микрофон и камеру по всей записи: '+Path(camera).name)
    result=measure(envelope(camera,work,cancel),envelope(microphone,work,cancel))
    duration=probe(camera)['duration'];rate=result['rate'];offset=result['offset']
    # Missing microphone lead/tail becomes silence; camera sound is never mixed in.
    trim=max(0,offset);delay=max(0,-offset/rate)
    filters=f'atrim=start={trim:.9f},asetpts=PTS-STARTPTS,atempo={rate:.12f},adelay={round(delay*48000)}S:all=1,apad,atrim=duration={duration:.9f}'
    partial=target.with_suffix('.partial.mp4')
    try:
        run(['-y','-i',camera,'-i',microphone,'-filter_complex',f'[1:a]aresample=48000,{filters}[voice]',
             '-map','0:v:0','-map','[voice]','-c:v','copy','-c:a','aac','-b:a','192k','-t',duration,'-movflags','+faststart',partial],cancel)
        partial.replace(target);report.write_text(json.dumps(result,indent=2))
    finally:partial.unlink(missing_ok=True)
    log(f'Микрофон синхронизирован: {result["anchors"]} точек, расхождение до {result["max_error"]*1000:.0f} мс; звук камеры заменён.')
    return str(target)
