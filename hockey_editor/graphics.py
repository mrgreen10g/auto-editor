from pathlib import Path
import os, math
from PIL import Image,ImageDraw,ImageFont

def font(size,bold=False):
    candidates=[]
    if os.name=='nt':candidates=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/('arialbd.ttf' if bold else 'arial.ttf')]
    candidates += [Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for p in candidates:
        if p.is_file():return ImageFont.truetype(str(p),size)
    # Pillow's embedded font is a last resort, not a silently missing font file.
    return ImageFont.load_default(size=size)

def wrap(draw,text,ft,maxwidth):
    lines=[]
    for paragraph in text.splitlines():
        line=''
        for word in paragraph.split():
            candidate=(line+' '+word).strip()
            if draw.textlength(candidate,font=ft)>maxwidth and line:
                lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
    return lines

def card_image(card,path):
    forecast=card.title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','ОЖИДАЕМЫЙ СЧЁТ')
    width=1160 if forecast else 430
    maxheight=180 if forecast else 310
    dummy=ImageDraw.Draw(Image.new('RGBA',(width,maxheight)))
    size=40 if forecast else 30
    while size>=18:
        ft=font(size,True);lines=wrap(dummy,card.text,ft,width-55)
        if len(lines)*(size+9)+70<=maxheight:break
        size-=1
    if len(lines)*(size+9)+70>maxheight:
        raise ValueError('Слишком длинный текст плашки. Сократите его в окне разметки.')
    height=max(115,65+len(lines)*(size+9))
    margin=12
    im=Image.new('RGBA',(width+margin*2,height+margin*2));d=ImageDraw.Draw(im)
    d.rounded_rectangle((margin+3,margin+5,margin+width+3,margin+height+5),radius=16,fill=(0,0,0,45))
    d.rounded_rectangle((margin,margin,margin+width,margin+height),radius=16,fill=(13,23,40,241))
    d.rounded_rectangle((margin,margin,margin+7,margin+height),radius=3,fill=(80,180,255,255))
    titleft=font(16)
    while d.textlength(card.title,font=titleft)>width-50:titleft=font(titleft.size-1)
    d.text((margin+25,margin+18),card.title,font=titleft,fill=(165,190,212,255))
    for i,line in enumerate(lines):d.text((margin+25,margin+53+i*(size+9)),line,font=ft,fill=(245,249,252,255))
    im.save(path)
    return (50 if forecast else 28, 720-height-50 if forecast else 28)
