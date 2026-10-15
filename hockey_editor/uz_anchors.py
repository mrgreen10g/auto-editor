"""Conservative section anchors from spoken body, not introductory team lists."""
import re
from difflib import SequenceMatcher
from .uzbek import spoken_uz


def tokens(text):return re.findall(r"[\w']+",spoken_uz(text))


def script_ranges(blocks,segments,duration):
    from .alignment import split_script
    from .uz_structure import fixture
    words=[w for s in segments for w in s.get('words',[]) if w['end']>w['start']]
    heard=[];times=[]
    for word in words:
        for token in tokens(word['word']):
            heard.append(token);times.append((word['start'],word['end']))
    if not words or not blocks or any(not b.script.strip() for b in blocks):return None
    starts=[0.];floor=0.
    for block in blocks[1:]:
        rows=[r for r in split_script(block.script) if not fixture(r.rstrip('.'),block.sport)]
        expected=tokens(' '.join(rows[:3]))[:32]
        if len(expected)<8:return None
        candidates=[]
        for i,token in enumerate(heard):
            if times[i][0]<max(floor,starts[-1]+.5) or token not in expected[:2]:continue
            best=None
            for length in range(max(8,len(expected)-4),len(expected)+5):
                matcher=SequenceMatcher(None,expected,heard[i:i+length],autojunk=False)
                matches=matcher.get_matching_blocks()
                if sum(m.size for m in matches)<8 or matcher.ratio()<.82 or matches[0].a>1 or matches[0].b>1:continue
                candidate=(matcher.ratio(),times[i][0],times[min(i+length-1,len(times)-1)][1])
                if best is None or candidate[0]>best[0]:best=candidate
            if best:candidates.append(best)
        if not candidates:return None
        best=max(candidates,key=lambda c:c[0])
        if any(abs(c[1]-best[1])>8 and c[0]>=best[0]-.02 for c in candidates):return None
        starts.append(best[1]);floor=best[1]+(best[2]-best[1])*.5
    ends=starts[1:]+[duration]
    if any(z-a<.5 for a,z in zip(starts,ends)):return None
    return list(zip(starts,ends))
