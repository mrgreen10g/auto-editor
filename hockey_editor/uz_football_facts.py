"""Uzbek football information, grounded in each timed sentence, never invented."""
import re
from .uzbek import norm,number
from .timeline import Card

ONES={norm(number(n)):n for n in range(10)}
TENS={norm(number(n)):n for n in range(10,100,10)}
WORDS={**ONES,**TENS,'yuz':100,'ming':1000}
TOKEN='|'.join(re.escape(w) for w in sorted(WORDS,key=len,reverse=True))
NUM=re.compile(r"(?<![\w'])((?:"+TOKEN+r")(?:\s+(?:"+TOKEN+r"))*)(ta(?:si|dan)?|tadan|dan|ni|ga|ning)?(?![\w'])",re.I)

def digits(text):
 text=text.translate(str.maketrans({c:"'" for c in '’‘ʻʼ`'}))
 # Scores are spoken as ikkiyu bir / to'rtu nol, not as a decimal.
 score=r'\b('+ '|'.join(re.escape(w) for w in ONES)+r')(?:yu|u)\s+('+ '|'.join(re.escape(w) for w in ONES)+r')\b'
 text=re.sub(score,lambda m:f'{ONES[m[1].lower()]}:{ONES[m[2].lower()]}',text,flags=re.I)
 text=re.sub(r'\bbitta\b','1 ta',text,flags=re.I)
 def convert(m):
  total=part=0
  for w in m[1].lower().split():
   n=WORDS[w]
   if n==100:part=max(1,part)*100
   elif n==1000:total+=max(1,part)*1000;part=0
   else:part+=n
  suffix=m[2] or ''
  return str(total+part)+(' '+suffix if suffix.startswith('ta') else suffix)
 return NUM.sub(convert,text)

RULES=[
 ('JAROHAT VA TARKIB',r'jarohat|safdan chiq|diskvalifik|ro.yxat.*kiritilma|ishtirok etmay|maydonga tushmay'),
 ('TARKIB VA ALMASHTIRISHLAR',r'tarkib|almashtir|rotatsiya|yangi avlod|murabbiy|zaxira|yig.in'),
 ('INTIZOM',r'qizil kart|sariq kart|chetlat|qoida buz'),
 ('TO‘P NAZORATI',r'to.p.*(?:egalik|nazorat)|egalik.*to.p'),
 ('TURNIR JADVALI',r'ochko|jadval|o.rin|guruh.*(?:yetakchi|peshqadam)'),
 ('O‘YIN STATISTIKASI',r'zarba|foiz|%|xg|uzatma|burchak'),
 ('NATIJA',r'\b\d{1,2}:\d{1,2}\b|yakuniy hisob|hisobni teng'),
 ('JAMOA FORMASI',r'g.alaba|mag.lub|durang|yutqaz|yutgan|ketma.ket|seriya'),
 ('HUJUM VA HIMOYA',r'gol|hujum|himoya|darvoza|to.sin|vaziyat.*foydalan'),
 ('TAKTIKA',r'pressing|bosim|qanot|markaz|tezlik|temp|sur.at|standart|bo.sh hudud|muvozanat|intizom'),
 ('TAQVIM VA YUKLAMA',r'yuklama|dam ol|safar|noyabr|oktabr|sentabr|daqiq|charchoq'),
 ('MOTIVATSIYA',r'motivatsiya|revansh|saralash|final|chempion|derbi|stadion'),
]

def classify(text):
 t=norm(digits(text))
 if '?' in t or re.search(r'telegram|havola|obuna|izoh|assalomu|ko.rishguncha|prognoz|tanlov|\b[px]\s*(?:ikki|bir|1|2)\b|\b(?:1x|x2)\b',t):return ''
 kind=next((label for label,pattern in RULES if re.search(pattern,t)), '')
 if not kind:return ''
 if re.search(r'\bagar\b|mumkin|ehtimol|kutil|kafolat|degani emas',t):return 'EHTIMOL VA XAVF'
 return kind

def visual(text,title):
 source=digits(text);t=norm(source);items=[]
 if title!='EHTIMOL VA XAVF':
  pattern=r'(?P<n>\d+(?:[.,]\d+)?)\s*(?:ta(?:dan|si)?\s*)?(?P<a>(?:(?:urilgan|o.tkazib yuborilgan|aniq|muhim|so.nggi|oxirgi)\s+)*)(?P<u>%|foiz\w*|gol\w*|ochko\w*|zarba\w*|g.alaba\w*|mag.lubiyat\w*|durang\w*|uchrashuv\w*|o.yin\w*|tur\b|o.rin\w*|daqiqa\w*)'
  for m in re.finditer(pattern,t):
   value=m['n'];unit=m['u'];context=t[max(0,m.start()-35):m.end()+30]
   label=('Gollar' if unit.startswith('gol') else 'Ochkolar' if unit.startswith('ochko') else 'Zarbalar' if unit.startswith('zarba') else 'G‘alabalar' if re.match('g.alaba',unit) else 'Mag‘lubiyatlar' if re.match('mag.lubiyat',unit) else 'Duranglar' if unit.startswith('durang') else 'Uchrashuvlar' if re.match('uchrashuv|o.yin',unit) else 'O‘rin' if re.match('o.rin',unit) else 'Daqiqa' if unit.startswith('daqiqa') else 'Tur')
   if unit=='%' or unit.startswith('foiz'):
    if not 0<=float(value.replace(',','.'))<=100:continue
    value+='%';label='To‘p nazorati' if re.search('to.p|egalik',t) else 'Foiz'
   if label=='Gollar' and ('yubor' in m['a'] or re.match(r'\s*(?:ham\s+)?o.tkazib',t[m.end():])):label='O‘tkazilgan gollar'
   if label=='Zarbalar' and 'darvoza' in context and re.search('aniq|to.g.ri|tomon',context):label='Darvoza tomon zarbalar'
   qualifier=re.search(r'(atigi|kamida|taxminan|ko.pi bilan)\s*$',t[:m.start()])
   if qualifier:value=qualifier[1]+' '+value
   items.append(dict(value=value,label=label))
  # Result suffixes and time-of-day must not be confused.
  if not re.search(r'soat|vaqti',t):
   for score in re.findall(r'\b\d{1,2}:\d{1,2}\b',source):items.append(dict(value=score,label='Hisob'))
  for m in re.finditer(r'(?:urilgan gollar(?: soni)?|o.tkazib yuborilgan gollar)\s*[—:-]\s*(\d+)\s*(?:ta)?',t):
   items.append(dict(value=m[1],label='O‘tkazilgan gollar' if m[0].startswith("o't") else 'Gollar'))
 # Source sentence remains visible so owners, time windows and qualifiers survive.
 unique=list({(i['value'],i['label']):i for i in items}.values())[:6]
 return dict(source=source,caption=source,kind=title,metrics=unique,language='uz',sport='football')

def enrich(block,lines,cards):
 result=list(cards)
 protected={'ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','ТЕЛЕГРАМ','ПОДПИСКА','РАЗБОР МАТЧА','СМЕНА МАТЧА','ИТОГИ ВЫПУСКА'}
 for i,line in enumerate(lines):
  title=classify(line.text)
  if not title or line.end-line.start<.5 or str(i) in block.card_overrides:continue
  if any(c.line==i and (c.asset or c.title in protected) for c in result):continue
  result=[c for c in result if c.line!=i]
  result.append(Card(line.start,line.end,title,digits(line.text),line=i,visual=visual(line.text,title)))
 first=min((c.start for c in result if c.visual),default=float('inf'))
 for c in result:
  if c.title=='РАЗБОР МАТЧА' and c.line<0 and c.start<first<c.end:c.end=first
 return sorted([c for c in result if c.end-c.start>=.15],key=lambda c:c.start)
