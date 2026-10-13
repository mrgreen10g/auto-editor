"""Saved per-profile materials, compatible with legacy flat asset kits."""
import json,re
from pathlib import Path
from .processing_cache import write_json

ROLES={'disclaimer':'Дисклеймер','telegram':'Telegram','subscribe':'Подписка'}
PATTERNS={'disclaimer':r'дисклеймер|disclaimer|diskleimer',
          'telegram':r'телеграм|telegram|(?:^|[\s_\-])(?:тг|tg)(?:$|[\s_\-])',
          'subscribe':r'подписк|подпиш|subscribe|subscription|obuna'}

def candidates(folder,previous=None):
    from .folder_import import VIDEO
    root=Path(folder)
    if not root.is_dir():raise ValueError('Папка постоянных материалов не найдена.')
    files=sorted((p for p in root.iterdir() if p.is_file() and p.suffix.lower() in VIDEO and not p.is_symlink()),key=lambda p:p.name.casefold())
    result={}
    for role,pattern in PATTERNS.items():
        old=Path((previous or {}).get(role,'')).name
        exact=[p for p in files if p.name.casefold()==old.casefold()] if old else []
        result[role]=exact or [p for p in files if re.search(pattern,p.stem,re.I)]
    return result

def resolve(folder,assets):
    result=dict(assets)
    if not folder or not Path(folder).is_dir():return result
    choices=candidates(folder,assets)
    for role,files in choices.items():
        if not result.get(role) or not Path(result[role]).is_file():
            if len(files)==1:result[role]=str(files[0].resolve())
    return result

def load_kit(path):
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        folder=data.get('_folder','');assets={k:v for k,v in data.items() if k in ROLES and isinstance(v,str)}
        return folder,{k:v for k,v in resolve(folder,assets).items() if v and Path(v).is_file()}
    except (OSError,ValueError,TypeError,AttributeError):return '',{}

def save_kit(path,folder,assets):
    write_json(path,{**assets,'_folder':folder})
