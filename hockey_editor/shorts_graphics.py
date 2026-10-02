"""Portrait artwork in a 720×1280 composition shared by export and preview."""
from pathlib import Path
from PIL import Image,ImageDraw
from .graphics import font,wrap,block_teams,logo_image
from .uzbek import card_label


def card_image(card,path,logos=None):
    logos=logos or {};pair=card.title=='РАЗБОР МАТЧА';pick=card.title=='ПРОГНОЗ'
    width=608;accent='#FFC65B' if pick else '#54E4C0'
    if pair:
        im=Image.new('RGBA',(width,154));d=ImageDraw.Draw(im)
        d.rounded_rectangle((0,0,width-1,153),radius=22,fill='#102D38',outline=accent,width=2)
        d.text((width//2,25),'O‘YIN TAHLILI',anchor='mm',font=font(16,True),fill=accent)
        names=block_teams(card.text)
        for i,name in enumerate(names):
            center=155 if i==0 else width-155
            path_logo=next((p for n,p in logos.items() if n.casefold()==name.casefold()),None)
            if path_logo and Path(path_logo).is_file():im.alpha_composite(logo_image(path_logo,46),(center-23,46))
            size=27
            while size>15 and d.textlength(name,font=font(size,True))>245:size-=1
            d.text((center,117),name,anchor='mm',font=font(size,True),fill='white')
        d.text((width//2,82),'VS',anchor='mm',font=font(23,True),fill=accent)
        im.save(path);return 40,70
    body=card.text;measure=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    size=34 if pick else 30
    while size>18:
        lines=wrap(measure,body,font(size,True),width-80)
        if len(lines)<=4 and len(lines)*(size+7)<=175:break
        size-=1
    lines=wrap(measure,body,font(size,True),width-80)
    if len(lines)*(size+7)>185:raise ValueError('Сократите плашку Shorts до одного факта или одной ставки.')
    owner=getattr(card,'fixture','');header=card_label(card.title)
    height=64+len(lines)*(size+7)+(27 if owner else 0)
    im=Image.new('RGBA',(width,height));d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,width-1,height-1),radius=22,fill='#102D38',outline=accent,width=2)
    d.rounded_rectangle((18,19,24,height-19),radius=3,fill=accent)
    d.text((39,19),header,font=font(16,True),fill=accent)
    y=51
    if owner:
        d.text((39,y),owner,font=font(18,True),fill='#A8CEC9');y+=27
    for line in lines:d.text((39,y),line,font=font(size,True),fill='#FFFFFF');y+=size+7
    im.save(path)
    return 40,min(865,1090-height)


def asset_filter(card):
    """Full-screen channel recording, preserving the entire source and host voice."""
    from .media import probe
    length=card.end-card.start;info=probe(card.asset)
    if info['duration']<=card.source_in:raise ValueError('Начало вставки выходит за видео Telegram.')
    available=info['duration']-card.source_in
    filt='setpts=PTS-STARTPTS,fps=30'
    if available<length:filt+=f',tpad=stop_mode=clone:stop_duration={length-available:.6f}'
    filt+=f',trim=duration={length:.6f},scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x102D38,setsar=1,format=rgba'
    return filt,'0','0'
