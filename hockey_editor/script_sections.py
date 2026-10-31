"""Optional editorial boundaries and exact imported folder heading hints."""
import re
from .model import Block

MARKER = re.compile(r'(?<!\w)Разбор([1-9][0-9]*)(?!\w)')


def clean(text):
    return MARKER.sub('',text)


def parse(text, profile, pair_hints=()):
    from .uz_structure import fixture, spoken_fixture, key, OUTRO
    from .framing import ru_fixture_heading
    sport='combat' if 'combat' in profile else 'football' if 'football' in profile else 'hockey'
    language='uz' if profile.startswith('uz_') else 'ru'
    lines=text.splitlines()
    def heading(value, explicit=False):
        value=value.strip(' #*[]():').strip()
        matches=[h for h in pair_hints if key(h)==key(value)]
        if len(set(matches))==1:return matches[0]
        if profile.startswith('ru_combat'):
            from .ru_combat import pair_heading
            title=pair_heading(value)
        else:title=(spoken_fixture(value,sport) or fixture(value,sport)) if language=='uz' else ru_fixture_heading(value,sport)
        if title:return title
        if explicit:
            # The marker explicitly declares a fixture, including clubs outside dictionaries.
            return fixture(value,sport)
        return None
    marks=[(i,m) for i,line in enumerate(lines) for m in MARKER.finditer(line)]
    boundaries=[]
    if marks:
        numbers=[m[1] for _,m in marks]
        if len(numbers)!=len(set(numbers)):raise ValueError('Номер РазборN повторяется. Укажите уникальный номер для каждого разбора.')
        for i,m in marks:
            own=heading(clean(lines[i]),True)
            if own:boundaries.append((i,i,own));continue
            neighbors=[next((j for j in range(i-1,-1,-1) if lines[j].strip()),-1), next((j for j in range(i+1,len(lines)) if lines[j].strip()),len(lines))]
            candidates=[(j,heading(lines[j],True)) for j in neighbors if 0<=j<len(lines)]
            candidates=[(j,t) for j,t in candidates if t]
            if len(candidates)!=1:raise ValueError(f'{m[0]}: укажите одну пару рядом с меткой — на той же, предыдущей или следующей строке.')
            j,title=candidates[0];boundaries.append((min(i,j),max(i,j),title))
    elif pair_hints:
        # Only standalone exact folder headings augment normal recognition.
        for i,line in enumerate(lines):
            if any(key(line)==key(h) for h in pair_hints):boundaries.append((i,i,heading(line)))
        if not boundaries:return None
        # Let the original parser preserve its richer behavior when it already works.
        from .folder_import import _parse_episode
        try:
            parsed=_parse_episode(text,profile)
            from .folder_import import pair_key
            found={pair_key(b.title,profile) for b in parsed[1]}
            if all(pair_key(title,profile) in found for _,_,title in boundaries):return parsed
        except ValueError:pass
        # Include ordinary headings too when dictionary coverage is incomplete.
        boundaries=[(i,i,heading(row)) for i,row in enumerate(lines) if heading(row)]
    else:return None
    if '_top5_' in profile:
        # Ranking format retains its own rank validation; markers are editorial only.
        from .folder_import import _parse_episode
        return _parse_episode(clean(text),profile)
    if any(b[0]<=a[1] for a,b in zip(boundaries,boundaries[1:])):raise ValueError('Метки разборов пересекаются: поставьте одну метку у каждой пары.')
    intro=Block(title='Boshlanish' if language=='uz' else 'Начало',uid='intro',kind='intro',language=language,sport=sport)
    outro=Block(title='Yakun' if language=='uz' else 'Итоги',uid='outro',kind='outro',language=language,sport=sport)
    intro.script=clean('\n'.join(lines[:boundaries[0][0]])).strip()
    blocks=[]
    for n,(start,end,title) in enumerate(boundaries):
        stop=boundaries[n+1][0] if n+1<len(boundaries) else len(lines)
        body=lines[end+1:stop]
        if n==len(boundaries)-1:
            split=next((j for j,row in enumerate(body) if key(row) in OUTRO|{'итоги','итог','вывод','заключение'} or re.match(r'^(?:demak\b.*(?:bugun.*tahlil qildik|tanlovlar.*takror|yakunlaymiz)|итак\b|подвед[её]м итоги\b|повторю\s+(?:\w+\s+)?(?:основны\w*\s+)?прогноз)',key(row))),None)
            if split is not None:
                outro.script=clean('\n'.join(body[split:])).strip();body=body[:split]
        # Keep spoken announcements, but omit editorial pair headings and markers.
        announcement=clean(lines[start]).strip(' #*[](): ')
        if profile.startswith('ru_combat'):
            from .ru_combat import CUE
            if re.match(CUE,announcement,re.I):body=[announcement]+body
        elif spoken_fixture(announcement,sport):body=[announcement]+body
        script=clean('\n'.join(body)).strip()
        if not script:raise ValueError('У пары отсутствует текст разбора: '+title)
        block=Block(title=title,script=script,language=language,sport=sport)
        if sport=='combat':
            if language=='ru':from .ru_combat import classify
            else:from .combat_shorts import classify
            picks=[body for row in script.splitlines() for kind,body in [classify(row)] if kind=='ПРОГНОЗ']
            if picks:block.forecast=picks[-1]
        blocks.append(block)
    intro.featured_pairs=[b.title for b in blocks]
    return intro,blocks,outro


def repair_premature_outro(project):
    """Recover the old marker parser's early Demak split only with an explicit ending heading."""
    if not project.profile.startswith('uz_') or not project.blocks:return False
    from .uz_structure import key,OUTRO
    rows=project.outro.script.splitlines()
    if not rows or not re.match(r'^demak\b',key(rows[0])):return False
    boundary=next((i for i,row in enumerate(rows) if i>0 and key(row) in OUTRO),None)
    if boundary is None:return False
    project.blocks[-1].script+='\n'+'\n'.join(rows[:boundary])
    project.outro.script='\n'.join(rows[boundary+1:])
    for block in [project.blocks[-1],project.outro]:block.asr_lines=[];block.speech_key='';block.speech_cards={}
    project.episode_key=''
    return True
