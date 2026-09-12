"""Broadcast-style raster panels; source logos are fitted without inventing detail."""
from pathlib import Path
import os, re
from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size, bold=False):
    candidates=[]
    if os.name=='nt':
        candidates=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/('arialbd.ttf' if bold else 'arial.ttf')]
    candidates += [Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for p in candidates:
        if p.is_file(): return ImageFont.truetype(str(p),size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, ft, maxwidth):
    lines=[]
    for paragraph in text.splitlines():
        line=''
        for word in paragraph.split():
            candidate=(line+' '+word).strip()
            if draw.textlength(candidate,font=ft)>maxwidth and line:
                lines.append(line);line=word
            else: line=candidate
        if line: lines.append(line)
    return lines


def block_teams(title):
    names = re.split(r'\s*[—–]\s*|\s+-\s+|(?<=\w)-(?=\w)', title, maxsplit=1)
    return [n.strip() for n in names] if len(names)==2 else [title.strip(), '']


def panel(width, height, accent=(70,211,215,255)):
    margin=12
    image=Image.new('RGBA',(width+24,height+24))
    d=ImageDraw.Draw(image)
    d.rounded_rectangle((15,18,width+15,height+18),radius=19,fill=(0,0,0,70))
    d.rounded_rectangle((12,12,width+12,height+12),radius=18,fill=(12,27,43,248),outline=(68,94,114,220),width=1)
    # Subtle rink markings, clipped to the panel, with restrained red/blue accents.
    rink=Image.new('RGBA',(width,height)); r=ImageDraw.Draw(rink)
    r.line((width*.78,0,width*.78,height),fill=(62,141,181,38),width=2)
    r.ellipse((width*.78-58,height/2-58,width*.78+58,height/2+58),outline=(89,175,203,35),width=2)
    r.line((width*.94,0,width*.94,height),fill=(229,92,111,38),width=2)
    image.alpha_composite(rink,(12,12))
    d=ImageDraw.Draw(image)
    d.rounded_rectangle((12,12,18,height+12),radius=3,fill=accent)
    return image


def logo_image(path, size=120):
    with Image.open(path) as source:
        im=ImageOps.exif_transpose(source).convert('RGBA')
    bounds=im.getchannel('A').getbbox()
    if bounds: im=im.crop(bounds)
    im.thumbnail((size,size),Image.Resampling.LANCZOS)
    if max(im.size)<size:
        ratio=min(size/im.width,size/im.height)
        im=im.resize((max(1,round(im.width*ratio)),max(1,round(im.height*ratio))),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',(size,size));result.alpha_composite(im,((size-im.width)//2,(size-im.height)//2))
    return result


def match_card(card, path, logos):
    width,height=1080,230
    im=panel(width,height);d=ImageDraw.Draw(im)
    d.text((44,31),'РАЗБОР МАТЧА',font=font(16,True),fill='#69dbd3')
    names=block_teams(card.text)
    for i,name in enumerate(names):
        cx=130 if i==0 else 974
        d.ellipse((cx-62,86,cx+62,210),fill=(244,249,251,255),outline='#65d9d0',width=2)
        logo=next((p for n,p in logos.items() if n.casefold()==name.casefold()),None)
        if logo and Path(logo).is_file():
            im.alpha_composite(logo_image(logo,100),(cx-50,98))
        else:
            initials=''.join(w[0] for w in name.split()[:3]) if len(name)>4 else name
            d.text((cx,145),initials or '•',font=font(30,True),fill='#173246',anchor='mm')
        x=218 if i==0 else 886
        anchor='lm' if i==0 else 'rm'
        size=35
        while size>20 and d.textlength(name,font=font(size,True))>265: size-=1
        d.text((x,147),name,font=font(size,True),fill='#f6fbff',anchor=anchor)
    d.rounded_rectangle((503,113,600,179),radius=13,fill='#254659')
    d.text((551,146),'VS',font=font(29,True),fill='#72e2d4',anchor='mm')
    im=im.resize((round(im.width*.82),round(im.height*.82)),Image.Resampling.LANCZOS)
    im.save(path);return (1280-im.width)//2,720-im.height-46

def forecast_card(card,path):
    width=760;size=44
    dummy=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    while size>24:
        lines=wrap(dummy,card.text,font(size,True),width-110)
        if len(lines)<=3:break
        size-=1
    height=85+len(lines)*(size+9)
    if height>260:raise ValueError('Сократите текст основной ставки до команды, типа и значения.')
    im=panel(width,height,(250,190,77,255));d=ImageDraw.Draw(im)
    d.rounded_rectangle((40,30,228,62),radius=10,fill='#fabe4d')
    d.text((56,36),'МОЙ ВЫБОР',font=font(17,True),fill='#102b40')
    for i,line in enumerate(lines):d.text((48,82+i*(size+9)),line,font=font(size,True),fill='#fff5d9')
    d.line((width-35,35,width-35,height-16),fill='#fabe4d',width=3)
    im.save(path);return (1280-im.width)//2,720-im.height-30

def section_card(card,path):
    im=Image.new('RGBA',(1280,720),'#0c1b2b');d=ImageDraw.Draw(im)
    d.polygon([(920,0),(1140,0),(640,720),(420,720)],fill='#14334a')
    d.polygon([(1160,0),(1200,0),(700,720),(660,720)],fill='#43ccd0')
    d.text((100,220),('ИТОГИ ВЫПУСКА' if card.title=='ИТОГИ ВЫПУСКА' else 'СЛЕДУЮЩИЙ МАТЧ'),font=font(22,True),fill='#69dbd3')
    size=52
    while size>28:
        lines=wrap(d,card.text,font(size,True),1060)
        if len(lines)<=2:break
        size-=1
    for i,line in enumerate(lines):d.text((100,285+i*(size+14)),line,font=font(size,True),fill='#f5faff')
    d.line((100,470,460,470),fill='#fabe4d',width=5)
    im.save(path);return 0,0


def card_image(card, path, logos=None):
    logos=logos or {}
    if card.title=='РАЗБОР МАТЧА': return match_card(card,path,logos)
    if card.title=='ПРОГНОЗ':return forecast_card(card,path)
    if card.title in ('СМЕНА МАТЧА','ИТОГИ ВЫПУСКА'):return section_card(card,path)
    forecast=card.title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','ОЖИДАЕМЫЙ СЧЁТ')
    wide=card.title=='СОСТАВ КОМАНДЫ' and len(card.text)>85
    width=1000 if wide else 430
    maxheight=230 if wide else 320
    size=30 if wide else 28
    body=card.text
    measure=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    if not wide:
        width=max(245,min(430,int(max([measure.textlength(s,font=font(size,True)) for s in body.splitlines()]+[measure.textlength(card.title,font=font(15,True))]))+74))
    dummy=ImageDraw.Draw(Image.new('RGBA',(width,maxheight)))
    while size>=18:
        ft=font(size,True);lines=wrap(dummy,body,ft,width-72)
        if len(lines)*(size+8)+67<=maxheight: break
        size-=1
    if len(lines)*(size+8)+67>maxheight:
        raise ValueError('Плашка слишком длинная. Сократите текст во вкладке «Речь и плашки».')
    height=max(100,65+len(lines)*(size+8))
    accent=(247,182,79,255) if card.title=='ПРОГНОЗ' else (72,211,216,255)
    im=panel(width,height,accent);d=ImageDraw.Draw(im)
    d.text((42,29),card.title,font=font(15,True),fill=accent)
    for i,line in enumerate(lines): d.text((42,65+i*(size+8)),line,font=ft,fill='#f5faff')
    im.save(path)
    return (88,720-height-48) if wide else (28,28)
