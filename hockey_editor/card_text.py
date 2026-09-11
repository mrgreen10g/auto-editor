"""Short, fact-preserving templates. Injuries and manual edits remain verbatim."""
import re
from .event_rules import TEAMS, team_position, clean

NUMBERS = {'одну':'1', 'одной':'1', 'один':'1', 'одна':'1', 'две':'2', 'двух':'2', 'два':'2', 'три':'3', 'трех':'3', 'полтора':'1.5', 'полторы':'1.5', 'двумя':'2', 'двум':'2', 'двух':'2', 'четыре':'4', 'четырех':'4', 'пять':'5', 'пяти':'5', 'шесть':'6', 'шести':'6', 'семь':'7', 'семи':'7', 'восемь':'8', 'восьми':'8', 'девять':'9', 'девяти':'9', 'десять':'10', 'десяти':'10'}


def teams(text):
    positions=[(team_position(name,text),name) for name in TEAMS]
    return [name for _,name in sorted((position,name) for position,name in positions if position is not None)]


def numeric(text):
    for word, number in NUMBERS.items(): text = re.sub(r'\b'+word+r'\b', number, text)
    return text


def summarize_card(title, text, subject=None):
    if title == 'СОСТАВ КОМАНДЫ': return text.strip()
    t = clean(text); numbers = numeric(t); names = teams(text)
    scores = re.findall(r'\b\d{1,2}:\d{1,2}\b', text)
    if title == 'УСЛОВИЯ ПРОГНОЗА':
        if 'возврат' in t:
            m = re.search(r'ровно\s+в\s+(\d+(?:[.,]\d+)?)', numbers)
            if m and any(w in t for w in ('поражени', 'проигр', 'уступ')):
                return f'Поражение ровно в {m[1]} шайбы → возврат'
        if 'ставка выигрывает' in t or 'ставка проходит' in t:
            if ('не проигрывает' in t or 'не проиграет' in t) and re.search(r'уступ\w*\s+в\s+1\s+шайб',numbers):
                return 'Не проиграть или уступить в 1 шайбу → выигрыш'
            if re.search(r'уступ\w*\s+в\s+1\s+шайб',numbers):return 'Поражение в 1 шайбу → выигрыш'
            clauses = []
            m = re.search(r'разниц\w*\s+в\s+(\d+)', numbers)
            if m: clauses.append(f'Разница в {m[1]} шайбу')
            if 'дополнительное время' in t: clauses.append('дополнительное время')
            elif 'овертайм' in t: clauses.append('овертайм')
            if clauses: return ' или '.join(clauses)+' → выигрыш'
    if title == 'СТАТИСТИКА':
        m=re.search(r'проигр\w*\s+(\d+)\s+первых\s+матч',numbers)
        if m:return f'Первые {m[1]} матча: {m[1]} поражения'
        m=re.search(r'(\d+)\s+побед\w*\s+в\s+(\d+)\s+матч',numbers)
        if m:return f'{m[1]} победы / {m[2]} матча'
        m=re.search(r'(\d+)\s+(товарищеских\s+)?матч\w*\s*[—–-]\s*(\d+)\s+побед',numbers)
        if m:return ('Товарищеские:\n' if m[2] else '')+f'{m[1]} матчей · {m[3]} побед'
        m = re.search(r'(\d+)\s+из\s+(\d+)', t)
        if m and any(w in t for w in ('отраз', 'сейв')): return f'Отражено {m[1]} из {m[2]} бросков'
        if scores:
            return (' — '.join(names[:2])+'\n' if names else '')+'Броски: '+scores[0].replace(':',' — ')
    if title == 'РЕЗУЛЬТАТ ВСТРЕЧИ' and scores:
        listed=re.findall(r'«([^»]+)»\s+(\d{1,2}:\d{1,2})',text)
        if len(listed)>1:
            heading='Кубок Минска' if 'кубке минска' in t else 'Результаты'
            rows=[next((n for n in TEAMS if team_position(n,name) is not None),name)+' '+score for name,score in listed]
            return heading+(' · '+subject if subject else '')+'\n'+'\n'.join(rows)
        if subject and names and not any(team_position(n,subject) is not None for n in names):names=[subject]+names
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
    if title in ('СТАТИСТИКА','УСЛОВИЯ ПРОГНОЗА'):return body[0].upper()+body[1:] if body else text.strip()
    if len(body)>120: return ''  # Keep the spoken explanation; don't replace it with a misleading fragment.
    return body[0].upper()+body[1:] if body else text.strip()


def classify_card(text):
    """Facts are independent of whether game footage occupies the same time."""
    t=clean(text);n=numeric(t)
    if any(w in t for w in ('по счету жду','ожидаемый счет')):return 'ОЖИДАЕМЫЙ СЧЁТ'
    if any(w in t for w in ('повреждени','травм','недоступен')):return 'СОСТАВ КОМАНДЫ'
    if 'мой выбор' in t or 'форой плюс' in t:return 'ПРОГНОЗ'
    if any(w in t for w in ('ставка проходит','ставка выигрывает','ставка выиграет','возврат','ставка проигрывает')):return 'УСЛОВИЯ ПРОГНОЗА'
    if re.search(r'\d',n) and any(w in t for w in ('броск','переброс','сейв','отражен','отразил','процент')):return 'СТАТИСТИКА'
    if re.search(r'\b\d{1,2}\s*[:：]\s*\d{1,2}\b',t):return 'РЕЗУЛЬТАТ ВСТРЕЧИ'
    if re.search(r'\b\d+[.,]\d{2}\b',t):return 'КОЭФФИЦИЕНТ ИЗ РАЗБОРА'
    if re.search(r'\b\d+\s+(?:\w+\s+){0,2}(?:побед|поражен|матч|встреч|шайб|гол)',n):
        if not any(w in t for w in ('жду','если','должен','хочется','пусть')):return 'СТАТИСТИКА'
    return ''
