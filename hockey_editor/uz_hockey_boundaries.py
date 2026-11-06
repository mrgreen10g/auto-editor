"""Contextual hockey boundary evidence; never rewrite script or club identities."""
import re
from difflib import SequenceMatcher
from .uzbek import norm
from .hockey_names import ALIASES, mentioned


def contextual_pair(expected, text):
    """Require two distinct nearby names and stronger evidence without a cue."""
    words = re.findall(r'\w+', norm(text))[:18]
    transition = bool(re.match(r'(?:birinchi|ikkinchi|uchinchi|keyingi|oxirgi)\b', norm(text)))
    known = {(i,n): set(mentioned(' '.join(words[i:i+n])))
             for i in range(min(10,len(words))) for n in range(1,min(4,len(words)-i)+1)}
    choices = []
    for club in sorted(expected):
        found = []
        for alias in ALIASES.get(club, ()):
            target = ''.join(re.findall(r'\w+', norm(alias)))
            if len(target) < 4 or club in ('СКА', 'ЦСКА'):
                continue  # Short identities such as SKA/CSKA cannot be fuzzy.
            for i in range(min(10, len(words))):
                for n in range(1, min(4, len(words) - i) + 1):
                    if known[i,n] - {club}:
                        continue  # A correctly heard different team cannot be "corrected".
                    value = ''.join(words[i:i+n])
                    if len(value) < 3 or value[0] != target[0]:
                        continue
                    values = [value] + [value[:-len(s)] for s in ('ning', 'dan', 'ga', 'da', 'ni', 'mi') if value.endswith(s)]
                    score = max(SequenceMatcher(None, target, v, autojunk=False).ratio() for v in values)
                    if score >= .8:
                        found.append((score, i, i+n))
        for i in range(min(10, len(words))):
            for n in range(1, min(4, len(words)-i) + 1):
                if known[i,n] == {club}:
                    found.append((1., i, i+n))
        choices.append(found)
    if len(choices) != 2:
        return False
    return any((a[2] <= b[1] or b[2] <= a[1])
               and max(a[2], b[2])-min(a[1], b[1]) <= 8
               and (a[0]+b[0])/2 >= (.84 if transition else .86)
               and (max(a[0], b[0]) >= .9 or transition)
               for a in choices[0] for b in choices[1])


def ordinal_starts(title, segments, index, floor):
    """Numbered match transition corroborated by its team within 30 seconds."""
    ordinal = {1: 'birinchi', 2: 'ikkinchi', 3: 'uchinchi',
               4: "to.rt(?:inchi)?", 5: 'beshinchi'}.get(index)
    if not ordinal:
        return []
    expected = set(mentioned(title))
    if len(expected) != 2:
        return []
    result = []
    for i, s in enumerate(segments):
        if s['start'] < floor:
            continue
        text=' '.join(norm(s['text']).split())
        if not re.match(r'(?:endi\s+)?' + ordinal + r"\s+(?:o.yin|uchrashuv|bahs)\w*\b", text):
            continue
        nearby = [v['text'] for v in segments[i:] if v['start'] <= s['start']+30]
        if expected & set(mentioned(' '.join(nearby))):
            result.append(s['start'])
    return result


def first_body_after_pause(title, segments, floor):
    """An early new take after the intro, corroborated by a distinctive club.

    Only the first analysis may use this fallback. Short acronyms alone and
    silent gaps alone are insufficient. No script or card text is rewritten.
    """
    if floor<=0:return []
    expected=set(mentioned(title))
    if len(expected)!=2:return []
    result=[]
    for previous,segment in zip(segments,segments[1:]):
        start=segment['start']
        if not floor<=start<=floor+90 or start-previous['end']<8:continue
        words=re.findall(r'\w+',norm(segment['text']))[:8]
        if set(mentioned(' '.join(words)))-expected:continue
        found=False
        for club in expected:
            for alias in ALIASES.get(club,()):
                target=''.join(re.findall(r'\w+',norm(alias)))
                if len(target)<6:continue
                for i in range(len(words)):
                    for n in range(1,min(4,len(words)-i)+1):
                        text=' '.join(words[i:i+n])
                        if set(mentioned(text))-{club}:continue
                        value=''.join(words[i:i+n])
                        variants=[value]+[value[:-len(s)] for s in ('ning','dan','ga','da','ni') if value.endswith(s)]
                        if any(SequenceMatcher(None,target,v,autojunk=False).ratio()>=.9 for v in variants):
                            found=True;break
                    if found:break
                if found:break
            if found:break
        if found:result.append(start)
    return result


def episode_recap(segments, index):
    from .uz_speech import recap_cue
    text = norm(segments[index]['text'])
    # Generic "xullas" and "demak" also introduce individual match arguments.
    if recap_cue(text) and re.search(r'tanlo|tanlu|varia|bugun|tahlil\s+qildik', text):
        return True
    if re.search(r'\b(?:xullas|qull?as)\b', text) and re.search(r'bugun.*(?:tanlo|uchrashuv)', text):
        return True
    if re.search(r'(?:ikki|uch|to.rt|besh)ta\s+uchrashuv.*qildi(?:m|k)', text):
        after = ' '.join(norm(s['text']) for s in segments[index+1:index+3]
                         if s['start'] <= segments[index]['end']+10)
        return bool(re.search(r'yana\s+bir\s+bor', after))
    return False
