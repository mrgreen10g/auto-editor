"""Readable, context-preserving football information panels."""
import re
from PIL import Image,ImageDraw
from .graphics import font,wrap
from .football_facts import visual

def image(card,path,data=None,accent=None):
 data=data or visual(card.text,card.title) # Rebuild after manual timeline edits.
 items=data['metrics'];body=data['caption'];w=424
 accent=accent or '#51dfc2'
 if re.search(r'проиграл|поражени|кризис',body,re.I) and not re.search(r'не проиграл|без поражени',body,re.I):accent='#ff7687'
 if card.title in ('СОСТАВ КОМАНДЫ','ДИСЦИПЛИНА','ФАКТОР РИСКА'):accent='#ffb360'
 rows=(len(items)+1)//2;top=74+rows*91
 measure=ImageDraw.Draw(Image.new('RGBA',(1,1)))
 for width in (w,760):
  for size in (23,22,21,20,19,18,17):
   lines=wrap(measure,body,font(size,True),width-44)
   h=top+len(lines)*(size+7)+26
   if h<=610:break
  if h<=610:w=width;break
 else:raise ValueError('Слишком длинная информационная плашка. Разделите фразу в разметке.')
 im=Image.new('RGBA',(w,h));d=ImageDraw.Draw(im)
 d.rounded_rectangle((0,0,w-1,h-1),radius=18,fill=(9,20,29,247),outline=(60,91,104,240),width=2)
 d.rounded_rectangle((0,16,5,h-16),radius=2,fill=accent)
 d.line((22,56,w-22,56),fill=accent,width=2)
 # Small geometric indicator, then section label; no subtitles/navigation.
 d.polygon([(22,24),(28,18),(34,24),(28,30)],fill=accent)
 title_size=16
 while measure.textlength(card.title,font=font(title_size,True))>w-68:title_size-=1
 d.text((44,17),card.title,font=font(title_size,True),fill=accent)
 for i,item in enumerate(items):
  cell=(w-54)//2;x=22+(i%2)*(cell+10);y=70+(i//2)*91
  d.rounded_rectangle((x,y,x+cell,y+80),radius=10,fill=(25,43,53,255))
  value_size=48 if len(items)==1 else 34
  while value_size>13 and measure.textlength(item['value'],font=font(value_size,True))>cell-16:value_size-=1
  d.text((x+8,y+6),item['value'],font=font(value_size,True),fill=accent)
  label_size=16
  while label_size>11 and measure.textlength(item['label'],font=font(label_size))>cell-16:label_size-=1
  d.text((x+8,y+57),item['label'],font=font(label_size),fill='#bcd0da')
 if data.get('sport')=='combat' and len(items)==2 and items[0]['label']==items[1]['label']:
  values=[float(v['value'].replace(',','.')) if re.fullmatch(r'\d+(?:[,.]\d+)?',v['value']) else None for v in items]
  if all(v is not None for v in values) and max(values)>0:
   cell=(w-54)//2
   for i,value in enumerate(values):
    x=22+i*(cell+10)
    d.rectangle((x+8,122,x+cell-8,125),fill='#29424c')
    d.rectangle((x+8,122,x+8+(cell-16)*value/max(values),125),fill=accent)
 if len(items)==1 and items[0]['label']=='Владение':
  percent=float(items[0]['value'].rstrip('%').replace(',','.'))
  if 0<=percent<=100:
   box=(w-138,70,w-58,150);d.arc(box,0,360,fill='#29424c',width=9);d.arc(box,-90,-90+360*percent/100,fill=accent,width=9)
 series=re.search(r'(\d+)\s+(?:побед|поражений)\s+подряд',data['source'],re.I)
 if not series:series=re.search(r'(?:проиграл\w*|выиграл\w*)\s+(\d+)\s+матч\w*\s+подряд',data['source'],re.I)
 if len(items)==1 and series and 1<=int(series[1])<=10:
  for n in range(int(series[1])):
   x=244+(n%5)*29;y=82+(n//5)*34
   d.ellipse((x,y,x+22,y+22),fill=accent)
   d.text((x+5,y+2),'П' if 'поражен' in items[0]['label'] else 'В',font=font(13,True),fill='#09141d')
 for i,line in enumerate(lines):
  x=22;y=top+i*(size+7)
  for piece in re.split(r'(\d+(?:[,:.]\d+)?%?)',line):
   f=font(size,bool(re.match(r'\d',piece)));d.text((x,y),piece,font=f,fill=accent if re.match(r'\d',piece) else '#f4f8fa');x+=measure.textlength(piece,font=f)
 im.save(path)
 return (24,76) if w<500 else ((1280-w)//2,720-h-24)
