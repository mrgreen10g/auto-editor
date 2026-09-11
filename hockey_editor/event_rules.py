"""Conservative script requests: source identity is separate from score order."""
import re
from .model import EventRequest

TEAMS = ('СКА', 'ЦСКА', 'Лада', 'Динамо', 'Северсталь', 'Адмирал', 'Торпедо',
         'Спартак', 'Ак Барс', 'Автомобилист', 'Металлург', 'Сибирь', 'Сочи',
         'Салават Юлаев', 'Локомотив', 'Авангард', 'Трактор', 'Амур', 'Барыс')

def clean(text):
    return text.lower().replace('ё', 'е')

def team_position(name, text):
    key = clean(name).split()[0]
    # Short names must not match a suffix (СКА inside ЦСКА).
    pattern = r'\b' + re.escape(key if len(key) <= 4 else key[:6]) + (r'\b' if len(key) <= 4 else r'\w*')
    match = re.search(pattern, clean(text))
    return match.start() if match else None

def suggested_names(filename):
    found = [(team_position(n, filename), n) for n in TEAMS]
    found = sorted((p, n) for p, n in found if p is not None)
    return [n for _, n in found[:2]]

def topic_for_phrase(topic,phrase,block_title):
    text=clean(phrase)
    if re.match(r'^(?:сначала|затем)\s+\d',text):return topic
    names=[n for n in suggested_names(block_title) if team_position(n,phrase) is not None]
    if names:return min(names,key=lambda n:team_position(n,phrase))
    if 'владивосток' in text:return 'Адмирал'
    if 'тольяттин' in text:return 'Лада'
    return topic

def result_reference(text):
    t=clean(text)
    return bool(re.search(r'\d{1,2}\s*[:：]\s*\d{1,2}',t) and (
        re.match(r'^(?:сначала|затем)\s+\d',t) or
        any(w in t for w in ('проигр','уступ','обыгр','выигр','побед','заверш','закончил'))))

def explicit_reference(text):
    t=clean(text)
    return result_reference(text) or any(w in t for w in ('сыграли','проигр','уступ','обыгр','выигр','побед','поражен','встречалась','предсезон'))

def requests_for(block, matches, use_manual=True):
    sources = [m for m in matches if m.id in block.match_ids]
    if not sources: return []
    primary = next((m for m in sources if all(team_position(n, block.title) is not None for n in (m.home, m.away))), sources[0])
    title_names=suggested_names(block.title)
    topic=title_names[0] if title_names else primary.home
    current = primary; subject = 0; previous = {}; finals = {}; result = []
    lines = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', block.script) if s.strip()]
    requested = [primary.home, primary.away]; active = False; last_generic = -3
    names = list(dict.fromkeys([*TEAMS, *[n for m in sources for n in (m.home, m.away)]]))
    for i, phrase in enumerate(lines):
        text = clean(phrase)
        if 'по счету жду' in text or 'мой выбор' in text: break
        if clean(block.title) == text.rstrip('.'): continue
        if any(w in text for w in ('ставка проходит','ставка выигрывает','возврат')):
            active=False;continue
        if any(w in text for w in ('форой', 'фора', 'минус полтор', 'плюс полтор', 'коэффициент', 'рынок', 'травм', 'поврежден', 'потерял', 'недоступен')):
            active = False; continue
        pairs = [m for m in sources if all(team_position(n, phrase) is not None for n in (m.home, m.away))]
        mentioned = [n for n in names if team_position(n, phrase) is not None]
        # Deduplicate city-qualified and short forms of the same team.
        known = []
        for name in mentioned:
            if not any(team_position(name, old) is not None for old in known): known.append(name)
        known.sort(key=lambda n:team_position(n,phrase))
        historical = result_reference(phrase) or any(w in text for w in ('побед','поражен','сыграли', 'выиграл', 'обыграл', 'уступил', 'проиграл', 'вела', 'вперед', 'сравн', 'забил', 'заброс', 'прошл', 'товарищ', 'предсезон', 'летом', 'встрече', 'встреча', 'встречу'))
        new_topic=topic_for_phrase(topic,phrase,block.title)
        if new_topic!=topic and not any(team_position(new_topic,n) is not None for n in requested):
            options=[m for m in sources if any(team_position(new_topic,n) is not None for n in (m.home,m.away))]
            current=options[0] if len(options)==1 else None;requested=[new_topic];active=True
        topic=new_topic
        if pairs:
            current = pairs[0]; requested = [current.home, current.away]
            active = historical or current.id != primary.id or active
        elif len(known) >= 2 and (historical or 'матч' in text):
            current = None; requested = known[:2]; active = True
        elif len(known) == 1 and not any(team_position(known[0], n) is not None for n in requested):
            options = [m for m in sources if any(team_position(known[0], n) is not None for n in (m.home, m.away))]
            preferred = [m for m in options if any(team_position(n, block.title) is not None for n in (m.home, m.away))]
            if len(preferred or options) == 1:
                current = (preferred or options)[0]; requested = [current.home, current.away]; active = True
            elif historical or 'матч' in text:
                teammate = next((n for n in requested if team_position(n, block.title) is not None), primary.home)
                current = None; requested = [teammate, known[0]]; active = True
        if historical: active = True
        is_result=result_reference(phrase)
        if is_result:
            opponents=[n for n in known if team_position(n,topic) is None]
            if opponents:
                opponent=opponents[0]
                exact_sources=[m for m in sources if all(any(team_position(n,k) is not None for k in (m.home,m.away)) for n in (topic,opponent))]
                current=exact_sources[0] if exact_sources else None
                requested=[topic,opponent];active=True
        if is_result and current is None:subject=0
        source_id = current.id if current else ''
        if current:
            positions = sorted((p, k) for k, n in enumerate((current.home, current.away)) if (p := team_position(n, phrase)) is not None)
            if positions: subject = positions[0][1]
            if is_result:
                subject=0 if team_position(current.home,topic) is not None or team_position(topic,current.home) is not None else 1
        if any(w in text for w in ('броск', 'переброс')): continue
        score_match = re.search(r'\b(\d{1,2})\s*[:：]\s*(\d{1,2})\b', phrase)
        score = None; kind = None
        if score_match and historical:
            a, b = map(int, score_match.groups())
            if max(a, b) > 15: continue
            score = [a, b] if subject == 0 else [b, a]; kind = 'result' if is_result else 'score'
            if 'овертайм' in text:
                finals[source_id] = score
                if any('овертайм' in clean(l) and any(w in clean(l) for w in ('затем', 'решил', 'победный')) for l in lines[i+1:]): continue
        elif 'сравн' in text:
            kind = 'equalizer'
            if source_id in previous:
                n = max(previous[source_id]); score = [n, n]
        elif 'овертайм' in text and any(w in text for w in ('решил', 'затем', 'победн')):
            kind = 'overtime'; score = finals.get(source_id)
        elif active and (pairs or known or i-last_generic >= 2):
            kind = 'play'; last_generic = i
        if not kind: continue
        if use_manual and any(clean(c.phrase) in text for c in block.clips if c.phrase.strip()): continue
        note = 'Несколько записей этих команд: источник можно заменить в выборе эпизода.' if len(pairs) > 1 else ''
        result.append(EventRequest(source_id, phrase, kind, score, note=note, requested_teams=requested.copy(),
                                   flexible_source=kind=='play' and not pairs and not known))
        if score: previous[source_id] = score
    return result
