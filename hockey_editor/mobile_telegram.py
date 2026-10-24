"""Manual Telegram overlays use the selected episode's permanent materials."""
from pathlib import Path
from .mini_server import RemoteError
from .folder_import import VIDEO
from .material_folder import resolve


def choices(project):
    assets=resolve(project.asset_folder,project.assets);selected=assets.get('telegram','')
    files=[]
    if project.asset_folder and Path(project.asset_folder).is_dir():
        files=[p for p in sorted(Path(project.asset_folder).iterdir()) if p.is_file() and not p.is_symlink() and p.suffix.lower() in VIDEO]
    if selected and Path(selected).is_file():files.insert(0,Path(selected))
    return selected,[dict(path=str(p.resolve()),name=p.name) for p in dict.fromkeys(p.resolve() for p in files)]


def source(project,path=None):
    selected,_=choices(project);value=str(path or selected)
    if not value:raise RemoteError('В выбранных постоянных материалах не найдена Telegram-вставка. Выберите файл на сервере.')
    p=Path(value).resolve()
    from .mini_export import folder
    folder(str(p.parent))
    if not p.is_file() or p.suffix.lower() not in VIDEO:raise RemoteError('Выберите видео Telegram на сервере.')
    return str(p)


def validate(card):
    from .media import probe
    info=probe(card.asset)
    if not info.get('video'):raise RemoteError('В Telegram-вставке не найдено видео.')
    if card.source_in<0 or card.source_in+card.end-card.start>info['duration']+.034:
        raise RemoteError('Telegram-вставка короче выбранного участка. Сократите время или выберите другой файл.')
