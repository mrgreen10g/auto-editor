"""FFmpeg execution, cancellation and bounded metadata reads."""
from pathlib import Path
import subprocess, threading, re, os, shutil

class Cancelled(Exception): pass

def ffmpeg():
    override = os.environ.get('HOCKEY_FFMPEG')
    if override and Path(override).is_file(): return override
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def run(args, cancel=None, log_path=None, progress=None):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    command = [ffmpeg(), '-hide_banner','-nostdin', *map(str,args)]
    proc = subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                            creationflags=flags,text=True,encoding='utf-8',errors='replace')
    lines=[]
    done=threading.Event()
    def watch():
        if cancel:
            while not done.wait(.15):
                if cancel.is_set():
                    try: proc.terminate()
                    except OSError: pass
                    if not done.wait(3):
                        try: proc.kill()
                        except OSError: pass
                    return
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    try:
        for line in proc.stderr:
            lines.append(line)
            if len(lines)>4000: lines=lines[-2000:]
            if progress:
                match=re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)',line)
                if match: progress(int(match[1])*3600+int(match[2])*60+float(match[3]))
        code=proc.wait()
    finally:
        done.set();proc.stderr.close()
    output=''.join(lines)
    if log_path: Path(log_path).write_text(output,encoding='utf-8')
    if cancel and cancel.is_set(): raise Cancelled('Операция отменена. Исходные файлы сохранены.')
    if code or any(marker in output for marker in ('partial file','Error during demuxing','Invalid data found when processing input')): raise RuntimeError('FFmpeg не завершил обработку:\n'+output[-3500:])
    return output

def probe(path):
    flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    r=subprocess.run([ffmpeg(),'-hide_banner','-i',str(path)],capture_output=True,
                     encoding='utf-8',errors='replace',creationflags=flags,timeout=25)
    text=r.stderr
    duration=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',text)
    video=next((l for l in text.splitlines() if 'Video:' in l),'')
    size=re.search(r'\b(\d{2,5})x(\d{2,5})\b',video)
    if not duration: raise ValueError(f'Не удалось прочитать длительность: {Path(path).name}')
    return {'duration':int(duration[1])*3600+int(duration[2])*60+float(duration[3]),
            'video':bool(video),'audio':'Audio:' in text,
            'width':int(size[1]) if size else 0,'height':int(size[2]) if size else 0}

def audio_extract(path,target,cancel=None):
    run(['-y','-i',path,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',target],cancel)
