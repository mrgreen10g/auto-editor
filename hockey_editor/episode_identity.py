"""Human titles and stable episode identities shared by desktop and Telegram."""
import hashlib,json

def title(project):
    pairs=list(dict.fromkeys(b.title.strip() for b in project.blocks if b.title.strip()))
    return ' · '.join(pairs)[:900] or 'Новый выпуск'

def scope(project):
    return hashlib.sha256(json.dumps([project.profile,project.host,[b.uid for b in project.blocks]],ensure_ascii=False).encode()).hexdigest()
