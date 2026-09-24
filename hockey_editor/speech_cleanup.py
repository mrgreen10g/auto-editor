"""Conservative script-backed retakes; never deduplicate distant recap speech."""
import copy
import re
from difflib import SequenceMatcher


def remove_retakes(blocks,segments):
    from .alignment import split_script
    from .ru_speech import tokens
    words=[w for s in segments for w in s.get('words',[])]
    texts=[tokens(t) for b in blocks for t in split_script(b.script)]
    source=[tokens(w['word']) for w in words]
    cuts=[]
    for target in texts:
        if len(target)<6 or texts.count(target)>1:continue
        prefix=target[:4]
        starts=[]
        for i in range(len(words)-3):
            # A restart is a sentence/segment boundary or follows a real pause.
            boundary=i==0 or re.search(r'[.!?…]$',words[i-1]['word'].strip()) or words[i]['start']-words[i-1]['end']>=.25
            if not boundary:continue
            flat=[t for row in source[i:i+4] for t in row]
            if flat[:4]==prefix:starts.append(i)
        for a,b in zip(starts,starts[1:]):
            if not 1<=words[b]['start']-words[a]['start']<=25:continue
            first=[t for row in source[a:b] for t in row]
            later=[t for row in source[b:b+len(target)+3] for t in row]
            # Require a complete, better matching replacement, not a repeated
            # slogan or the speaker merely continuing the original sentence.
            best=max((SequenceMatcher(None,target,later[:n],autojunk=False).ratio() for n in range(max(4,len(target)-2),min(len(later),len(target)+2)+1)),default=0)
            earlier=SequenceMatcher(None,target,first,autojunk=False).ratio()
            if best<.85 or best+.001<earlier or len(first)>len(target)+4:continue
            if words[b]['start']-words[b-1]['end']<.18:continue
            lo=max(0,words[a]['start']-.06)
            if a:lo=max(lo,words[a-1]['end'])
            hi=max(lo,words[b]['start']-.08)
            if hi-lo>=.3:cuts.append((lo,hi))
    cuts=merge_ranges(cuts)
    result=[]
    for segment in segments:
        kept=[copy.deepcopy(w) for w in segment.get('words',[]) if not any(a<=w['start']<b for a,b in cuts)]
        if kept:result.append(dict(segment,words=kept,start=kept[0]['start'],end=kept[-1]['end'],text=' '.join(w['word'] for w in kept)))
    return result,cuts


def merge_ranges(ranges):
    result=[]
    for a,b in sorted(ranges):
        if b<=a:continue
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(b,result[-1][1]))
        else:result.append((a,b))
    return result


def subtract_ranges(keep,cuts):
    for lo,hi in merge_ranges(cuts):
        output=[]
        for a,b in keep:
            if hi<=a or lo>=b:output.append((a,b));continue
            if a<lo:output.append((a,lo))
            if hi<b:output.append((hi,b))
        keep=output
    return keep
