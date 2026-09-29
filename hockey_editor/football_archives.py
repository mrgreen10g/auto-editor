"""Archive b-roll; explicit fixtures preferred, fallback always labelled."""
import re
from .model import EventRequest
from .alignment import split_script
from .team_names import FOOTBALL,football_identity,football_positions
from .graphics import block_teams


def events(block,matches):
    from .uzbek import classify,norm
    sources=[m for m in matches if m.id in block.match_ids and m.sport=='football']
    if not sources:return []
    def key(name):return football_identity(name) or norm(name)
    owners={key(n) for n in block_teams(block.title) if n}
    teams={m.id:{key(m.home),key(m.away)} for m in sources}
    catalog=set(FOOTBALL)|set().union(*teams.values())
    current=None;subject=None;counts={m.id:0 for m in sources};result=[]
    speech=[l['text'] for l in block.asr_lines] if block.asr_lines else split_script(block.script)
    for i,text in enumerate(speech):
        t=norm(text);title,_=classify(text)
        title=block.speech_cards.get(str(i),{}).get('title',title)
        if title in ('ПРОГНОЗ','УСЛОВИЯ ПРОГНОЗА','СОСТАВ КОМАНДЫ') or re.search(r'telegram|obuna|layk|tanlov',t):continue
        hits=sorted((a,n) for n in catalog for a,z in football_positions(n,text))
        named=list(dict.fromkeys(n for a,n in hits))
        if len(named)>=2:
            pair=set(named[:2]);exact=[m for m in sources if teams[m.id]==pair];subject=named[0]
            current=min(exact,key=lambda m:counts[m.id]) if exact else None
        elif named:
            if named[0] in owners:subject=named[0]
            if current and named[0] not in teams[current.id]:current=None
        if current is None:
            relevant=[m for m in sources if subject in teams[m.id]]
            if not relevant:relevant=[m for m in sources if teams[m.id]&owners]
            if not relevant and not any(football_identity(n) for n in owners):relevant=sources
            if not relevant:continue
            current=min(relevant,key=lambda m:counts[m.id])
        if len(t.split())>=6 or re.search(r'o.yn|o.yin|hujum|himoya|vaziyat|nazorat|bosim|hisob|uchrashuv|gol|safar|maydon',t):
            result.append(EventRequest(current.id,text,kind='play',requested_teams=list(owners)))
            counts[current.id]+=1
    return result
