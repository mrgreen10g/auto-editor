"""Transactional episode-folder discovery. Folder ownership is not footage identity."""
import copy,re,os
from pathlib import Path
from .model import Block,MatchSource
from .graphics import block_teams
from .team_names import normalize,compact

VIDEO={'.mov','.mp4','.mkv','.avi','.webm','.m4v'}

def presenter_folder(folder,profile):
    root=Path(folder).resolve()
    if not profile.endswith('_shorts'):return root
    choices=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name.casefold()=='shorts']
    if '_top5_' in profile and not choices:return root
    if len(choices)!=1:raise ValueError('Для Shorts выберите папку лонга с единственной вложенной папкой shorts.')
    return choices[0]

def root_files(folder):
    root=Path(folder).resolve()
    if not root.is_dir():raise ValueError('Папка выпуска не найдена.')
    files=sorted((p for p in root.iterdir() if p.is_file() and not p.is_symlink()),key=lambda p:p.name.casefold())
    return ([p for p in files if p.suffix.lower() in {'.mov','.mp4'}],
            [p for p in files if p.suffix.lower() in {'.txt','.docx'} and not p.name.startswith('~$')])

def parse_episode(text,profile,pair_hints=()):
    from .script_sections import parse
    return parse(text,profile,pair_hints) or _parse_episode(text,profile)

def _parse_episode(text,profile):
    if '_top5_' in profile:
        from .top5 import parse_script
        return parse_script(text,'football' if 'football' in profile else 'hockey')
    if profile=='ru_football_shorts':
        from .shorts import parse_ru_script
        return parse_ru_script(text,sport='football')
    if profile=='uz_combat_shorts':
        from .combat_shorts import parse_script
        return parse_script(text)
    if profile=='ru_football':
        from .ru_football import parse_script as parse
    elif profile=='ru_hockey_shorts':
        from .shorts import parse_ru_script as parse
    elif profile=='uz_hockey_shorts':
        from .uz_hockey_shorts import parse_script as parse
    elif profile=='uz_football_shorts':
        from .shorts import parse_script as parse
    elif profile=='uz_hockey':
        from .uz_hockey import parse_script as parse
    elif profile=='uz_football':
        from .uzbek import parse_script as parse
    elif profile.startswith('uz_combat'):
        from .combat import parse_script as parse
    else:
        from .framing import split_full_script
        intro,blocks,outro=split_full_script(text)
        return Block(title='Начало',uid='intro',kind='intro',script=intro),[Block(title=t,script=s) for t,s in blocks],Block(title='Итоги',uid='outro',kind='outro',script=outro)
    return parse(text)

def identity(name,profile):
    if 'football' in profile:
        from .team_names import football_identity
        return football_identity(name) or compact(name)
    if profile.startswith('uz_combat'):
        from .fighters import identity as canonical
        return canonical(name)
    from .hockey_names import identity as hockey_identity
    return hockey_identity(name) or compact(name)

def pair_key(title,profile):
    if '_top5_' in profile:
        from .top5 import members
        return tuple(sorted(members(title,'football' if 'football' in profile else 'hockey')))
    names=block_teams(title)
    return tuple(sorted(identity(n,profile) for n in names)) if all(names) else ()

def media_files(folder):
    result=[]
    for root,dirs,files in os.walk(folder,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d.casefold()!='shorts' and not d.startswith('.') and not Path(root,d).is_symlink())
        result.extend(Path(root,f).resolve() for f in sorted(files) if Path(f).suffix.lower() in VIDEO and not Path(root,f).is_symlink())
    return result

def source_names(path,profile):
    """Infer only from the recording filename, never the forecast folder."""
    text=Path(path).stem.replace('_',' ')
    if profile.startswith('uz_combat'):return '',''
    if 'football' in profile:
        from .team_names import football_names
        found=football_names(text)
    elif profile.startswith('uz_hockey'):
        from .hockey_names import mentioned,display
        found=[display(v) for v in mentioned(text)]
    else:
        from .team_names import ru_file_names
        found=ru_file_names(text)
    if len(found)==2:return tuple(found)
    # Unlisted football names are allowed in an explicit file pair.
    if 'football' in profile:
        from .shorts import _declared_football_name
        pair=block_teams(text)
        if all(pair) and all(_declared_football_name(n) for n in pair):return tuple(pair)
    return '',''

def build_import(project,folder,host,script,overrides=None):
    from .script_input import read_script
    root=Path(folder).resolve();hosts,scripts=root_files(presenter_folder(root,project.profile))
    host=Path(host).resolve();script=Path(script).resolve()
    if host not in hosts or script not in scripts:raise ValueError('Выберите запись ведущего и сценарий из папки shorts.' if project.profile.endswith('_shorts') else 'Выберите запись ведущего и сценарий из корня выбранной папки.')
    draft=copy.deepcopy(project)
    hints=folder_pair_hints(root,draft.profile)
    draft.intro,draft.blocks,draft.outro=parse_episode(read_script(script),draft.profile,hints)
    draft.host=str(host);draft.hosts=[str(host)];draft.matches=[]
    draft.full_video=True;draft.whole_episode=True;draft.recording_times=''
    draft.episode_plan=None;draft.episode_key='';draft.settings.use_manual_clips=False
    directories=sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and p.name.casefold()!='shorts'),key=lambda p:p.name.casefold())
    notes=[];mapping={};seen={};used=set();overrides=overrides or {}
    for i,block in enumerate(draft.blocks):
        expected=pair_key(block.title,draft.profile)
        choices=[p for p in directories if expected and pair_key(p.name,draft.profile)==expected]
        selected=Path(overrides[i]).resolve() if overrides.get(i) else choices[0] if len(choices)==1 else None
        if selected is None:
            notes.append(block.title+(': несколько подходящих папок — выберите одну.' if choices else ': папка матчей не найдена.'))
            continue
        if not selected.is_dir():raise ValueError('Папка матчей не найдена: '+str(selected))
        if selected in used:raise ValueError('Одна папка назначена нескольким разборам: '+selected.name)
        used.add(selected);mapping[i]=str(selected)
        files=media_files(selected)
        if not files:notes.append(block.title+': в папке нет видео.')
        for path in files:
            if path in seen:
                notes.append('Повтор файла пропущен: '+str(path));continue
            a,b=source_names(path,draft.profile)
            source=MatchSource(str(path),a,b,sport='combat' if draft.profile.startswith('uz_combat') else 'football' if 'football' in draft.profile else 'hockey')
            if source.sport=='combat':
                candidates=[n for n in block_teams(block.title) if identity(n,draft.profile) in (identity(path.stem,draft.profile),identity(path.parent.name,draft.profile))]
                if len(candidates)==1:source.fighter=source.home=candidates[0]
            draft.matches.append(source);block.match_ids.append(source.id);seen[path]=source.id
    for p in directories:
        if p not in used:notes.append('Папка не использована: '+p.name)
    return draft,mapping,notes

def unresolved_sources(project):
    return [m for m in project.matches if (not m.fighter.strip() if m.sport=='combat' else not m.home.strip() or not m.away.strip())]


def folder_pair_hints(root,profile):
    return [p.name for p in sorted(Path(root).iterdir()) if p.is_dir() and not p.is_symlink() and p.name.casefold()!="shorts" and pair_key(p.name,profile)]
