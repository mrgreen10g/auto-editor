"""Short, fact-preserving templates. Injuries and manual edits remain verbatim."""
import re
from .event_rules import TEAMS, team_position, clean

NUMBERS = {'одну':'1', 'одной':'1', 'один':'1', 'одна':'1', 'две':'2', 'двух':'2', 'два':'2', 'три':'3', 'трех':'3', 'полтора':'1.5', 'полторы':'1.5'}


def teams(text):
    positions=[(team_position(name,text),name) for name in TEAMS]
    return [name for _,name in sorted((position,name) for position,name in positions if position is not None)]


def numeric(text):
    for word, number in NUMBERS.items(): text = re.sub(r'\b'+word+r'\b', number, text)
    return text


def summarize_card(title, text):
    if title == 'СОСТАВ КОМАНДЫ': return text.strip()
    t = clean(text); numbers = numeric(t); names = teams(text)
    scores = re.findall(r'\b\d{1,2}:\d{1,2}\b', text)
    if title == 'УСЛОВИЯ ПРОГНОЗА':
        if 'возврат' in t:
            m = re.search(r'ровно\s+в\s+(\d+(?:[.,]\d+)?)', numbers)
            if m and any(w in t for w in ('поражени', 'проигр', 'уступ')):
                return f'Поражение ровно в {m[1]} шайбы → возврат'
        if 'ставка выигрывает' in t or 'ставка проходит' in t:
            clauses = []
            m = re.search(r'разниц\w*\s+в\s+(\d+)', numbers)
            if m: clauses.append(f'Разница в {m[1]} шайбу')
            if 'дополнительное время' in t: clauses.append('дополнительное время')
            elif 'овертайм' in t: clauses.append('овертайм')
            if clauses: return ' или '.join(clauses)+' → выигрыш'
    if title == 'СТАТИСТИКА':
        m = re.search(r'(\d+)\s+из\s+(\d+)', t)
        if m and any(w in t for w in ('отраз', 'сейв')): return f'Отражено {m[1]} из {m[2]} бросков'
        if scores:
            return (' — '.join(names[:2])+'\n' if names else '')+'Броски: '+scores[0].replace(':',' — ')
    if title == 'РЕЗУЛЬТАТ ВСТРЕЧИ' and scores:
        suffix = ' · ОТ' if 'овертайм' in t else ''
        return (' — '.join(names[:2])+'\n' if names else '')+scores[0]+suffix
    if title == 'ОЖИДАЕМЫЙ СЧЁТ' and scores:
        return ' или '.join(scores)+(' · '+names[-1] if names else '')
    if title == 'ПРОГНОЗ':
        m = re.search(r'фор\w*\s+(плюс|минус)\s+(\d+(?:[.,]\d+)?)', numbers)
        if m: return (names[-1]+'\n' if names else '')+f'Фора ({"+" if m[1] == "плюс" else "−"}{m[2]})'
    if title == 'КОЭФФИЦИЕНТ ИЗ РАЗБОРА':
        coefficient = re.search(r'\b\d[.,]\d{2}\b', t)
        handicap = re.search(r'(плюс|минус)\s+(\d+(?:[.,]\d+)?)', numbers)
        if coefficient:
            return (' · '.join(names[:1])+' ' if names else '')+(f'{"+" if handicap[1] == "плюс" else "−"}{handicap[2]} · ' if handicap else '')+coefficient[0]
    # Remove rhetorical introductions, never cut off a numerical condition or negate it.
    body = re.sub(r'^(?:а если|то есть|поэтому|и это|но при этом)\s+', '', text.strip(), flags=re.I)
    if len(body)>120: return ''  # Keep the spoken explanation; don't replace it with a misleading fragment.
    return body[0].upper()+body[1:] if body else text.strip()
