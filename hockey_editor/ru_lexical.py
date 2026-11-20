"""Equivalent spellings for alignment only; original ASR remains visible."""
import re
from functools import lru_cache
@lru_cache(maxsize=1)
def aliases():
 from .team_names import FOOTBALL
 result=[]
 for names in FOOTBALL.values():
  russian=next((n for n in names if re.fullmatch(r'[А-Яа-яЁё .-]+',n)),None)
  if russian:
   for name in names:
    if re.search('[a-zA-Z]',name):result.append((name,russian.lower()))
 return [(re.compile(r'(?<!\w)'+re.escape(a)+r'(?!\w)',re.I),b) for a,b in sorted(result,key=lambda x:-len(x[0]))]
@lru_cache(maxsize=8192)
def names(text):
 for pattern,value in aliases():text=pattern.sub(value,text)
 return text
@lru_cache(maxsize=8192)
def normalized(text):
 from .combat_facts import digits
 t=digits(names(text));t=re.sub(r'(?<!\w)1\s*[xх](?!\w)','1 икс',t,flags=re.I)
 return re.sub(r'(?<!\w)[xх]\s*2(?!\w)','икс 2',t,flags=re.I)
