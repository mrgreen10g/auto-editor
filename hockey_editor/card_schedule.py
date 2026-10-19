"""Resolve automatic cards within their own spoken intervals."""
import copy
from .timeline import frame


def exclusive(cards):
    priority={'ТЕЛЕГРАМ':5,'ПОДПИСКА':5,'ПРОГНОЗ':4,'РАЗБОР МАТЧА':3}
    accepted=[];omitted=[]
    for _,original in sorted(enumerate(cards),key=lambda v:(-priority.get(v[1].title,1),v[1].start,v[0])):
        intervals=[(original.start,original.end)]
        for busy in accepted:
            remaining=[]
            for a,z in intervals:
                if busy.start>=z or busy.end<=a:remaining.append((a,z))
                else:
                    if a<busy.start:remaining.append((a,busy.start))
                    if busy.end<z:remaining.append((busy.end,z))
            intervals=remaining
        valid=[(frame(a),frame(z)) for a,z in intervals if frame(z)-frame(a)>=.5]
        if not valid:omitted.append(original);continue
        a,z=max(valid,key=lambda span:span[1]-span[0])
        card=copy.copy(original);card.start=a;card.end=z
        # Frame rounding may move the start backwards by a sub-frame epsilon.
        # Only actual trimming consumes time in the animation source.
        if card.asset:card.source_in+=max(0.,a-original.start)
        accepted.append(card)
    return sorted(accepted,key=lambda c:(c.start,c.end)),omitted

