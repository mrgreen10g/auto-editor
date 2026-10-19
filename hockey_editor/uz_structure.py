"""Structure from fixture headings and spoken prose, not mandatory labels.

This module never invents recording timestamps from script time hints.
"""
import re
from .model import Block


def key(text):
    return text.casefold().translate(str.maketrans({c: "'" for c in '’‘ʻʼ`'})).strip(' #*:')


INTRO = {'kirish', 'hook', 'intro', 'boshlanish'}
OUTRO = {'yakun', 'xulosa', 'yakuniy xulosa', 'yakuniy tanlovlar',
         'yakuniy cta', 'yakuniy ekspress'}
TIME = re.compile(r'^(\d{1,2}):(\d{2})\s*[—–-]\s*(\d{1,2}):(\d{2})$')


def narrative_heading(line):
    if len(line)>160 or line.rstrip().endswith(('.', '!', '?')):return False
    return bool(re.match(r"^(?:(?:birinchi|ikkinchi|uchinchi|to'rtinchi|beshinchi|oltinchi|yettinchi|sakkizinchi|to'qqizinchi|o'ninchi|\d+)\s+)?(?:qism|bo'lim)\b", key(line)))


def fixture(line, sport):
    if narrative_heading(line):return None
    line = re.sub(r'^\d+[.)]\s*', '', line).strip(' #*')
    oral=re.match(r"(?:birinchi|ikkinchi|uchinchi|to'rtinchi|beshinchi)\s+(?:uchrashuv|o'yin|jang)\s*[—–:-]?\s+(.+)",key(line),re.I)
    if oral:
        return None  # spoken_fixture strips the lead-in and preserves spoken text.
    line = re.sub(r'^[^\w]+', '', line)
    if len(line) > 120 or line.endswith(('.', ':', '!', '?')):
        return None
    names = re.split(r'\s+[—–-]\s+', line)
    if len(names) != 2 or any(not n or len(n.split()) > 7 for n in names):
        return None
    if re.search(r"\b(?:1x|x2|total|tanlov\w*|mag'lub\w*|bo'l\w*|g'alaba\w*|kam|ko'p)\b", key(line)):
        return None
    if sport == 'hockey':
        from .hockey_names import identity, display
        if all(identity(n) for n in names):
            return ' — '.join(display(identity(n)) for n in names)
    elif sport == 'football':
        from .team_names import football_identity
        if all(football_identity(n) for n in names):
            from .uzbek import display_title
            return display_title(' — '.join(names))
    if not all(re.fullmatch(r"[\w'’‘ʻʼ`./\- \"“”]+", n) and
               (n[0].isupper() or n[0].isdigit()) for n in names):
        return None
    return ' — '.join(names)


def spoken_fixture(line, sport):
    # Editorial ordinal labels sometimes mix Cyrillic and Latin lookalikes.
    parts=line.split(maxsplit=1)
    if len(parts)==2 and re.search('[A-Za-z]',parts[0]):
        line=parts[0].translate(str.maketrans({'К':'K','к':'k','И':'I','С':'C','с':'c','О':'O','о':'o','Т':'T','А':'A','а':'a'}))+' '+parts[1]
    match = re.match(r"(?:birinchi|ikkinchi|uchinchi|to'rtinchi|beshinchi)\s+(?:uchrashuv|o'yin|jang)\s*[—–:-]?\s+(.+)", line, re.I)
    if not match:
        return None
    return fixture(re.sub(r'\s+va\s+', ' — ', match[1].rstrip('.!'), count=1, flags=re.I), sport)


def rows(text):
    text = re.sub(r'\[[^\]]*[А-Яа-яЁё][^\]]*\]', '', text, flags=re.S)
    text = re.sub(r'https?://\S+|www\.\S+|:chatgpt-content-reference\{[^}]*\}|[^]*', '', text)
    return [r.strip().lstrip('\ufeff').strip(' #*') for r in text.splitlines()
            if r.strip() and not re.fullmatch(r'[━─═_—–\-\s]+', r)]


def parse(text, sport):
    values = rows(text)
    def label(row):
        return key(row.split('|')[0])
    first = next((i for i, r in enumerate(values) if label(r) in INTRO), None)
    index = [fixture(r.split('|')[0].strip(), sport) for r in values[:first]] if first is not None else []
    # An initial fixture list is metadata when the body introduces matches orally.
    if first is None and any(spoken_fixture(r, sport) for r in values):
        first = 0
        while first < len(values) and fixture(values[first].split('|')[0].strip(), sport):
            index.append(fixture(values[first].split('|')[0].strip(), sport))
            first += 1
    single = [p for p in index if p]
    # A leading pair is an index, not the start of the analysis, when the
    # script then has an introduction and thematic sections of that same game.
    if first is None and values and fixture(values[0].split('|')[0].strip(), sport) and any(narrative_heading(r) for r in values):
        declared=[];pos=0
        while pos<len(values):
            pair=fixture(values[pos].split('|')[0].strip(), sport)
            if not pair:break
            declared.append(pair);pos+=1
        if len(declared)==1:
            index=declared;single=declared;first=pos
    single = single[0] if len(single) == 1 else None
    body_rows = values[first if first is not None else 0:]
    explicit_pairs = any(fixture(r.split('|')[0].strip(), sport) for r in body_rows)
    intro = Block(title='Boshlanish', uid='intro', kind='intro', language='uz', sport=sport)
    outro = Block(title='Yakun', uid='outro', kind='outro', language='uz', sport=sport)
    blocks = []
    current = intro
    for raw in body_rows:
        line = re.sub(r'\s*\|\s*\d{1,2}:\d{2}\s*[—–-]\s*\d{1,2}:\d{2}\s*$', '', raw).strip()
        k = key(line)
        if narrative_heading(line):
            if single and not blocks and current is intro:
                current=Block(title=single,language='uz',sport=sport)
                blocks.append(current)
            continue  # Editorial section label, not spoken text or a new game.
        if k in INTRO:
            if blocks:
                raise ValueError('Заголовок вступления найден внутри разбора: проверьте сценарий.')
            current = intro
            continue
        if k in OUTRO:
            current = outro
            continue
        hint = TIME.fullmatch(line)
        if hint:
            interval = [int(hint[1])*60+int(hint[2]), int(hint[3])*60+int(hint[4])]
            current.source_hint = [current.source_hint[0], interval[1]] if current.source_hint else interval
            continue
        title = fixture(line, sport)
        spoken=spoken_fixture(line, sport)
        # Prefer names from the initial fixture list to ordinal labels such as
        # 'IKKINCHI UCHRASHUV — TEAM VA TEAM'. These labels are not team names.
        declared=next((p for p in index if p and spoken and key(p)==key(spoken)),None)
        oral_title = declared or (spoken if not explicit_pairs else None)
        if oral_title:
            if current.kind=='analysis' and key(current.title)==key(oral_title):
                if line.isupper():continue
                title=None;oral_title=None  # Keep the actual spoken introduction.
            else:title=oral_title
        if single and not blocks and current is intro and line.isupper() and line.endswith('?'):
            current = Block(title=single, language='uz', sport=sport)
            blocks.append(current)
            continue
        if title and current is not outro:
            # A repeated fixture heading in the same analysis is not a new match.
            if current.kind == 'analysis' and key(current.title) == key(title) and not re.match(r'^\d+[.)]\s', line):
                continue
            current = Block(title=title, language='uz', sport=sport)
            blocks.append(current)
            if oral_title:
                current.script = line
            continue
        if re.search('[А-Яа-яЁё]', line):
            continue  # standalone editorial note; fixture names were handled above
        if not blocks and (re.search(r'\b(?:SSENARIY|SCENARIY|LONG|SHORTS)\b', line, re.I)
                           or line.startswith('```')):
            continue
        if blocks and re.search(r"^(?:demak|xullas|qisqacha|endi)\b.*(?:tanlovlar\w*.*(?:takror|quyidagicha)|takror\w*.*tanlov|yakunlaymiz)", k):
            current = outro
        pick = re.match(r'PROGNOZ\s*:\s*(.+)', line, re.I)
        if sport == 'combat' and pick and current.kind == 'analysis':
            current.forecast = pick[1].strip().rstrip('.')
            continue
        current.script += ('\n' if current.script else '') + line
    if not blocks:
        raise ValueError('Не найдены пары для разбора. Укажите отдельной строкой «Команда — Команда»; KIRISH и YAKUN не обязательны.')
    if any(not b.script.strip() for b in blocks):
        raise ValueError('У пары отсутствует текст разбора: проверьте заголовки сценария.')
    intro.featured_pairs = list(dict.fromkeys([p for p in index if p] + [b.title for b in blocks]))
    return intro, blocks, outro

