"""Server-side downloads from explicit Drive files and individual YouTube videos."""
import hashlib,re,shutil,time
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from . import drive_upload as drive

def canonical(value):
    p=urlsplit(str(value).strip())
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443):raise ValueError('Нужна HTTPS-ссылка Google Диска или YouTube.')
    q=parse_qs(p.query)
    if p.hostname=='drive.google.com':
        m=re.fullmatch(r'/file/d/([A-Za-z0-9_-]{10,200})(?:/view|/preview)?/?',p.path)
        ident=m[1] if m else q.get('id',[''])[0] if p.path in ('/open','/uc') else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}',ident):raise ValueError('Нужна ссылка на отдельный видеофайл Google Диска.')
        return 'drive','https://drive.google.com/file/d/'+ident+'/view'
    if p.hostname in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
        ident=p.path.strip('/') if p.hostname=='youtu.be' else q.get('v',[''])[0] if p.path=='/watch' else p.path.split('/')[-1] if p.path.startswith(('/shorts/','/live/')) else ''
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',ident):raise ValueError('Нужна ссылка на одно видео YouTube, не канал или плейлист.')
        return 'youtube','https://www.youtube.com/watch?v='+ident
    raise ValueError('Поддерживаются ссылки Google Диска и YouTube.')

def download(item,path,update,cancel):
    if item['source']=='drive':return drive_download(item,path,update,cancel)
    return youtube_download(item,path,update,cancel)

def drive_download(item,path,update,cancel):
    ident=canonical(item['url'])[1].split('/')[5];client,_=drive.session()
    try:
        url=drive.API+'/files/'+ident
        r=client.get(url,params={'fields':'id,name,size,md5Checksum,mimeType,modifiedTime,capabilities(canDownload)','supportsAllDrives':'true'},timeout=30);drive.check(r);meta=r.json()
        if not meta.get('mimeType','').startswith('video/') or not meta.get('capabilities',{}).get('canDownload'):raise ValueError('Нет доступа к скачиванию видео. Откройте доступ подключённому Google-аккаунту.')
        size=int(meta.get('size',0))
        if not 0<size<=50*1024**3:raise ValueError('Недопустимый размер видео (максимум 50 ГБ).')
        stamp=[ident,size,meta.get('md5Checksum'),meta.get('modifiedTime')]
        if item.get('remote') and item['remote']!=stamp:raise ValueError('Исходное видео на Диске изменилось. Уберите материал и добавьте ссылку заново.')
        offset=path.stat().st_size if path.exists() else 0
        if offset>size:raise ValueError('Неверный размер частичной загрузки.')
        if shutil.disk_usage(path.parent).free<size-offset+512*1024**2:raise ValueError('На сервере недостаточно места.')
        update(remote=stamp,size=size,received=offset)
        while offset<size:
            if cancel.is_set():raise InterruptedError()
            end=min(offset+8*1024**2,size)-1
            with client.get(url,params={'alt':'media','supportsAllDrives':'true'},headers={'Range':f'bytes={offset}-{end}'},stream=True,timeout=60,allow_redirects=False) as response:
                drive.check(response)
                if response.status_code!=206 or response.headers.get('Content-Range')!=f'bytes {offset}-{end}/{size}':raise ValueError('Google не подтвердил диапазон скачивания. Повторите позже.')
                with path.open('ab') as out:
                    for chunk in response.iter_content(256*1024):
                        if cancel.is_set():raise InterruptedError()
                        if offset+len(chunk)>end+1:raise ValueError('Google вернул неожиданный размер блока.')
                        out.write(chunk);offset+=len(chunk)
                if offset!=end+1:raise ValueError('Передача прервалась. Можно продолжить.')
            update(received=offset,message='Скачиваю с Google Диска')
        if meta.get('md5Checksum'):
            digest=hashlib.md5()
            with path.open('rb') as source:
                for chunk in iter(lambda:source.read(8*1024**2),b''):
                    if cancel.is_set():raise InterruptedError()
                    digest.update(chunk)
            if digest.hexdigest()!=meta['md5Checksum']:raise ValueError('Контрольная сумма не совпала. Уберите материал и загрузите заново.')
    finally:client.close()

def deno_path():
    import sys
    if getattr(sys,'frozen',False):
        binary=Path(sys._MEIPASS)/'deno_bin'/'deno.exe'
        if not binary.is_file():raise ValueError('В сборке отсутствует компонент Deno. Распакуйте полный архив программы.')
        return str(binary)
    import deno
    found=Path(deno.find_deno_bin())
    if found.is_file():return str(found)
    candidates=list(Path(deno.__file__).parent.rglob('deno.exe'))+list(Path(deno.__file__).parent.rglob('deno'))
    binary=next((p for p in candidates if p.is_file()),None)
    if not binary:raise ValueError('В сборке не найден компонент скачивания YouTube (Deno).')
    return str(binary)

def youtube_download(item,path,update,cancel):
    from yt_dlp import YoutubeDL
    import imageio_ffmpeg
    last=[0.]
    def progress(info):
        if cancel.is_set():raise InterruptedError()
        if shutil.disk_usage(path.parent).free<512*1024**2:raise ValueError('На сервере заканчивается место.')
        if time.monotonic()-last[0]>1:
            last[0]=time.monotonic();update(received=info.get('downloaded_bytes',0),size=info.get('total_bytes') or info.get('total_bytes_estimate') or 0,message='Скачиваю запись YouTube')
    class Logger:
        def debug(self,*a):pass
        def warning(self,*a):pass
        def error(self,*a):pass
    def match(info,*,incomplete=False):
        if info.get('is_live') or info.get('live_status')=='is_live':return 'Дождитесь окончания прямого эфира.'
    options=dict(quiet=True,no_warnings=True,logger=Logger(),noplaylist=True,continuedl=True,
                 socket_timeout=30,retries=2,fragment_retries=2,concurrent_fragment_downloads=1,
                 outtmpl=str(path)+'.%(ext)s',format='bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]',
                 merge_output_format='mp4',ffmpeg_location=imageio_ffmpeg.get_ffmpeg_exe(),
                 js_runtimes={'deno':{'path':deno_path()}},remote_components=[],progress_hooks=[progress],match_filter=match,
                 max_filesize=50*1024**3,overwrites=False)
    try:
        with YoutubeDL(options) as ydl:
            info=ydl.extract_info(item['url'],download=True)
            if not info:raise ValueError('Запись недоступна или эфир ещё идёт.')
            final=Path(info.get('filepath') or ydl.prepare_filename(info)).with_suffix('.mp4')
            if not final.is_file():
                candidates=[p for p in path.parent.glob(path.name+'.*') if p.suffix in ('.mp4','.webm','.mkv')]
                if len(candidates)!=1:raise ValueError('Не удалось собрать скачанное видео.')
                final=candidates[0]
            final.replace(path)
            from .folder_import import source_names
            home,away=source_names(info.get('title','')+'.mp4',item.get('profile','ru_hockey'))
            update(home=item.get('home') or home,away=item.get('away') or away)
    except InterruptedError:raise
    except ValueError:raise
    except Exception:
        if cancel.is_set():raise InterruptedError() from None
        raise ValueError('YouTube не отдал запись. Проверьте ссылку и доступность с сервера. Ограничения входа/региона могут мешать скачиванию; можно загрузить файл с устройства.') from None

