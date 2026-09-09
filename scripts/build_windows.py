from pathlib import Path
import subprocess,sys,shutil,importlib.metadata,json,os
root=Path(__file__).resolve().parents[1]
os.chdir(root)
cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed','--onedir','--name','HockeyAutoEditor',
     '--collect-all','espeakng_loader','--collect-all','imageio_ffmpeg','--collect-all','num2words',
     '--collect-submodules','scipy.signal','--hidden-import','scipy.special._special_ufuncs','main.py']
subprocess.run(cmd,check=True)
dest=root/'dist'/'HockeyAutoEditor';licenses=dest/'licenses';licenses.mkdir(exist_ok=True)
for name in ['numpy','scipy','pillow','espeakng-loader','imageio-ffmpeg','num2words','pyinstaller','docopt']:
    dist=importlib.metadata.distribution(name)
    for f in dist.files or []:
        if any(term in str(f).lower() for term in ('license','copying','notice')):
            source=Path(dist.locate_file(f))
            if source.is_file():
                target=licenses/name/str(f);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
shutil.copy2(root/'docs'/'QUICKSTART_RU.md',dest/'START_HERE_RU.txt')
shutil.copy2(root/'THIRD_PARTY.md',dest/'THIRD_PARTY.txt')
# Verify a frozen EXE, not merely its Python source.
report=root/'build'/'bundle-check.json'
subprocess.run([str(dest/'HockeyAutoEditor.exe'),'--self-test',str(report)],check=True,timeout=120)
result=json.loads(report.read_text(encoding='utf-8'))
if result.get('status')!='ok':raise RuntimeError(result)
subprocess.run([str(dest/'HockeyAutoEditor.exe'),'--smoke-gui'],check=True,timeout=45)
shutil.copy2(report,dest/'bundle-check.json')
shutil.make_archive(str(root/'dist'/'HockeyAutoEditor-0.1.0-Windows'),'zip',root/'dist','HockeyAutoEditor')
print('Windows bundle built and checked.')
