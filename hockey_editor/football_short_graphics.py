"""Informational football cards inside a portrait phone-safe lower area."""
import re
from PIL import Image,ImageDraw
from .graphics import font,wrap
from .football_facts import visual

def image(card,path):
    data=visual(card.text,card.title);body=data['caption'];items=data['metrics']
    width=608;accent='#51dfc2'
    if re.search(r'проиграл|поражени|кризис',body,re.I) and not re.search(r'не проиграл|без поражени',body,re.I):accent='#ff7687'
    if card.title in ('СОСТАВ КОМАНДЫ','ДИСЦИПЛИНА','ФАКТОР РИСКА'):accent='#ffbd69'
    cols=min(3,max(1,len(items)));rows=(len(items)+cols-1)//cols
    top=54+rows*76
    measure=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    for size in (29,28,27,26,25,24,23,22):
        lines=wrap(measure,body,font(size,True),width-44)
        height=top+len(lines)*(size+6)+22
        if height<=400:break
    else:raise ValueError('Разделите длинную информационную фразу Shorts на две плашки.')
    im=Image.new('RGBA',(width,height));d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,width-1,height-1),radius=22,fill=(9,20,29,247),outline=accent,width=2)
    d.rounded_rectangle((8,20,13,height-20),radius=3,fill=accent)
    d.text((25,15),card.title,font=font(18,True),fill=accent)
    cell=(width-44-(cols-1)*10)//cols
    for i,item in enumerate(items):
        x=22+(i%cols)*(cell+10);y=49+(i//cols)*76
        d.rounded_rectangle((x,y,x+cell,y+67),radius=10,fill='#192b35')
        size_value=37
        while size_value>16 and d.textlength(item['value'],font=font(size_value,True))>cell-16:size_value-=1
        d.text((x+8,y+1),item['value'],font=font(size_value,True),fill=accent)
        size_label=17
        while size_label>12 and d.textlength(item['label'],font=font(size_label))>cell-16:size_label-=1
        labels=wrap(d,item['label'],font(size_label),cell-16)
        if len(labels)>1:
            # A long label remains fully present in the caption; tiles remain readable.
            labels=[' '.join(labels)]
            while size_label>9 and d.textlength(labels[0],font=font(size_label))>cell-16:size_label-=1
        d.text((x+8,y+44),labels[0],font=font(size_label),fill='#bdd0db')
    for i,line in enumerate(lines):
        x=22;y=top+i*(size+6)
        for piece in re.split(r'(\d+(?:[,:.]\d+)?%?)',line):
            numeric=bool(re.match(r'\d',piece));ft=font(size,numeric)
            d.text((x,y),piece,font=ft,fill=accent if numeric else '#f4f8fa');x+=d.textlength(piece,font=ft)
    im.save(path)
    return 40,1100-height
