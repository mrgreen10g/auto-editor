"""Per-profile reusable settings; no scripts, media timelines or event choices."""
from pathlib import Path
from dataclasses import asdict,fields
import json,os
from .model import Settings


def location():
    return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.config')))/'HockeyAutoEditor'/'preferences.json'


def read(path=None):
    try:
        value=json.loads(Path(path or location()).read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def write(data,path=None):
    target=Path(path or location());target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)


def presets(profile,path=None):return read(path).get(profile,{}).get('presets',{})


def save_preset(project,name,path=None):
    if not name.strip():raise ValueError('Введите название шаблона.')
    data=read(path);entry=data.setdefault(project.profile,{})
    entry.setdefault('presets',{})[name.strip()]={'settings':asdict(project.settings),'music':project.music,'logo_folder':project.logo_folder}
    write(data,path)


def apply_preset(project,name,path=None):
    value=presets(project.profile,path).get(name)
    if value is None:raise ValueError('Выберите сохранённый шаблон этого ведущего.')
    settings=Settings(**{k:v for k,v in value['settings'].items() if k in {f.name for f in fields(Settings)}})
    project.settings=settings;project.music=value.get('music','');project.logo_folder=value.get('logo_folder','')
    from .logos import assign
    return assign(project)


def remember_folder(project,path=None):
    data=read(path);data.setdefault(project.profile,{})['logo_folder']=project.logo_folder;write(data,path)


def restore_folder(project,path=None):
    project.logo_folder=read(path).get(project.profile,{}).get('logo_folder','')
