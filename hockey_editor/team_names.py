"""Club identities and attested names; shared cities require fixture context.

The aliases describe names, not current league membership. Script spelling is
kept for graphics. Never infer a club from Manchester/Moscow alone.
"""
import re
import unicodedata
from functools import lru_cache

CATALOG_VERSION = 'teams-1'

@lru_cache(maxsize=8192)
def normalize(text):
    return unicodedata.normalize('NFKC', text).casefold().replace('ё','е').translate(
        str.maketrans({'’':"'",'‘':"'",'ʻ':"'",'ʼ':"'",'`':"'",'«':' ', '»':' ', '"':' '}))

RU = {
 'СКА': (r'ска(?!\s*[-—]\s*вмф)',),
 'ЦСКА': (r'цска',),
 'Лада': (r'лад[аыуе]|ладой', r'тольятт\w*'),
 'Динамо Москва': (r'московск\w*\s+динамо|динамо\s+москв\w*',),
 'Динамо Минск': (r'минск\w*\s+динамо|динамо\s+минск\w*', r'минск\w*|минчан\w*'),
 'Северсталь': (r'северстал\w*', r'черепов\w*'),
 'Адмирал': (r'адмирал\w*', r'владивосток\w*'),
 'Торпедо': (r'торпедо', r'нижн\w*\s+новгород\w*|нижегород\w*'),
 'Спартак': (r'спартак\w*',),
 'Ак Барс': (r'ак\s+барс\w*', r'казан\w*'),
 'Автомобилист': (r'автомобилист\w*', r'екатеринбург\w*|екатеринбурж\w*'),
 'Металлург': (r'металлург\w*', r'магнитк\w*|магнитогор\w*'),
 'Сибирь': (r'сибир\w*', r'новосибир\w*'),
 'Сочи': (r'сочи',),
 'Салават Юлаев': (r'салават\w*(?:\s+юлаев\w*)?', r'уф[ауыуе]|уфим\w*'),
 'Локомотив': (r'локомотив\w*', r'ярослав\w*'),
 'Авангард': (r'авангард\w*', r'омск\w*|омич\w*'),
 'Трактор': (r'трактор\w*', r'челябин\w*'),
 'Амур': (r'амур(?:а|у|ом|е)?', r'хабаров\w*'),
 'Барыс': (r'барыс\w*', r'астан\w*'),
 'Шанхайские Драконы': (r'шанха\w*|дракон\w*',),
 'Нефтехимик': (r'нефтехимик\w*', r'нижнекам\w*'),
 # Mentioned as preseason opponents; never conflate them with the senior clubs.
 'СКА-ВМФ': (r'ска\s*[-—]\s*вмф',),
 'Нефтяник': (r'нефтяник\w*',),
}
RU_CONTEXT = {
 r'москв\w*|москвич\w*': ('Динамо Москва','ЦСКА','Спартак'),
 r'(?:санкт[- ]?)?петербург\w*|питер\w*': ('СКА','Шанхайские Драконы'),
 r'армей\w*': ('СКА','ЦСКА'),
 r'динамо': ('Динамо Москва','Динамо Минск'),
}

def _matches(pattern,text):
    return list(re.finditer(r'(?<!\w)(?:'+pattern+r')(?!\w)',normalize(text)))

def _city_matches(pattern,text,context):
    result=[]
    for match in _matches(pattern,text):
        prefix=normalize(text)[:match.start()]
        # A tournament name is never an opponent. Location alone is only useful
        # inside an already known fixture (e.g. the intro: "едет в Челябинск").
        if re.search(r'(?:кубк\w*|турнир\w*|мемориал\w*)\s+$',prefix):continue
        if not context and re.search(r'\b(?:в|во|из)\s+$',prefix):continue
        result.append(match)
    return result

@lru_cache(maxsize=2048)
def ru_identity(name):
    text=normalize(name).strip()
    if text=='динамо':return 'Динамо'
    # Qualified Dynamo forms must be tested before the generic name.
    for canonical,patterns in RU.items():
        if any(_matches(pattern,text) for pattern in patterns):return canonical
    return None

def ru_position(name,text,context=()):
    identity=ru_identity(name)
    if not identity:return None
    value=normalize(text)
    if identity in ('Динамо','Динамо Москва','Динамо Минск'):
        qualified=[]
        for club in ('Динамо Москва','Динамо Минск'):
            qualified.extend((m.start(),m.end(),club) for m in _matches(RU[club][0],value))
        hits=[a for a,z,club in qualified if club==identity or (identity=='Динамо' and club=='Динамо Москва')]
        unqualified=[m.start() for m in _matches('динамо',value)
                     if not any(a<=m.start()<z for a,z,_ in qualified)]
        candidates={ru_identity(n) for n in context}
        if identity in ('Динамо','Динамо Москва') and 'Динамо Минск' not in candidates:hits+=unqualified
        if identity=='Динамо Минск' and 'Динамо Минск' in candidates and not candidates.intersection({'Динамо','Динамо Москва'}):hits+=unqualified
        if identity=='Динамо Минск':hits += [m.start() for m in _city_matches(RU[identity][1],value,context)]
    else:
        hits=[m.start() for i,pattern in enumerate(RU[identity])
              for m in (_matches(pattern,value) if i==0 else _city_matches(pattern,value,context))]
    candidates={ru_identity(n) for n in context}
    candidates={'Динамо Москва' if n=='Динамо' else n for n in candidates}
    for pattern,clubs in RU_CONTEXT.items():
        selected=candidates.intersection(clubs)
        target='Динамо Москва' if identity=='Динамо' else identity
        if selected=={target} and pattern!='динамо':hits += [m.start() for m in _matches(pattern,value)]
    return min(hits) if hits else None

# Full names plus independent, distinctive short names. Ambiguous single words
# are deliberately absent (Manchester, United, City, Madrid, London, Toshkent).
FOOTBALL = {
 'OKMK': ('OKMK','AGMK','ОКМК','АГМК'),
 'Paxtakor': ('Paxtakor','Pakhtakor','Пахтакор'),
 'Neftchi': ('Neftchi','Neftchi Fargona','Нефтчи'),
 'Surxon': ('Surxon','Surkhon','Сурхон'),
 'Nasaf': ('Nasaf','Насаф'),
 'Bunyodkor': ('Bunyodkor','Бунёдкор','Бунедкор'),
 'Xorazm Urganch': ('Xorazm Urganch','Xorazm','Khorezm','Хорезм'),
 "So'g'diyona": ("So'g'diyona",'Sogdiyona','Sogdiana','Согдиана'),
 'Buxoro': ('Buxoro','Bukhara','Бухара'),
 'Navbahor': ('Navbahor','Navbakhor','Навбахор'),
 'Lokomotiv Toshkent': ('Lokomotiv Toshkent','Lokomotiv Tashkent','Локомотив Ташкент','Lokomotiv'),
 "Mash'al": ("Mash'al",'Mashal','Машал'),
 'Union Berlin': ('Union Berlin','Union','Унион Берлин','Унион'),
 'Schalke': ('Schalke','Shalke','Шальке'),
 'Augsburg': ('Augsburg','Аугсбург'),
 'Bayer': ('Bayer','Bayer Leverkusen','Leverkusen','Байер'),
 'Borussia Dortmund': ('Borussia Dortmund','Borussiya Dortmund','Dortmund','Borussiya','Боруссия Дортмунд','Дортмунд'),
 'Paderborn': ('Paderborn','Padedborn','Padeborn','Падерборн'),
 'Mainz': ('Mainz','Mayns','Mays','Майнц'),
 'Eintracht Frankfurt': ('Eintracht Frankfurt','Ayntraxt Frankfurt','Ayntraxt','Eintraxt','Eintracht','Айнтрахт'),
 'Liverpool': ('Liverpool','Liverpul','Ливерпуль'),
 'Fulham': ('Fulham','Fulhem','Фулхэм'),
 'Chelsea': ('Chelsea','Chelsi','Челси'),
 'Hull': ('Hull','Hall','Hull City','Халл'),
 'Tottenham': ('Tottenham','Tottenxem','Тоттенхэм'),
 'Everton': ('Everton','Эвертон'),
 'Sunderland': ('Sunderland','Sanderlend','Сандерленд'),
 'Arsenal': ('Arsenal','Арсенал'),
 'Coventry City': ('Coventry City','Koventri Siti','Coventry','Koventri','Ковентри'),
 'Brighton': ('Brighton','Brayton','Брайтон'),
 'Manchester United': ('Manchester United','Manchester Yunayted','Манчестер Юнайтед'),
 'Manchester City': ('Manchester City','Manchester Siti','Манчестер Сити'),
 'Como': ('Como','Komo','Комо'),
 'Parma': ('Parma','Парма'),
 'Torino': ('Torino','Торино'),
 'Roma': ('Roma','Рома'),
 'Inter': ('Inter','Inter Milan','Интер'),
 'Udinese': ('Udinese','Udineze','Удинезе'),
 'Rayo Vallecano': ('Rayo Vallecano','Rayo Valyekano','Rayo','Райо Вальекано'),
 'Espanyol': ('Espanyol','Эспаньол'),
 'Alaves': ('Alaves','Алавес'),
 'Valencia': ('Valencia','Valensiya','Валенсия'),
 'Elche': ('Elche','Эльче'),
 'Real Madrid': ('Real Madrid','Реал Мадрид'),
 'Nottingham Forest': ('Nottingham Forest','Nottingham','Forest','Ноттингем Форест'),
 'Bournemouth': ('Bournemouth','Bornmut','Борнмут'),
 'Newcastle United': ('Newcastle United','Newcastle','Nyukasl','Ньюкасл'),
 'Ipswich Town': ('Ipswich Town','Ipswich','Ипсвич'),
 'Aston Villa': ('Aston Villa','Villa','Астон Вилла'),
 'Celta': ('Celta','Selta','Сельта'),
 'Athletic': ('Athletic','Athletic Bilbao','Atletik','Атлетик'),
 'Osasuna': ('Osasuna','Осасуна'),
 'Getafe': ('Getafe','Хетафе'),
 'Barcelona': ('Barcelona','Barselona','Барселона'),
 'Toulouse': ('Toulouse','Tuluza','Тулуза'),
 'Lille': ('Lille','Lill','Лилль'),
 'Lyon': ('Lyon','Lion','Лион'),
 'Auxerre': ('Auxerre','Oser','Осер'),
 'PSG': ('PSG','PSJ','Paris Saint Germain','ПСЖ'),
 'Monaco': ('Monaco','Monako','Монако'),
}
FOOTBALL_CONTEXT = {'Real': ('Real Madrid',), 'Yunayted': ('Manchester United','Newcastle United'),
                    'United': ('Manchester United','Newcastle United'),
                    'Siti': ('Manchester City','Coventry City','Hull'),
                    'City': ('Manchester City','Coventry City','Hull')}

def compact(text):return ''.join(c for c in normalize(text) if c.isalnum())

@lru_cache(maxsize=2048)
def football_identity(name):
    key=compact(name)
    return next((club for club,aliases in FOOTBALL.items() if key in [compact(a) for a in aliases]),None)

def football_aliases(name,context=()):
    club=football_identity(name)
    result=list(FOOTBALL.get(club,(name,)))
    known={football_identity(n) for n in context}
    for alias,clubs in FOOTBALL_CONTEXT.items():
        if club and known.intersection(clubs)=={club}:result.append(alias)
    return tuple(result)

def football_positions(name,text,context=()):
    text=normalize(text);hits=[]
    suffix=r"(?:'?(?:ning|ni|ga|da|dan|mi))?"
    for alias in football_aliases(name,context):
        pattern=r'\s+'.join(re.escape(w) for w in normalize(alias).split())
        hits.extend((m.start(),m.end()) for m in re.finditer(r'(?<!\w)'+pattern+suffix+r'(?!\w)',text))
    return sorted(set(hits))

def football_names(text):
    found=[(hits[0][0],club) for club in FOOTBALL if (hits:=football_positions(club,text))]
    return [club for _,club in sorted(found)[:2]]

def ru_file_names(text):
    from .event_rules import suggested_names
    names=suggested_names(text)
    if 'Динамо' in names and _matches(RU['Динамо Москва'][0],text):
        names[names.index('Динамо')]='Динамо Москва'
    return names
