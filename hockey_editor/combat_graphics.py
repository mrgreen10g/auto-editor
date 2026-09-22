"""Text-only fight broadcast cards: charcoal, ivory, red and blue accents."""
from PIL import Image,ImageDraw
from .graphics import font,wrap,block_teams


def card_image(card,path):
    transition=card.title in ('СМЕНА МАТЧА','ИТОГИ ВЫПУСКА');pair=card.title=='РАЗБОР МАТЧА';wide=transition or pair or card.title=='ПРОГНОЗ'
    width=1280 if transition else 1040 if pair else 860 if wide else 620
    label={'РАЗБОР МАТЧА':'JANG TAHLILI','СМЕНА МАТЧА':'KEYINGI JANG','ИТОГИ ВЫПУСКА':'YAKUNIY TANLOVLAR','ПРОГНОЗ':'TANLOV','СТАТИСТИКА':'JANGCHI STATISTIKASI','ИНФОРМАЦИЯ':'JANG HAQIDA','УСЛОВИЯ ПРОГНОЗА':'TANLOV SHARTLARI','ТЕЛЕГРАМ':'TELEGRAM','ПОДПИСКА':'OBUNA'}.get(card.title,'MA’LUMOT')
    height=720 if transition else 230 if pair else 320
    im=Image.new('RGBA',(width,height),(17,17,20,250));d=ImageDraw.Draw(im)
    d.polygon([(width-160,0),(width,0),(width,height),(width-260,height)],fill=(37,25,28,255))
    for x in range(width-190,width,22):d.line((x,0,x-120,height),fill=(70,37,40,150),width=2)
    d.rectangle((0,0,9,height),fill='#e63840');top=200 if transition else 26
    d.text((36,top),label,font=font(18,True),fill='#ff5b5e')
    if pair:
        for n,(name,x) in enumerate(zip(block_teams(card.text),(36,580))):
            size=34
            while size>19 and d.textlength(name.upper(),font=font(size,True))>424:size-=1
            d.text((x,108),name.upper(),font=font(size,True),fill='#f5f0e9');d.line((x,172,x+180,172),fill='#e63840' if n==0 else '#668db8',width=3)
        d.text((510,118),'VS',font=font(28,True),anchor='mm',fill='#ff5b5e')
    else:
        size=48 if transition else 36 if wide else 27
        while size>16:
            lines=wrap(d,card.text,font(size,True),width-80)
            if (size+9)*len(lines)<height-top-75:break
            size-=1
        if (size+9)*len(lines)>=height-top-75:raise ValueError('Сократите текст боевой плашки в редакторе.')
        for i,line in enumerate(lines):d.text((36,top+46+i*(size+9)),line,font=font(size,True),fill='#f5f0e9')
        if not transition:im=im.crop((0,0,width,min(height,top+60+len(lines)*(size+9))))
    ImageDraw.Draw(im).line((32,im.height-14,width-32,im.height-14),fill='#e63840',width=3)
    im.save(path)
    return (0,0) if transition else ((1280-im.width)//2,720-im.height-35) if wide else (28,28)
