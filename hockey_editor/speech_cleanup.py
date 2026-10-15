"""Conservative script-backed retakes; never deduplicate distant recap speech."""
import copy
import re
from difflib import SequenceMatcher


def remove_retakes(blocks,segments):
    from .alignment import split_script
    from .ru_speech import tokens
    words=[w for s in segments for w in s.get('words',[])]
    sentences=[tokens(t) for b in blocks if b.language=='ru' for t in split_script(b.script)]
    texts=[]
    for block in blocks:
        if block.language!='ru':continue
        local=[tokens(t) for t in split_script(block.script)]
        for i in range(len(local)):
            # The presenter can restart a whole thought (up to three sentences).
            # Repeated authored sentences, including recap, remain protected.
            if sentences.count(local[i])!=1:continue
            for size in range(1,min(3,len(local)-i)+1):
                target=[t for row in local[i:i+size] for t in row]
                if 6<=len(target)<=100:texts.append(target)
    source=[tokens(w['word']) for w in words]
    cuts=[]
    for target in texts:
        if len(target)<6 or texts.count(target)>1:continue
        prefix=target[:4]
        starts=[]
        for i in range(len(words)-3):
            # A restart is a sentence/segment boundary or follows a real pause.
            boundary=i==0 or re.search(r'[.!?…]$',words[i-1]['word'].strip()) or words[i]['start']-words[i-1]['end']>=.25
            flat=[t for row in source[i:i+4] for t in row]
            hits=sum(a==b for a,b in zip(flat[:4],prefix))
            if (hits==4 or (boundary and hits>=3 and flat[:1]==prefix[:1])):starts.append(i)
        for a,b in zip(starts,starts[1:]):
            if not 1<=words[b]['start']-words[a]['start']<=60:continue
            first=[t for row in source[a:b] for t in row]
            later=[t for row in source[b:b+len(target)+5] for t in row]
            # Require a complete, better matching replacement, not a repeated
            # slogan or the speaker merely continuing the original sentence.
            options=[(SequenceMatcher(None,target,later[:n],autojunk=False).ratio(),n) for n in range(max(4,len(target)-3),min(len(later),len(target)+3)+1)]
            best,n=max(options,default=(0,0))
            critical={'не','нет','без','ноль','один','одна','одно','два','две','три','четыре','пять','шесть','семь','восемь','девять','десять','одинна','двенад','тринад','четырн','пятнад','шестна','семнад','восемн','девятн','двадца','тридца','сорок','пятьде','шестьд','семьде','восемь','девяно','сто','полови'}
            if [t for t in target if t in critical]!=[t for t in later[:n] if t in critical]:continue
            # A high overall match must still include the end of the new take.
            if not n or SequenceMatcher(None,target[-4:],later[max(0,n-4):n],autojunk=False).ratio()<.75:continue
            earlier=SequenceMatcher(None,target,first,autojunk=False).ratio()
            if best<.85 or best+.001<earlier or len(first)>len(target)+8:continue
            correction=bool(re.search(r'\b(?:нет|точнее|заново|оговорился|поправлюсь)\b',' '.join(w['word'].lower().strip(',.!?') for w in words[a:b])))
            if words[b]['start']-words[b-1]['end']<.08 and not correction:continue
            if not correction and best-earlier<.05 and words[b]['start']-words[b-1]['end']<.18:continue
            lo=max(0,words[a]['start']-.06)
            if a:lo=max(lo,words[a-1]['end'])
            hi=max(lo,words[b]['start']-.08)
            if hi-lo>=.3:cuts.append((lo,hi,len(target),best))
    # Overlapping detections can refer to sentence one and sentence two of
    # the SAME restarted thought. Unioning them would erase the successful
    # first sentence. Prefer the complete thought and reject competing cuts.
    selected=[]
    for lo,hi,length,quality in sorted(cuts,key=lambda c:(-c[2],-c[3],c[0])):
        if not any(lo<b and hi>a for a,b in selected):selected.append((lo,hi))
    cuts=merge_ranges(selected)
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
