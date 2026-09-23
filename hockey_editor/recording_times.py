"""Optional user-verified recording sections, distinct from authored script times."""
import re

def parse_times(text,count,include_outro=True):
    rows=[]
    pattern=r'^\s*(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)\s+(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)\s+(.+?)\s*$'
    def seconds(value):
        parts=[float(v) for v in value.replace(',','.').split(':')]
        if any(v>=60 for v in parts[1:]):raise ValueError('Секунды и минуты должны быть меньше 60.')
        result=0
        for part in parts:result=result*60+part
        return result
    for line in text.splitlines():
        if not line.strip():continue
        match=re.match(pattern,line)
        if not match:raise ValueError('Формат таймкода: 00:32 02:08 Augsburg Bayer. Каждая строка — отдельный раздел.')
        a,b=seconds(match[1]),seconds(match[2])
        if b<=a:raise ValueError('Конец раздела должен быть позже начала.')
        if rows and a<rows[-1][1]:raise ValueError('Разделы таймкодов пересекаются или идут не по порядку.')
        rows.append((a,b,match[3]))
    if not include_outro and len(rows)!=count+1:
        raise ValueError(f'Нужно: начало и {count} разбора по порядку. В этом сценарии нет завершения.')
    if include_outro and len(rows) not in (count+2,count+3):
        raise ValueError(f'Нужно: начало, {count} разбора по порядку и завершение. Итоги и прощание можно указать двумя строками.')
    return rows

def recording_ranges(project,segments):
    rows=parse_times(project.recording_times,len(project.blocks))
    last=max(w['end'] for s in segments for w in s['words'])
    if rows[-1][1]>last+3:raise ValueError('Таймкоды выходят за запись. Укажите время исходного видео, не примерное время из сценария.')
    # User labels are descriptive; actual project blocks retain their canonical names.
    # Whole-second markers may fall inside a sentence; recover its beginning nearby.
    starts=[s['start'] for s in segments]
    anchors=[row[0] for row in rows[:len(project.blocks)+2]]
    bounds=[]
    for anchor in anchors:
        nearby=[v for v in starts if abs(v-anchor)<=2.5]
        bounds.append(min(nearby,key=lambda v:abs(v-anchor)) if nearby else anchor)
    ends=[w['end'] for s in segments for w in s['words']]
    ranges=[]
    for i,start in enumerate(bounds):
        # Keep supplied ends: the next start may follow a long recording break.
        # Recap and farewell remain one logical outro.
        anchor=rows[i][1] if i<len(bounds)-1 else rows[-1][1]
        limit=bounds[i+1] if i+1<len(bounds) else last
        nearby=[v for v in ends if abs(v-anchor)<=2.5 and start<v<=limit]
        end=max(nearby) if nearby else min(anchor,limit)
        if end-start<3:raise ValueError('Уточнённые разделы пересекаются или слишком короткие. Проверьте таймкоды записи.')
        ranges.append((start,end))
    return ranges

def recording_bounds(project,segments):
    ranges=recording_ranges(project,segments)
    return [a for a,b in ranges]+[ranges[-1][1]]
