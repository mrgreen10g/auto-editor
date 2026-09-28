"""Uzbek/Latin hockey names sharing the existing RU NHL/KHL identities.

Names are an identity catalog, not a season membership or results database.
Sources: https://www.nhl.com/info/teams/ and https://www.khl.ru/clubs/.
"""
import re,unicodedata
from functools import lru_cache
from .nhl import NHL,CODES
from .team_names import RU,ru_identity

KHL={
 'СКА':'SKA', 'ЦСКА':'CSKA|TsSKA|SSKA', 'Лада':'Lada|Tolyatti',
 'Динамо Москва':'Dinamo Moskva|Dynamo Moscow|Moskva Dinamo',
 'Динамо Минск':'Dinamo Minsk|Dynamo Minsk|Minsk Dinamo',
 'Северсталь':'Severstal|Cherepovets', 'Адмирал':'Admiral|Vladivostok',
 'Торпедо':'Torpedo|Nizhny Novgorod|Nijniy Novgorod', 'Спартак':'Spartak',
 'Ак Барс':'Ak Bars|Aq Bars|Kazan|Qozon', 'Автомобилист':'Avtomobilist|Yekaterinburg',
 'Металлург':'Metallurg|Metalurg|Magnitogorsk|Magnitka', 'Сибирь':'Sibir|Novosibirsk',
 'Сочи':'Sochi', 'Салават Юлаев':'Salavat Yulaev|Salavat Yulayev|Salavat|Ufa',
 'Локомотив':'Lokomotiv|Yaroslavl', 'Авангард':'Avangard|Omsk',
 'Трактор':'Traktor|Chelyabinsk', 'Амур':'Amur|Khabarovsk|Xabarovsk',
 'Барыс':'Barys|Baris|Astana', 'Шанхайские Драконы':'Shanghai Dragons|Shanxay Dragonlari|Shanxay|Shanghai',
 'Нефтехимик':'Neftekhimik|Nefteximik|Nizhnekamsk',
 'СКА-ВМФ':'SKA-VMF', 'Нефтяник':'Neftyanik',
}
PHONETIC=(
 'Anaxaym|Anahaym','Boston','Buffalo|Baffalo','Kalgari','Karolina',
 'Chikago','Kolorado','Kolambus','Dallas','Detroyt','Edmonton','Florida',
 'Los Anjeles|Los Anjeles Kings','Minnesota','Monreal|Monreal Kanadiens',
 'Neshvill|Nashvill','Nyu Jersi|Nyu Jersi Devils','Nyu York Aylanders|Aylanders',
 'Nyu York Reynjers|Reynjers|Reyndjers','Ottava','Filadelfiya','Pitsburg|Pittsburg',
 'San Xose|San Hoze','Sietl|Sietl Kraken','Sent Luis|Sent Luis Blyuz',
 'Tampa Bey','Toronto','Yuta|Yuta Mammot','Vankuver','Vegas|Veqas',
 'Vashington','Vinnipeg|Vinipeg',
)

def norm(text):
    t=''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',t.translate(str.maketrans({'’':"'",'‘':"'",'ʻ':"'",'ʼ':"'",'ё':'е'}))).strip()

ALIASES={k:tuple(v.split('|')) for k,v in KHL.items()}
for club,code,extra in zip(NHL,CODES,PHONETIC):
    parts=club.split();city=' '.join(parts[:-2] if club in ('Toronto Maple Leafs','Detroit Red Wings','Columbus Blue Jackets','Vegas Golden Knights') else parts[:-1])
    if club=='St. Louis Blues':city='St. Louis'
    aliases=[club,code,*extra.split('|')]
    if city not in ('New York',):aliases.append(city)
    # A distinct nickname is useful in the second sentence of a team discussion.
    aliases.append(' '.join(parts[len(city.split()):]))
    ALIASES[club]=tuple(dict.fromkeys(x for x in aliases if x))
ALIASES['New York Rangers']+=('NY Rangers',)
ALIASES['New York Islanders']+=('NY Islanders',)

@lru_cache(maxsize=1)
def patterns():
    result=[]
    for club,aliases in ALIASES.items():
        for alias in aliases:
            pattern=re.escape(norm(alias)).replace(r'\ ',r'[\s-]+')
            result.append((club,re.compile(r'(?<!\w)'+pattern+r"(?:'?ning|ning|niki|ni|ga|ka|da|dan|dagi|lar|larning)?(?!\w)")))
    for club,values in RU.items():
        for pattern in values:result.append((club,re.compile(r'(?<!\w)(?:'+pattern+r')(?!\w)')))
    return result

@lru_cache(maxsize=8192)
def hits(text):
    t=norm(text);found=[(m.start(),m.end(),club) for club,pattern in patterns() for m in pattern.finditer(t)]
    selected=[]
    for a,z,club in sorted(set(found),key=lambda x:(-(x[1]-x[0]),x[0])):
        if not any(a<y and z>x for x,y,_ in selected):selected.append((a,z,club))
    return sorted(selected)

def identity(name):
    found=hits(name);values={c for a,z,c in found};rest=list(norm(name))
    for a,z,_ in found:rest[a:z]=' '*(z-a)
    remainder=re.sub(r'\b(?:hc|hk|хк)\b','', ''.join(rest))
    return next(iter(values)) if len(values)==1 and not re.search(r'\w',remainder) else None

def canonicalize(text):
    t=norm(text)
    for a,z,club in reversed(hits(t)):t=t[:a]+club+t[z:]
    return t

def mentioned(text):return list(dict.fromkeys(c for _,_,c in hits(text)))

def pair_in(title,text):
    from .graphics import block_teams
    names=[identity(n) for n in block_teams(title)]
    return all(names) and len(set(names))==2 and set(names).issubset(mentioned(text))

def display(name):return ALIASES.get(name,(name,))[0] if name not in NHL else name
