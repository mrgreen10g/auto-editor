"""Opaque fight-broadcast artwork shared by export and live preview."""
from PIL import Image,ImageDraw
from .graphics import font,wrap,block_teams

RED='#dc2535';BLUE='#245be0';INK='#151c2c';PAPER='#fffaf0'

def glove(d,x,y,scale=1,color=RED):
    def box(a,b,c,e):return tuple(round(v) for v in (x+a*scale,y+b*scale,x+c*scale,y+e*scale))
    d.rounded_rectangle(box(9,0,52,47),radius=round(15*scale),fill=color)
    d.rounded_rectangle(box(0,23,22,52),radius=round(9*scale),fill=color)
    d.rounded_rectangle(box(12,44,47,65),radius=round(3*scale),fill=INK)
    for i in (50,56):d.line(box(17,i,42,i),fill=PAPER,width=max(1,round(2*scale)))
    d.arc(box(17,8,44,32),195,280,fill=PAPER,width=max(1,round(2*scale)))

def card_image(card,path):
    transition=card.title in ('СМЕНА МАТЧА','ИТОГИ ВЫПУСКА');pair=card.title=='РАЗБОР МАТЧА';wide=transition or pair or card.title=='ПРОГНОЗ'
    width=1280 if transition else 1080 if pair else 900 if wide else 420
    height=720 if transition else 180 if pair else 320
    label={'РАЗБОР МАТЧА':'FIGHT CARD','СМЕНА МАТЧА':'NEXT FIGHT','ИТОГИ ВЫПУСКА':'FINAL PICKS','ПРОГНОЗ':'TANLOV','СТАТИСТИКА':'FIGHT STATS','ИНФОРМАЦИЯ':'KEY FACT','УСЛОВИЯ ПРОГНОЗА':'TANLOV SHARTLARI','ТЕЛЕГРАМ':'TELEGRAM','ПОДПИСКА':'OBUNA'}.get(card.title,'FIGHT INSIGHT')
    im=Image.new('RGBA',(width,height),PAPER);d=ImageDraw.Draw(im)
    top=195 if transition else 0
    d.rectangle((0,top,width,top+58),fill=INK)
    d.rectangle((0,top,8,top+58),fill=RED)
    d.text((27,top+17),label,font=font(20,True),fill='white')
    glove(d,width-57,top+7,.65,RED)
    if pair:
        from .fighters import clean_name
        a,b=[clean_name(n) for n in block_teams(card.text)]
        for name,x,color in ((a,28,RED),(b,602,BLUE)):
            size=28
            while size>20 and len(wrap(d,name.upper(),font(size,True),440))>2:size-=1
            rows=wrap(d,name.upper(),font(size,True),440)
            for j,row in enumerate(rows):d.text((x,82+j*(size+6)),row,font=font(size,True),fill=INK)
            d.rectangle((x,155,x+440,162),fill=color)
        d.ellipse((498,78,566,146),fill=INK);d.text((532,109),'VS',font=font(26,True),anchor='mm',fill='white')
    else:
        size=48 if transition else 36 if wide else 24
        body=card.text.replace(' · ','\n')
        while size>17:
            rows=[r for paragraph in body.splitlines() for r in wrap(d,paragraph,font(size,True),width-56)]
            if (size+12)*len(rows)<height-top-97:break
            size-=1
        if (size+12)*len(rows)>=height-top-97:raise ValueError('Сократите текст боевой плашки в редакторе.')
        for j,row in enumerate(rows):d.text((28,top+82+j*(size+12)),row,font=font(size,True),fill=INK)
        if not transition:im=im.crop((0,0,width,min(height,106+len(rows)*(size+12))))
    d=ImageDraw.Draw(im)
    d.rectangle((0,im.height-7,width//2,im.height),fill=RED);d.rectangle((width//2,im.height-7,width,im.height),fill=BLUE)
    if transition:
        glove(d,70,50,1.5,RED);glove(d,1100,50,1.5,BLUE)
        d.text((640,105),'FIGHT NIGHT',font=font(36,True),anchor='mm',fill=INK)
    im.save(path)
    return (0,0) if transition else ((1280-im.width)//2,720-im.height-35) if wide else (1280-im.width-28,28)


def portrait_card(card,path):
    """Fight identities without club crests, in the shared Shorts safe area."""
    from .fighters import clean_name
    pair=card.title=='РАЗБОР МАТЧА';width=608
    label={'РАЗБОР МАТЧА':'JANG TAHLILI','ПРОГНОЗ':'TANLOV','СТАТИСТИКА':'STATISTIKA',
           'ИНФОРМАЦИЯ':'MUHIM FAKT','УСЛОВИЯ ПРОГНОЗА':'TANLOV SHARTLARI',
           'ВОПРОС ЗРИТЕЛЮ':'SIZNING FIKRINGIZ'}.get(card.title,'JANG TAHLILI')
    measure=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    if pair:
        names=[clean_name(n) for n in block_teams(card.text)]
        size=27
        while size>16 and any(measure.textlength(n,font=font(size,True))>245 for n in names):size-=1
        height=154;body=[]
    else:
        size=32
        while True:
            body=wrap(measure,card.text,font(size,True),width-56)
            if len(body)*(size+7)<=185:break
            if size<=18:raise ValueError('Сократите боевую плашку Shorts, сохранив условие ставки.')
            size-=1
        height=66+len(body)*(size+7)+(30 if card.fixture else 0)
    im=Image.new('RGBA',(width,height),PAPER);d=ImageDraw.Draw(im)
    d.rectangle((0,0,width,47),fill=INK);d.text((24,13),label,font=font(17,True),fill=PAPER)
    glove(d,width-47,5,.47,RED)
    if pair:
        for name,x in zip(names,(143,465)):d.text((x,97),name,font=font(size,True),anchor='mm',fill=INK)
        d.text((304,97),'VS',font=font(22,True),anchor='mm',fill=RED)
    else:
        y=58
        if card.fixture:
            fs=18
            while fs>11 and d.textlength(card.fixture,font=font(fs,True))>width-48:fs-=1
            d.text((24,y),card.fixture,font=font(fs,True),fill=BLUE);y+=30
        for row in body:d.text((24,y),row,font=font(size,True),fill=INK);y+=size+7
    d.rectangle((0,height-6,width//2,height),fill=RED);d.rectangle((width//2,height-6,width,height),fill=BLUE)
    im.save(path)
    return (40,70) if pair else (40,min(865,1090-height))
