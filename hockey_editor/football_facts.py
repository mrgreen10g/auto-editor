"""Script-grounded football facts. No generated statistics or guessed owners."""
import re
from .timeline import Card

GROUPS=[
(0,'ноль нуля нулю'),(1,'один одна одно одну одной одного одном'),(2,'два две двух двумя'),(3,'три трех трёх тремя'),(4,'четыре четырех четырёх четырьмя'),(5,'пять пяти пятью'),(6,'шесть шести шестью'),(7,'семь семи семью'),(8,'восемь восьми восемью'),(9,'девять девяти девятью'),(10,'десять десяти десятью'),(11,'одиннадцать одиннадцати'),(12,'двенадцать двенадцати'),(13,'тринадцать тринадцати'),(14,'четырнадцать четырнадцати'),(15,'пятнадцать пятнадцати'),(16,'шестнадцать шестнадцати'),(17,'семнадцать семнадцати'),(18,'восемнадцать восемнадцати'),(19,'девятнадцать девятнадцати'),(20,'двадцать двадцати'),(30,'тридцать тридцати'),(40,'сорок сорока'),(50,'пятьдесят пятидесяти'),(60,'шестьдесят шестидесяти'),(70,'семьдесят семидесяти'),(80,'восемьдесят восьмидесяти'),(90,'девяносто девяноста'),(100,'сто ста')]
NUM={word:value for value,words in GROUPS for word in words.split()}
for value,stem in [(1,'перв'),(2,'втор'),(3,'трет'),(4,'четверт'),(4,'четвёрт'),(5,'пят'),(6,'шест'),(7,'седьм'),(8,'восьм'),(9,'девят'),(10,'десят'),(11,'одиннадцат'),(12,'двенадцат'),(13,'тринадцат'),(14,'четырнадцат'),(15,'пятнадцат'),(16,'шестнадцат'),(17,'семнадцат'),(18,'восемнадцат'),(19,'девятнадцат'),(20,'двадцат'),(30,'тридцат'),(40,'сороков'),(50,'пятидесят'),(60,'шестидесят'),(70,'семидесят'),(80,'восьмидесят'),(90,'девяност')]:
 for ending in ('ый','ой','ая','ое','ые','ого','ому','ом','ую','ым','ых','ий','ья','ьей','ьем','ью'):
  NUM[stem+ending]=value
PAT=re.compile(r'\b(?:'+ '|'.join(sorted(NUM,key=len,reverse=True))+r')(?:\s+(?:'+ '|'.join(sorted(NUM,key=len,reverse=True))+r'))*\b',re.I)

def digits(text):
 def number(m):
  values=[NUM[w.lower()] for w in m.group().split()];result=[];total=values[0];last=values[0]
  for value in values[1:]:
   if last>=20 and value<last and value<10:total+=value
   else:result.append(str(total));total=value
   last=value
  return ' '.join(result+[str(total)])
 text=PAT.sub(number,text)
 text=re.sub(r'\bполутора\b','1,5',text,flags=re.I)
 text=re.sub(r'\bполтора\b','1,5',text,flags=re.I)
 text=re.sub(r'\bдважды\b','2 раза',text,flags=re.I)
 text=re.sub(r'\bтрижды\b','3 раза',text,flags=re.I)
 text=re.sub(r'\bчетырежды\b','4 раза',text,flags=re.I)
 text=re.sub(r'(\d+)\s+процент\w*',r'\1%',text,flags=re.I)
 return text

RULES=[
 ('СОСТАВ КОМАНДЫ',r'травм|замен|ротац|состав|отсутств|останется без|потерял\w* капитана|дебют|не сыгра|кадров|дисквалиф'),
 ('ДИСЦИПЛИНА',r'удален|удалён|красн\w* карточ|ж[её]лт\w* карточ|меньшинств|вдесятером'),
 ('ТУРНИРНАЯ ТАБЛИЦА',r'очк|мест[оеа]|строчк|таблиц|повышен'),
 ('СТАТИСТИКА МАТЧА',r'владел|владени|удар|створ|ожидаем\w* гол|xg|процент|%'),
 ('РЕЗУЛЬТАТ ВСТРЕЧИ',r'\b\d{1,2}:\d{1,2}\b'),
 ('ЭПИЗОД МАТЧА',r'минут|пенальти|углов|автогол|перерыв|тайм|сравня\w* сч[её]т'),
 ('ФОРМА КОМАНДЫ',r'побед|поражен|поражён|проигр|выигр|обыгра|уступ|ничь|вничью|серии|подряд|кризис|побежд'),
 ('АТАКА И ОБОРОНА',r'забил|забивал|забит|пропуст|пропуск|гол|мяч|отлич|атак|оборон|реализ|защит|контратак'),
 ('ТАКТИКА',r'создава\w* момент|созданием момент|создавать момент|пространств|свободн\w* зон|штрафн|компакт|давлен|завершен|завершён|сыгранност|осторожн|закрыться|активност|идти впер[её]д|открытая игра'),
 ('О МАТЧЕ',r'дерби|стадион|команды чемпионата'),
 ('КАЛЕНДАРЬ',r'ноябр|октябр|сентябр|декабр|январ|феврал|марта|апрел|мая|июн|июл|август|календар|между матчами|нагрузк'),
 ('МОТИВАЦИЯ',r'мотивац|необходима|достаточно ничьей|нужна победа|турнирную задачу|бороться')]

def classify(text):
 t=text.lower()
 if '?' in t or re.search(r'телеграм|telegram|подпис|комментар|всем привет|с вами был|пишите|разбер[её]м|теперь переходим|подвед[её]м итоги',t):return ''
 if re.search(r'мой прогноз|мой выбор|выбираю|индивидуальный тотал',t):return '' # Existing authoritative forecast cards.
 if not any(re.search(p,t) for _,p in RULES):return ''
 if re.search(r'\bесли\b|\bможет\b|\bмогут\b|\bожидаю\b|\bриск|контраргумент|нельзя исключать|\bожидается\b|\bпланирует\b',t):return 'ФАКТОР РИСКА'
 return next(label for label,pattern in RULES if re.search(pattern,t))

UNIT=r'(?:ожидаемых\s+гол\w*|удар\w*(?:\s+в\s+створ)?|гол\w*|мяч\w*|очк\w*|побед\w*|поражен\w*|поражён\w*|ничь\w*|матч\w*|встреч\w*|тур\w*|минут\w*|мест\w*|дн\w*)'

def metrics(text,kind):
 if kind in ('ФАКТОР РИСКА','СОСТАВ КОМАНДЫ','МОТИВАЦИЯ','КАЛЕНДАРЬ'):return []
 result=[]
 # Only literal numeric facts. Keep qualifiers and full sentence below the tiles.
 for m in re.finditer(r'(?P<q>около\s+|примерно\s+|всего\s+|только\s+|максимум\s+|больше\s+|меньше\s+|не больше\s+|не меньше\s+)?(?P<n>\d+(?:[,.]\d+)?)(?:-й|-я|-е|-го)?\s*(?P<u>%|'+UNIT+r')',text,re.I):
  if re.search(r'\bни\s*$|\bни\s+разу\s+не\s+\w+\s*$',text[max(0,m.start()-30):m.start()],re.I):continue
  value=(m['q'] or '')+m['n'];label=m['u']
  if label=='%':value+='%';label='Владение' if re.search(r'владел|владени',text,re.I) else 'Процент'
  result.append({'value':value.strip(),'label':label})
 comparison=re.search(r'против\s+(\d+)\s+у\s+соперника',text,re.I)
 if comparison and re.search(r'удар',text[:comparison.start()],re.I):result.append({'value':comparison[1],'label':'ударов у соперника'})
 for m in re.finditer(r'\b\d{1,2}:\d{1,2}\b',text):result.append({'value':m.group(),'label':'Счёт'})
 # Never reinterpret "ни разу не забил больше одного" as zero goals.
 if re.search(r'ни\s+разу\s+не\s+проигр|без\s+(?:единого\s+)?поражен',text,re.I):result.append({'value':'0','label':'поражений'})
 if re.search(r'не\s+одержал\w*\s+ни\s+1\s+побед',text,re.I):result.append({'value':'0','label':'побед'})
 return result[:6]

def visual(text,title):
 source=digits(text)
 items=metrics(source,title)
 series=re.search(r'(?:проиграл\w*|победил\w*|выиграл\w*)\s+(\d+)\s+(?:матч\w*|встреч\w*)\s+подряд',source,re.I)
 if series:
  losing=bool(re.search(r'проиграл',series.group(),re.I));items=[{'value':series[1],'label':'поражений подряд' if losing else 'побед подряд'}]+[v for v in items if not (v['value']==series[1] and re.match(r'матч|встреч',v['label']))]
 caption=source
 # Remove only a verbatim, fully represented metric clause; keep all qualifiers.
 if series and source[series.end():].strip(' .!')=='':
  prefix=source[:series.start()].rstrip(' ,')
  prefix=re.sub(r'\s+и\s+уже$','',prefix,flags=re.I)
  if prefix:caption=prefix.rstrip(' ,')+'.'
 table=re.fullmatch(r'(.+?)\s+занимает\s+\d+\s+место\s+с\s+\d+\s+очк\w*[.!]?',source,re.I)
 possession=re.fullmatch(r'(.+?)\s+владел[аи]?\s+мячом\s+\d+%\s+времени[.!]?',source,re.I)
 if table:caption=table[1]
 if possession:caption=possession[1]
 return {'source':source,'caption':caption,'kind':title,'metrics':items[:6]}

def enrich(block,lines,cards):
 result=list(cards)
 for i,line in enumerate(lines):
  title=classify(line.text)
  if not title or line.end-line.start<.5:continue
  protected=[c for c in result if c.line==i and (c.asset or c.title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','ТЕЛЕГРАМ','ПОДПИСКА','РАЗБОР МАТЧА','СМЕНА МАТЧА','ИТОГИ ВЫПУСКА'))]
  if protected or str(i) in block.card_overrides:continue
  result=[c for c in result if c.line!=i]
  text=digits(line.text)
  result.append(Card(line.start,line.end,title,text,line=i,visual=visual(text,title)))
 # The generic opening card must not cover the first information panel.
 first=min((c.start for c in result if c.visual),default=float('inf'))
 for c in result:
  if c.title=='РАЗБОР МАТЧА' and c.line<0 and c.start<first<c.end:c.end=first
 result=[c for c in result if not(c.title=='РАЗБОР МАТЧА' and c.line<0 and c.start>=first) and c.end-c.start>=.15]
 return sorted(result,key=lambda c:c.start)
