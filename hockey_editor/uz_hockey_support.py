"""Conservative grounding of noisy Uzbek hockey speech."""
import re
from collections import Counter
from .hockey_names import mentioned, pair_in
from .uzbek import norm


def check_script(project,segments):
    if not segments or segments[-1]['end']<45:return
    expected={n for b in project.blocks for n in mentioned(b.title)}
    counts=Counter(n for s in segments for n in mentioned(s['text']))
    heard={n for n,count in counts.items() if count>=2}
    # Strong positive evidence for another episode, not just missing ASR names.
    if len(expected)>=4 and len(heard-expected)>=3 and len(expected & heard)<len(expected)/2:
        raise ValueError('Видео и сценарий описывают разные матчи. В речи: '+', '.join(sorted(heard))+'. В проекте: '+', '.join(b.title for b in project.blocks)+'. Загрузите сценарий именно этой записи и проверьте назначенные матчи. Повторная разметка не заменяет неверный сценарий.')


def forecast_span(block,segments,lo,hi):
    from .uz_hockey import bet, numeric, forecast_conflict
    from .framing import forecast_text
    expected=forecast_text(block)
    if not expected:return None
    choices=[]
    local=[s for s in segments if lo<=s['start']<hi]
    for i,s in enumerate(local):
        if s['start']<lo+(hi-lo)*.35:continue
        for count in (1,2,3):
            group=local[i:i+count]
            if len(group)!=count or group[-1]['end']-s['start']>30:continue
            text=' '.join(v['text'] for v in group);t=norm(text)
            if not re.search(r'tanlo|tanlu|tanla|varia|qildik',t):continue
            if re.search(r'olmayman|tanlamayman',t):continue
            from .graphics import block_teams
            names=block_teams(block.title)
            if re.search(r'yutqazm',t):
                for side,name in enumerate(names):
                    if set(mentioned(name)) & set(mentioned(text)):
                        text=name+(' 1X ' if side==0 else ' X2 ')+text;break
            actual=bet(text)
            if not actual:continue
            reason=forecast_conflict(expected,text)
            # Never silently overwrite conflicting spoken numbers or direction.
            confidence=6 if not reason else 0
            confidence+=2 if re.search(r'tanlo|varia|qildik',t) else 0
            confidence-=.04*(group[-1]['end']-s['start'])
            if reason:continue
            fuzzy=bool(re.search(r'to.riyam|brix|briggs|beshtana|beshtandan|beshtada\b|yutqazmini',t))
            choices.append((confidence,s['start'],group[-1]['end'],expected,
                            'Проверьте нечётко произнесённое число или рынок ставки.' if fuzzy else ''))
    return max(choices,default=None)
