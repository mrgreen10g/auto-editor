"""Optional RU Shorts caption layer. Word timings are relative to each Line."""
import math,re
from pathlib import Path
from PIL import Image,ImageDraw
from .graphics import font
from .timeline import map_time


def cut_words(original,line,source_start,keep):
    result=[]
    for word in original.words:
        a=original.start+word['start']-source_start;b=original.start+word['end']-source_start
        spans=[(max(a,x),min(b,y)) for x,y in keep if min(b,y)>max(a,x)]
        if not spans:continue
        start=max(line.start,map_time(spans[0][0],keep));end=min(line.end,map_time(spans[-1][1],keep))
        if end-start>.01:result.append(dict(word=word['word'],start=start-line.start,end=end-line.start))
    return result


def line_words(line):
    """Legacy projects get phrase captions, without pretending to know word times."""
    if line.words:
        result=[]
        for w in line.words:
            a=max(line.start,line.start+w['start']);b=min(line.end,line.start+w['end'])
            if math.isfinite(a) and math.isfinite(b) and b>a and str(w['word']).strip():
                result.append(dict(text=str(w['word']).strip(),start=a,end=b,precise=True))
        return sorted(result,key=lambda w:w['start'])
    words=(line.recognized or line.text).split();total=sum(max(2,len(w)) for w in words);cursor=line.start
    if not total or line.end<=line.start:return []
    result=[]
    for word in words:
        end=cursor+(line.end-line.start)*max(2,len(word))/total
        result.append(dict(text=word,start=cursor,end=end,precise=False));cursor=end
    return result


def groups(plan):
    measure=ImageDraw.Draw(Image.new('RGB',(1,1)));ft=font(44,True)
    for line in plan.lines:
        part=[]
        for word in line_words(line):
            text=' '.join(w['text'] for w in [*part,word])
            if part and (len(part)>=4 or measure.textlength(text,font=ft)>576 or word['start']-part[-1]['end']>.45 or word['end']-part[0]['start']>2.7):
                yield part;part=[]
            part.append(word)
            if re.search(r'[.!?;]$',word['text']):yield part;part=[]
        if part:yield part


def caption_events(plan):
    blocked=[(c.start,c.end) for c in plan.cards if c.asset and c.title=='ТЕЛЕГРАМ']
    events=[];cursor=0
    for group in groups(plan):
        start=max(cursor,group[0]['start']);end=min(plan.duration,group[-1]['end'])
        if end-start<.04:continue
        text=' '.join(w['text'] for w in group);precise=all(w['precise'] for w in group)
        bounds=sorted(set([start,end]+[w['start'] for w in group if start<w['start']<end])) if precise else [start,end]
        for a,b in zip(bounds,bounds[1:]):
            index=max((i for i,w in enumerate(group) if w['start']<=a+.001),default=0) if precise else -1
            pieces=[(a,b)]
            for lo,hi in blocked:
                pieces=[p for x,y in pieces for p in ([(x,y)] if hi<=x or lo>=y else [(x,min(y,lo)),(max(x,hi),y)]) if p[1]-p[0]>=.04]
            for x,y in pieces:events.append(dict(start=x,end=y,words=[w['text'] for w in group],active=index,text=text))
        cursor=end
    return events


def ass_text(text):
    return str(text).replace('\\','＼').replace('{','｛').replace('}','｝').replace('\r',' ').replace('\n',' ')


def ass_time(t):
    ticks=max(0,round(t*100));return f'{ticks//360000}:{ticks//6000%60:02}:{ticks//100%60:02}.{ticks%100:02}'


def filter_path(path):
    return str(Path(path).resolve()).replace('\\','/').replace(':',r'\:').replace("'", "'\\\\\\''")


def write_ass(plan,path):
    events=caption_events(plan)
    if not events:return False
    ft=font(44,True);family=ft.getname()[0].replace(',',' ')
    header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Speech,{family},44,&H00FFFFFF,&H005BC6FF,&H00141920,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,5,60,60,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    measure=ImageDraw.Draw(Image.new('RGB',(1,1)));rows=[]
    for event in events:
        width=measure.textlength(event['text'],font=ft);size=min(44,max(16,int(44*576/max(1,width))))
        tokens=[]
        for i,word in enumerate(event['words']):
            color='&H5BC6FF&' if i==event['active'] else '&HFFFFFF&'
            tokens.append('{\\c'+color+'}'+ass_text(word))
        body='{\\an5\\pos(340,1180)\\fs'+str(size)+'}'+ ' '.join(tokens)
        rows.append(f"Dialogue: 0,{ass_time(event['start'])},{ass_time(event['end'])},Speech,,0,0,0,,{body}")
    Path(path).write_text(header+'\n'.join(rows)+'\n',encoding='utf-8-sig')
    return True
