"""Literal combat evidence; statistics are never inferred from predictions."""
import re
from .football_facts import digits as basic_digits,NUM,PAT
from .timeline import Card
RULES=[
 ('ЗДОРОВЬЕ И ВЕСОГОНКА',r'травм|операци|поврежд|восстанов|весогон|межпозвон|ше[еию]|колен'),
 ('ПОДГОТОВКА',r'подготов|тренир|лагер|зал\b|одноклуб|команд|уведомлен|замен|снял|простой|перерыв|не выступал'),
 ('ГАБАРИТЫ И ВОЗРАСТ',r'рост|размах|сантиметр|килограмм|габарит|моложе|возраст|\bлет\b|\bгода\b|весов'),
 ('УДАРНАЯ СТАТИСТИКА',r'значим\w* удар|удар\w* в минут|удар\w* за минут|точн\w* удар|процент|%'),
 ('БОРЬБА И КОНТРОЛЬ',r'тейкдаун|перевод|борьб|борцов|партер|контрол|клинч|сетк|сабмиш|удуш|болев|кимур'),
 ('РЕКОРД И ФОРМА',r'побед|поражен|проигр|выигр|уступ|непобежд|серии|серия|подряд|рекорд'),
 ('ХОД ПОЕДИНКА',r'раунд|минут|секунд|нокаут|нокдаун|суд[еь]|дистанц|финиш|добив|останов'),
 ('ТАКТИКА БОЯ',r'удар|атак|защит|стойк|ритм|темп|давлен|размен|ногами|руками|лоу-кик|джеб|комбинац|сближ|мощ|сил[уы]|вынослив|работоспособ'),
 ('ТИТУЛ И ОПЫТ',r'чемпион|титул|пояс|опыт|карьер|олимпий|дивизион'),
 ('О БОЕ',r'турнир|ноябр|октябр|сентябр|декабр|январ|феврал|марта|апрел|мая|июн|июл|август')]
def digits(text):
 def number(m):
  values=[NUM[w.lower()] for w in m.group().split()];out=[];total=values[0];last=values[0]
  for n in values[1:]:
   if (last>=100 and n<100) or (last>=20 and n<10):total+=n
   else:out.append(str(total));total=n
   last=n
  return ' '.join(out+[str(total)])
 t=basic_digits(PAT.sub(number,text))
 t=re.sub(r'\b(\d+)\s+цел\w*\s+(\d+)\s+(сотых|десятых)\b',lambda m:m[1]+','+m[2].zfill(2 if m[3]=='сотых' else 1),t,flags=re.I)
 t=re.sub(r'\b(\d+)\s+с\s+половиной\b',lambda m:m[1]+',5',t,flags=re.I)
 t=re.sub(r'\bни\s+(?:1|одного)\s+поражен\w*','0 поражений',t,flags=re.I)
 return t

def classify(text):
 t=text.lower()
 if '?' in t or re.search(r'телеграм|telegram|подпис|комментар|всем привет|с вами был|разбер[её]м|подвед[её]м|мой прогноз|мой основной прогноз|мой выбор|выбираю побед|основной выбор',t):return ''
 if not any(re.search(p,t) for _,p in RULES):return ''
 if re.search(r'\bесли\b|\bможет\b|\bмогут\b|\bожидаю\b|риск|контраргумент|не исключаю|предполагаю|вероятн|допускаю',t):return 'СЦЕНАРИЙ И РИСК'
 return next(label for label,p in RULES if re.search(p,t))
UNIT=r'(?:побед\w*|поражен\w*|раунд\w*|бой|боя|боев|боёв|поедин\w*|лет|года|год|сантиметр\w*|килограмм\w*|минут\w*|секунд\w*|(?:значим\w*\s+|точн\w*\s+)?удар\w*|(?:успешн\w*\s+)?(?:перевод\w*|тейкдаун\w*)|%)'
def visual(text,title,previous=''):
 source=digits(text);items=[]
 if title!='СЦЕНАРИЙ И РИСК':
  for m in re.finditer(r'(?P<q>около\s+|примерно\s+|меньше\s+|больше\s+|до\s+)?(?P<n>\d+(?:[,.]\d+)?)(?:-й|-м|-го)?\s*(?P<u>'+UNIT+r')',source,re.I):
   before=source[max(0,m.start()-30):m.start()].lower();label=m['u'];value=(m['q'] or '')+m['n']
   if re.search(r'ни\s*$|не больше\s*$',before):continue
   if re.search('удар',label,re.I) and re.search(r'за минут|в минут',source[m.end():m.end()+15]):label+=' / мин'
   if label=='%':value+='%';label='Доля'
   items.append({'value':value.strip(),'label':label})
  if re.search(r'килограмм|весогон',source,re.I):
   m=re.search(r'укладываться в\s+(\d+(?:[,.]\d+)?)',source,re.I)
   if m:items.append({'value':m[1],'label':'Вес, кг'})
  for m in re.finditer(r'(рост|размах рук)\s*(?:\w+\s*)?[—:-]\s*(около\s+|примерно\s+)?(\d+(?:[,.]\d+)?)',source,re.I):
   label='Рост, см' if m[1].lower()=='рост' else 'Размах рук, см'
   items=[v for v in items if v['value']!=m[3]]+[{'value':(m[2] or '')+m[3],'label':label}]
  context=source if re.search(r'значим\w* удар',source,re.I) else previous
  if re.search(r'значим\w* удар',context,re.I):
   for m in re.finditer(r'(?:—|против|равенство:)\s*(?:только\s+)?(\d+(?:[,.]\d+)?)(?!\d)',source):
    if not any(v['value']==m[1] for v in items):items.append({'value':m[1],'label':'значимых ударов / мин' if re.search(r'за минут|в минут',context) else 'значимых ударов'})
  for m in re.finditer(r'\b(\d+)\s+минут\w*\s+(?:и\s+)?(\d+)\s+секунд\w*',source,re.I):
   items=[v for v in items if not(v['value'] in (m[1],m[2]) and re.search('минут|секунд',v['label']))]
   items.append({'value':f'{m[1]}:{int(m[2]):02d}','label':'Время контроля' if 'контрол' in (source+previous).lower() else 'Время'})
 return {'source':source,'caption':source,'kind':title,'metrics':items[:6],'sport':'combat'}

def enrich(block,lines,cards):
 result=list(cards)
 for i,line in enumerate(lines):
  title=classify(line.text)
  if not title and i and re.search(r'—\s*(?:только\s+)?\d',digits(line.text)) and re.search(r'значим\w* удар',lines[i-1].text,re.I):title='УДАРНАЯ СТАТИСТИКА'
  if not title or line.end-line.start<.5 or str(i) in block.card_overrides:continue
  if any(c.line==i and (c.asset or c.title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','ТЕЛЕГРАМ','ПОДПИСКА','РАЗБОР МАТЧА','СМЕНА МАТЧА','ИТОГИ ВЫПУСКА')) for c in result):continue
  result=[c for c in result if c.line!=i];data=visual(line.text,title,lines[i-1].text if i else '')
  result.append(Card(line.start,line.end,title,data['source'],line=i,visual=data))
 first=min((c.start for c in result if c.visual),default=float('inf'))
 for c in result:
  if c.title=='РАЗБОР МАТЧА' and c.line<0 and c.start<first<c.end:c.end=first
 return sorted([c for c in result if c.end-c.start>=.15],key=lambda c:c.start)

def image(card,path,shorts=False):
 data=card.visual if card.visual and card.visual.get('source')==card.text else visual(card.text,card.title)
 from . import fact_graphics,football_short_graphics
 return (football_short_graphics if shorts else fact_graphics).image(card,path,data=data,accent='#ffbd69')
