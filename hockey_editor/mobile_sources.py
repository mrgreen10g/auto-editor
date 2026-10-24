"""Merge server sources into a hybrid draft without replacing uploaded material."""
from pathlib import Path
from .model import Block
from .folder_import import discover_matches,folder_pair_hints
from .mini_server import RemoteError


def server_root(d):
    if d.get('server_root'):return Path(d['server_root'])
    # Older server imports stored hints/source but omitted their root.
    if d.get('pair_hints') and d.get('script_source'):
        root=Path(d['folder'])
        return root.parent if d['profile'].endswith('_shorts') and root.name.casefold()=='shorts' else root
    return None


def roots(d):
    values=d.get('server_roots') or ([str(server_root(d))] if server_root(d) else [])
    return list(dict.fromkeys(Path(v).resolve() for v in values))


def update_hints(d):
    selected=roots(d)
    if not selected:return
    hints=[]
    for root in selected:
        if not root.is_dir():raise RemoteError('Папка материалов недоступна на сервере. Выберите её заново.')
        hints.extend(folder_pair_hints(root,d['profile']))
    d['server_roots']=[str(p) for p in selected];d['server_root']=str(selected[0]);d['pair_hints']=list(dict.fromkeys(hints))


def ready(inputs,d,path,role,block='',home='',away='',fighter='',explicit=False):
    p=Path(path).resolve()
    existing=[r for r in d['files'] if r['role']==role and r.get('path') and Path(r['path']).resolve()==p]
    if any(r['status']=='ready' and r['block']==block for r in existing):return False
    # Keep explicit removals removed; a pair disappearing is not a manual removal.
    if not explicit and any(r['status']=='removed' and not r.get('unassigned') and r['block']==block for r in existing):return False
    if not explicit and role=='match' and any(r['status']=='ready' and r['block']!=block for r in existing):
        d.setdefault('import_notes',[]).append('Запись уже назначена другому разбору: '+p.name);return False
    row=inputs.new_file(d,dict(role=role,block=block,name=p.name,home=home,away=away,fighter=fighter))
    row.update(path=str(p),size=p.stat().st_size,received=p.stat().st_size,status='ready',source='local',message='Файл на сервере')
    return True


def reconcile(inputs,d):
    if not roots(d):return 0
    update_hints(d);count=0;folders={}
    for root in roots(d):
        blocks=[Block(title=b['title'],uid=b['uid']) for b in d['blocks']]
        sources,mapping,notes=discover_matches(blocks,d['profile'],root)
        d['import_notes']=list(dict.fromkeys(d.get('import_notes',[])+notes))
        for b in blocks:
            for m in sources:
                if m.id in b.match_ids:count+=ready(inputs,d,m.path,'match',b.uid,m.home,m.away,m.fighter)
        folders.update({blocks[i].uid:path for i,path in mapping.items()})
    d['match_folders']=folders
    return count
