"""Fighter identity, separated from changing records and betting opinions.

Full first names disambiguate shared surnames; nicknames are local aliases.
"""
import re,unicodedata
from functools import lru_cache
from difflib import SequenceMatcher
from .uzbek import norm

TRANSLIT=dict(zip('абвгдеёзийклмнопрстуфыэ','abvgdeezijklmnoprstufye'))
TRANSLIT.update({'ж':'zh','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ь':'','ъ':'','ю':'yu','я':'ya'})
VARIANTS={
 'ogan esyan':['agassan','agassian','oganesyan','agassen','aga isyan'],
 'chibisov':['shibysov','chiribesov','chibis'],
 'chijov':['chizhov','chirjov','chirishov','gatti'],
 'gadjiev':['gadzhiev','gajiev','gajiyev'],
 'pogodin':['paguddin','pogodiy','pogodiyin'],
 'barmin':['barmiyn','barmiy','balu'],
 'xalzov':['khalzov','halzov'],'espay':['yespay','y espay'],
 'staryx':['starykh'],'buxarov':['bukharov'],'sulgin':['shulgin'],
}
VARIANTS['oganesyan']=VARIANTS.pop('ogan esyan')

def normalized(text):
    t=''.join(TRANSLIT.get(c,c) for c in norm(text))
    t=''.join(c for c in unicodedata.normalize('NFKD',t) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]',' ',t)

def clean_name(name):
    name=re.sub(r'[“"«][^”"»]+[”"»]',' ',name)
    return ' '.join(re.sub(r'\s+(?:II|III|IV|2|3)\s*$','',name).split())

@lru_cache(maxsize=8192)
def identity(name):
    return ' '.join(normalized(clean_name(name)).split())

def same_fighter(a,b):
    # A shared surname alone does not make two named people identical.
    a=identity(a).split();b=identity(b).split()
    if a==b:return bool(a)
    if len(a)<2 or len(b)<2:return False
    return SequenceMatcher(None,a[0],b[0]).ratio()>=.8 and SequenceMatcher(None,a[-1],b[-1]).ratio()>=.8

@lru_cache(maxsize=1024)
def roster_names(name):
    from .fighter_roster import UFC_NAMES,TOPDOG_NAMES
    key=identity(name)
    # Full-name comparison keeps similarly named people distinct.
    return tuple(n for n in (*UFC_NAMES,*TOPDOG_NAMES) if identity(n)==key or same_fighter(n,name))


@lru_cache(maxsize=2048)
def aliases(name):
    words=identity(name).split()
    if not words:return []
    surname=words[-1]
    result=[surname,*VARIANTS.get(surname,[])]
    result+=re.findall(r'[“"«]([^”"»]+)[”"»]',name)
    for known in roster_names(name):
        result.append(identity(known).split()[-1])
        result+=re.findall(r'[“"«]([^”"»]+)[”"»]',known)
    return list(dict.fromkeys(' '.join(normalized(v).split()) for v in result))

def position(name,text):
    words=normalized(text).split();hits=[]
    for alias in aliases(name):
        count=len(alias.split())
        for i in range(len(words)-count+1):
            w=' '.join(words[i:i+count]);variants=[w]+[w[:-len(s)] for s in ('ning','dan','ga','ni','da') if w.endswith(s)]
            score=max(SequenceMatcher(None,alias,v).ratio() for v in variants)
            if score>=.80 and min(len(alias),len(w))>=4:hits.append((i,score))
    return max(hits,key=lambda h:h[1])[0] if hits else None
