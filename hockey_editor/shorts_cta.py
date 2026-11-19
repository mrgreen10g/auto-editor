"""Speech-timed invitation to the long video, never a fabricated betting pick."""
import re
from .timeline import Card,frame

TITLE='ПОЛНЫЙ РАЗБОР'

def is_invitation(text):
    text=text.lower().replace('ё','е')
    return bool(re.search(r'прогноз\w*',text) and re.search(r'в\s+полн\w*\s+разбор\w*',text))

def is_pointer(text):
    text=text.lower().replace('ё','е')
    return bool(re.search(r'(?:жми|нажми|переходи|смотри)',text) and re.search(r'видео\s+под\s+(?:этим\s+)?роликом',text))

def teaser(project):
    return project.profile.startswith('ru_') and project.profile.endswith('_shorts') and any(is_invitation(b.script) for b in [project.intro,*project.blocks,project.outro])

def cards(lines,duration):
    result=[];used=set()
    for i,line in enumerate(lines):
        if i in used or not is_invitation(line.text):continue
        last=i
        if not is_pointer(line.text) and i+1<len(lines) and lines[i+1].start-line.end<=1.5 and is_pointer(lines[i+1].text):last=i+1
        start=frame(max(0,line.start));end=frame(min(duration,lines[last].end))
        if end-start<.15:continue
        reason='; '.join(dict.fromkeys(l.review_reason for l in lines[i:last+1] if l.review_reason))
        text=' '.join(l.text for l in lines[i:last+1])
        result.append(Card(start,end,TITLE,text,line=i if i==last else -1,review_reason=reason,visual={'kind':'longform_cta'}))
        used.update(range(i,last+1))
    return result

def image(card,path):
    from PIL import Image,ImageDraw
    from .graphics import font
    width,height=608,256;accent='#5ce9c9'
    im=Image.new('RGBA',(width,height));d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,width-1,height-1),radius=24,fill=(8,23,32,250),outline=accent,width=3)
    d.rounded_rectangle((20,16,width-20,45),radius=12,fill='#203d49')
    d.text((width//2,30),'ВСЕ ПРОГНОЗЫ НА МАТЧИ',anchor='mm',font=font(17,True),fill='#b8d3de')
    d.text((width//2,79),'В ПОЛНОМ РАЗБОРЕ',anchor='mm',font=font(35,True),fill='white')
    d.rounded_rectangle((28,111,width-28,157),radius=12,fill=accent)
    d.text((width//2,134),'ЖМИ НА ВИДЕО ПОД РОЛИКОМ',anchor='mm',font=font(24,True),fill='#08202b')
    # Vector arrows: no dependence on Windows symbol fonts.
    for x in (150,304,458):
        d.line((x,176,x,227),fill=accent,width=7)
        d.line((x-17,209,x,227,x+17,209),fill=accent,width=7,joint='curve')
    im.save(path)
    return 40,844
