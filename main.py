import os
# Keep matrix operations economical on a 16 GB Windows workstation.
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(name,'2')
os.environ['ORT_DISABLE_TELEMETRY']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['DO_NOT_TRACK']='1'
import sys,json,tempfile,threading
from pathlib import Path
if getattr(sys,'frozen',False):
    # Console-oriented download libraries also run inside a windowed EXE.
    if sys.stdout is None:sys.stdout=open(os.devnull,'w',encoding='utf-8')
    if sys.stderr is None:sys.stderr=open(os.devnull,'w',encoding='utf-8')

def self_test(report):
    from hockey_editor.mobile_downloads import deno_path
    from yt_dlp import YoutubeDL
    import yt_dlp_ejs,subprocess
    subprocess.run([deno_path(),'--version'],check=True,capture_output=True,timeout=15)
    with YoutubeDL({'quiet':True,'js_runtimes':{'deno':{'path':deno_path()}}}) as downloader:
        assert downloader is not None
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials
    oauth = InstalledAppFlow.from_client_config({'installed': {
        'client_id': 'bundle-check.apps.googleusercontent.com', 'client_secret': 'bundle-check',
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token'}},
        scopes=['https://www.googleapis.com/auth/drive'], autogenerate_code_verifier=True)
    assert oauth.oauth2session is not None
    with AuthorizedSession(Credentials(token='offline-bundle-check')) as session:
        assert session.credentials.token == 'offline-bundle-check'
    from hockey_editor.notifications import tls_context
    import ssl
    context=tls_context()
    assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
    assert context.cert_store_stats()['x509_ca']>0
    from hockey_editor import mini_server
    mini_assets=Path(mini_server.__file__).with_name('mini_web')
    assert all((mini_assets/name).is_file() for name in ('index.html','app.js','app.css','input.js','editor.js'))
    from hockey_editor.media import run,probe
    from hockey_editor.alignment import synthesize,features,subsequence_dtw,normalized
    import numpy as np
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='hockey-check-') as d:
        d=Path(d);voice=d/'voice.wav'
        synthesize(['Проверка сборки. Гол и точный пас.'],voice,threading.Event())
        x=normalized(features(voice),0);mapping,score=subsequence_dtw(x,x)
        assert np.max(abs(mapping-np.arange(len(x))))<1
        video=d/'check.mp4'
        run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=0.4','-f','lavfi','-i','anullsrc=r=48000:cl=mono','-t','0.4','-c:v','libx264','-c:a','aac',video])
        assert probe(video)['video']
        Image.new('RGB',(10,10)).save(d/'image.png')
        synthesize(["O'yinni tahlil qilamiz. Kamida ikkita gol."],d/'uz.wav',threading.Event(),language='uz')
        from faster_whisper import WhisperModel
        from faster_whisper.audio import decode_audio
        decoded=decode_audio(str(voice),sampling_rate=16000)
        assert len(decoded)>1600 and np.isfinite(decoded).all()
        import ctranslate2,tokenizers,av
        assert 'int8' in ctranslate2.get_supported_compute_types('cpu')
    if sys.platform == 'win32':
        from hockey_editor.score_ocr import ScoreReader, score_text
        from hockey_editor.graphics import font
        from PIL import ImageDraw
        image = Image.new('RGB', (240, 75), 'white')
        ImageDraw.Draw(image).text((12, 8), '3 | 2', font=font(40, True), fill='black')
        value, confidence = ScoreReader().text(np.asarray(image)[:, :, ::-1].copy())
        assert score_text(value) == (3, 2), (value, confidence)
        import cv2
        for name in ('haarcascade_frontalface_default.xml','haarcascade_eye_tree_eyeglasses.xml'):
            assert not cv2.CascadeClassifier(str(Path(cv2.data.haarcascades)/name)).empty(), name
    Path(report).write_text(json.dumps({'status':'ok','checks':['google-drive-oauth-runtime','espeak-ru','espeak-uz','audio-alignment','ffmpeg-h264-aac','pillow','whisper-runtime','whisper-audio-decoder','ctranslate2-cpu-int8']+(['bundled-score-ocr'] if sys.platform == 'win32' else [])},indent=2),encoding='utf-8')

if __name__=='__main__':
    try:
        if '--self-test' in sys.argv:self_test(sys.argv[sys.argv.index('--self-test')+1])
        elif '--smoke-gui' in sys.argv:
            import tkinter as tk
            from hockey_editor.gui import App
            root=tk.Tk();root.withdraw();app=App(root);root.update();app.set_busy(True);root.update();app.set_busy(False);root.destroy()
        elif '--render-project' in sys.argv:
            from hockey_editor.model import Project
            from hockey_editor.engine import Engine
            i=sys.argv.index('--render-project');project=Project.load(sys.argv[i+1]);target=Path(sys.argv[i+2])
            from hockey_editor.episode import EpisodeEngine
            engine_class=EpisodeEngine if project.whole_episode else Engine
            engine=engine_class(project,0,target.parent/'.hockey-cache',threading.Event(),print)
            engine.render(engine.analyze(),target)
        else:
            from hockey_editor.gui import launch
            launch()
    except Exception as e:
        if '--self-test' in sys.argv:
            Path(sys.argv[sys.argv.index('--self-test')+1]).write_text(json.dumps({'status':'failed','error':repr(e)}),encoding='utf-8')
        if sys.stdout:print(repr(e))
        if getattr(sys,'frozen',False) and '--self-test' not in sys.argv and '--smoke-gui' not in sys.argv:
            import tkinter.messagebox
            tkinter.messagebox.showerror('Auto Editor',str(e))
        sys.exit(1)



