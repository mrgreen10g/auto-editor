"""Exact filename/club aliases only; ambiguous files remain unassigned."""
from pathlib import Path
from .team_names import compact,ru_identity,football_identity,RU,_matches,normalize
from .graphics import block_teams


def identity(name,profile):
    if profile=='uz_football':return football_identity(name)
    # Entire filename must identify one club, not a game or a prose mention.
    hits={club for club,patterns in RU.items() for pattern in patterns if any(m.start()==0 and m.end()==len(normalize(name)) for m in _matches(pattern,name))}
    return next(iter(hits)) if len(hits)==1 else None


def assign(project):
    if project.profile=='uz_combat' or not project.logo_folder:return []
    folder=Path(project.logo_folder)
    if not folder.is_dir():return ['Папка логотипов не найдена: '+str(folder)]
    files=[p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp')]
    by_exact={};by_club={}
    for p in files:
        by_exact.setdefault(compact(p.stem),[]).append(str(p))
        club=identity(p.stem,project.profile)
        if club:by_club.setdefault(club,[]).append(str(p))
    warnings=[]
    for name in dict.fromkeys(n for b in project.blocks for n in block_teams(b.title) if n):
        if name in project.team_logos:continue  # empty value is an explicit manual removal
        options=by_exact.get(compact(name),[]) or by_club.get(identity(name,project.profile),[])
        if len(options)==1:project.team_logos[name]=options[0]
        elif len(options)>1:warnings.append('Несколько логотипов для '+name+' — выберите вручную.')
    return warnings
