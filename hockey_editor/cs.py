"""Counter-Strike vocabulary, editorial statistics and archive illustration requests."""
import re
from functools import lru_cache
from .cs_catalog import TEAMS
TEAM_RU='мауз|фурия|виталити|спирит|аврора|фальконс|бетбум|нави|фут|монголз|немига|джи ту|паривижн|легаси|ван вин|мибр|ликвид|фейз|найн зи|астралис|бейт|нип|этернал файр|эм эйти|хероик|геймер легион|фнатик|энви|мэджик|тайлу|хоту|биг|сто тивс|люминосити|денделе|эн эр джи|иннер серкл|джи джи хао|альянс|синнерс|пейн|сангал|вайлдкард|лин вижн|кей двадцать семь|прайвет|би си гейм|империал|файв стар|би би эл|немезис|нексус|фокус|ибериан соул|бетклик|блэк феникс|бестия|шинден|айболлерс|флайквест|нуклеар тайгерс|чингис ворриорз|бейсмент бойз|соу|метизпорт|флуксо|галорис|фантом|нексвойд|вока|барса|пьюр|лоу кортизол|юнити|ребелс|баунти хантерс|виртус про|инфинит|дабл ю би ти|лео|эймклаб|нави джуниор|визаут э руф|апгрейд|процион|зэ ханс|джонни спидс|квазар|спирит академи|меллрен|дабл ю би ти академи|марсборн|иннер серкл академи|лейзер кэтс|экс зеро тенасити|бакс|оу джи|брут|иллирийанс|глитч'.split('|')
SPECIAL={'G2':['джи-ту','джиту','джи два'],'MOUZ':['моуз','маусы'],'FURIA':['фурии','фурию'],'Spirit':['тим спирит','team spirit','спирита'],'Aurora':['авроры','авророй','аврору'],'Natus Vincere':['navi','на-ви','натус винсере'],'Ninjas in Pyjamas':['nip'],'The MongolZ':['монголы'],'3DMAX':['три-ди-макс','три ди макс'],'9z':['найнз'],'XANTARES':['ксантэрес','ксантарес'],'woxic':['воксик'],'Wicadia':['викадия'],'Jimpphat':['джимпхат'],'kyxsan':['киксан'],'KSCERATO':['ксерато','ксцерато'],'donk':['донк','донка'],'sh1ro':['широ'],'m0NESY':['монеси'],'NiKo':['нико'],'ZywOo':['зайву'],'huNter-':['хантер'],'FalleN':['фоллен'],'Spinx':['спинкс'],'device':['девайс'],'rain':['рейн'],'s1mple':['симпл'],'Boombl4':['бумыч'],'b1t':['бит'],'w0nderful':['вондерфул'],'FL1T':['флит'],'Jame':['джейм'],'ropz':['ропз']}
assert len(TEAM_RU)==len(TEAMS)
for row,ru in zip(TEAMS,TEAM_RU):SPECIAL.setdefault(row['name'],[]).insert(0,ru)
LETTERS=dict(zip('abcdefghijklmnopqrstuvwxyz',['эй','би','си','ди','и','эф','джи','эйч','ай','джей','кей','эл','эм','эн','оу','пи','кью','ар','эс','ти','ю','ви','дабл ю','экс','уай','зэд']))
def key(text):return re.sub(r'[^a-zа-я0-9]','',text.casefold().replace('ё','е'))
def translit(text):
 text=text.lower()
 for a,b in [('sh','ш'),('ch','ч'),('zh','ж'),('th','т'),('ph','ф'),('oo','у'),('ee','и')]:text=text.replace(a,b)
 return text.translate(str.maketrans(dict(zip('abcdefghijklmnopqrstuvwxyz',['а','б','к','д','е','ф','г','х','и','дж','к','л','м','н','о','п','к','р','с','т','у','в','в','кс','и','з']))))
def aliases(name):
 variants=[name,*SPECIAL.get(name,[]),translit(name),translit(name.translate(str.maketrans('013457','oieast')))]
 if name.isupper() and len(name)<=5:variants.append(' '.join(LETTERS.get(c,c) for c in name.lower()))
 return list(dict.fromkeys(v for v in variants if v))
TEAM_NAMES=[r['name'] for r in TEAMS]+['3DMAX']
PLAYERS=list(dict.fromkeys(p for r in TEAMS for p in r['players']))
DICTIONARY={n:aliases(n) for n in dict.fromkeys(TEAM_NAMES+PLAYERS)}
LOOKUP={key(a):n for n in TEAM_NAMES for a in DICTIONARY[n]}
def identity(name):return LOOKUP.get(key(name),name.strip(' «»".'))
def pattern(alias):return r'[\s\-—–]*'.join(re.escape(v) for v in re.split(r'[\s\-—–]+',alias) if v)
@lru_cache(maxsize=1)
def team_patterns():return [(n,re.compile(r'(?<!\w)(?:'+'|'.join(pattern(a) for a in DICTIONARY[n])+r')(?!\w)',re.I)) for n in TEAM_NAMES]
def mentioned(text):
 hits=sorted((m.start(),-len(m[0]),m.end(),n) for n,p in team_patterns() for m in p.finditer(text))
 accepted=[];last=-1
 for a,_,z,n in hits:
  if a<last:continue
  accepted.append(n);last=z
 return list(dict.fromkeys(accepted))
def pair_heading(text):
 parts=re.split(r'\s+[—–-]\s+|\s+vs\.?\s+',text.strip(' «»".'),flags=re.I)
 if len(parts)!=2 or len(text)>100:return None
 names=[identity(p) for p in parts]
 return ' — '.join(names) if all(n in TEAM_NAMES for n in names) else None

def classify(text):
 t=text.lower();body=text.strip()
 if re.search(r'телеграм|telegram',t):return 'ТЕЛЕГРАМ',body
 if re.search(r'(?:мой|основной)\s+(?:выбор|прогноз)\s*(?:—|–|-|:|это)|\b(?:беру|выбираю|ставлю на)\b',t) and not re.search(r'\bне\s+(?:беру|выбираю|ставлю)|не стал бы|не буду',t) and mentioned(text):return 'ПРОГНОЗ',body
 if re.search(r'процент|%|винрейт|win\s*rate',t):return ('ПИСТОЛЕТНЫЕ РАУНДЫ' if 'пистолет' in t else 'ВИНРЕЙТ КАРТЫ'),body
 if re.search(r'рейтинг\s+(?:один|ноль|[0-9]+[.,])|\b(?:adr|kast|kd|k/d|rating)\b|килл|фраг|убийств|хедшот',t):return 'СТАТИСТИКА ИГРОКА',body
 if re.search(r'\d+\s*[:–-]\s*\d+|(?:тринадцать|четырнадцать|пятнадцать|шестнадцать|два|один)[ -](?:ноль|один|два|три|четыре|пять|шесть|семь|восемь|девять|десять|четырнадцать)',t):return 'РЕЗУЛЬТАТ КАРТЫ' if re.search(r'карт|мираж|нюк|даст|инферно|эншент|тринадцать|шестнадцать',t) else 'РЕЗУЛЬТАТ СЕРИИ',body
 if re.search(r'пистолет|экономик|форс.?бай|эко.?раунд|клатч|оверта[йи]м|вето|мр12|mr12|bo[135]',t):return 'СТАТИСТИКА CS',body
 if re.search(r'карт|раунд|побед|поражен|рейтин',t) and re.search(r'\d|процент|подряд|пяти|трех|четырех|пять|три|четыре|десяти',t):return 'СТАТИСТИКА CS',body
 return None,''
def forecast(script):
 from .alignment import split_script
 picks=[body for row in split_script(script) for title,body in [classify(row)] if title=='ПРОГНОЗ']
 return picks[-1] if picks else ''
def events(block,matches):
 from .model import EventRequest
 from .alignment import split_script
 sources=[m for m in matches if m.id in block.match_ids and m.sport=='cs']
 if not sources:return []
 rows=[l['text'] for l in block.asr_lines] if block.asr_lines else split_script(block.script);result=[]
 for row in rows:
  title,_=classify(row)
  if len(row.split())<6 or title in ('ТЕЛЕГРАМ','ПРОГНОЗ') or re.search(r'подпис|ссылк|лайк',row,re.I):continue
  source=sources[len(result)%len(sources)];result.append(EventRequest(source.id,row,kind='play',strict_source=True))
 return result

def prepare_script(block):
 text=block.script
 if block.kind=='intro':text=re.sub(r',\s+(?=(?:а\s+)?[«"А-ЯA-Z])','\n',text)
 from .alignment import split_script
 rows=[]
 for row in split_script(text):
  if rows and re.match(r'ссылка\b',row,re.I) and re.search(r'телеграм',rows[-1],re.I):rows[-1]=rows[-1].rstrip('.!?')+' — '+row
  else:rows.append(row)
 return '\n'.join(rows)
@lru_cache(maxsize=1)
def speech_vocabulary():
 entries={}
 for i,(name,variants) in enumerate(DICTIONARY.items()):
  code='cs'+chr(97+i//676)+chr(97+(i//26)%26)+chr(97+i%26)
  for v in variants:entries[v.casefold()]=code
 parts=[];lookup={}
 for v in sorted(entries,key=len,reverse=True):
  parts.append(pattern(v));lookup[key(v)]=entries[v]
 return re.compile(r'(?<!\w)(?:'+'|'.join(parts)+r')(?!\w)',re.I),lookup
def normalize_speech(text):
 p,lookup=speech_vocabulary();return p.sub(lambda m:lookup[key(m[0])],text)
def speech_name(text):return bool(speech_vocabulary()[0].fullmatch(text))
