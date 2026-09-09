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

def requests_for(block, matches):
    sources = [m for m in matches if m.id in block.match_ids]
    if not sources:
        return []
    primary = next((m for m in sources if all(team_position(n, block.title) is not None for n in (m.home, m.away))), sources[0])
    current = primary
    subject = 0
    previous = {}
    finals = {}
    result = []
    lines = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', block.script) if s.strip()]
    missing = False
    for i, phrase in enumerate(lines):
        text = clean(phrase)
        if 'по счету жду' in text or 'мой выбор' in text:
            break
        pairs = [m for m in sources if all(team_position(n, phrase) is not None for n in (m.home, m.away))]
        known = [n for n in TEAMS if team_position(n, phrase) is not None]
        if pairs:
            current = pairs[0]
            missing = False
        elif len(known) >= 2 and any(w in text for w in ('обыграл', 'уступил', 'проиграл', 'выиграл', 'матч')):
            missing = True
        positions = [(team_position(n, phrase), k) for k, n in enumerate((current.home, current.away))]
        positions = sorted((p, k) for p, k in positions if p is not None)
        if positions:
            subject = positions[0][1]
        if any(w in text for w in ('броск', 'форой', 'фора', 'минус полтор', 'плюс полтор', 'коэффициент', 'травм', 'поврежден')):
            continue
        score_match = re.search(r'\b(\d{1,2})\s*[:：]\s*(\d{1,2})\b', phrase)
        score = None
        kind = None
        if score_match and any(w in text for w in ('вела', 'вперед', 'выиграл', 'обыграл', 'уступил', 'проиграл', 'победил', 'счет')):
            a, b = map(int, score_match.groups())
            if max(a, b) > 15:
                continue
            score = [a, b] if subject == 0 else [b, a]
            kind = 'score'
            if 'овертайм' in text:
                finals[current.id] = score
                if any('овертайм' in clean(l) and any(w in clean(l) for w in ('затем', 'решил', 'победный')) for l in lines[i+1:]):
                    continue
        elif 'сравн' in text:
            kind = 'equalizer'
            if current.id in previous:
                n = max(previous[current.id]); score = [n, n]
        elif 'овертайм' in text and any(w in text for w in ('решил', 'затем', 'победн')):
            kind = 'overtime'; score = finals.get(current.id)
        elif any(w in text for w in ('создавала моменты', 'создавал моменты', 'атака действительно', 'играть намного осторожнее', 'хорошая оборон')):
            kind = 'play'
        if not kind:
            continue
        if any(clean(c.phrase) in text for c in block.clips if c.phrase.strip()):
            continue
        if missing:
            result.append(EventRequest('', phrase, kind, score, skipped=True, note='Запись этой встречи не добавлена. Оставлен ведущий.'))
            continue
        note = 'Несколько записей этих команд: проверьте дату встречи.' if len(pairs) > 1 else ''
        result.append(EventRequest(current.id, phrase, kind, score, note=note))
        if score:
            previous[current.id] = score
    return result
