"""Durable timeline edits and validation shared by preview and final export."""
import copy
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from .timeline import Plan


def project_edit_key(project, index):
    block = asdict(project.blocks[index]); block.pop('edit_plan',None);block.pop('edit_key',None)
    block.pop('kind',None);block.pop('uid',None)  # Preserve the v0.4 per-block edit fingerprint.
    def identity(path):
        if not path: return None
        p=Path(path)
        if not p.is_file(): return [str(p),'missing']
        st=p.stat();return [str(p.resolve()),st.st_size,st.st_mtime_ns]
    structural={k:getattr(project.settings,k) for k in ('cut_pauses','insert_frequency','auto_rotate','rotate','use_manual_clips','allow_other_matches')}
    for clip in block['clips']:
        clip['path']=identity(clip['path'])
        if clip.get('origin_path'):clip['origin_path']=identity(clip['origin_path'])
    data=[block,structural,identity(project.host),
          [(m.id,m.home,m.away,identity(m.path),m.score_box) for m in project.matches if m.id in block['match_ids']]]
    if len(project.host_paths())>1:data.append([identity(path) for path in project.host_paths()])
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def validate_plan(plan, check_files=True):
    if not math.isfinite(plan.duration) or plan.duration<=0: raise ValueError('Некорректная длина дорожки.')
    def span(start,end):
        if not all(math.isfinite(v) for v in (start,end)) or not 0<=start<end<=plan.duration+.034:
            raise ValueError('Границы элемента должны находиться внутри дорожки.')
        if end-start<.15: raise ValueError('Элемент слишком короткий.')
    end=0
    for c in sorted(plan.inserts,key=lambda c:c.start):
        span(c.start,c.end)
        if c.start<end-.001: raise ValueError('Игровые вставки пересекаются. Сдвиньте или сократите одну из них.')
        end=c.end
        if not all(math.isfinite(v) for v in (c.source_in,c.source_min)) or c.source_in<c.source_min-.001:
            raise ValueError('Начало вышло за проверенный игровой фрагмент.')
        if c.source_max is not None and not math.isfinite(c.source_max):raise ValueError('Некорректная граница исходника.')
        if c.source_max is not None and c.source_in+c.end-c.start>c.source_max+.034:
            raise ValueError('Вставка выходит за конец игрового фрагмента. Сократите её или выберите другой момент.')
        if check_files and not Path(c.path).is_file(): raise ValueError('Не найдена запись: '+c.path)
    for c in plan.cards:
        span(c.start,c.end)
        if c.asset:
            if check_files and not Path(c.asset).is_file():raise ValueError('Не найдена анимация: '+c.asset)
            if not math.isfinite(c.source_in) or c.source_in<0:raise ValueError('Некорректное начало анимации.')
        if c.title=='ТЕЛЕГРАМ' and c.line>=0:
            line=plan.lines[c.line]
            if abs(c.start-line.start)>.035 or abs(c.end-line.end)>.035:
                raise ValueError('Telegram должен занимать ровно фразу о канале и ссылке. Измените текст начала или конца и определите тайминги заново.')
        if not c.text.strip(): raise ValueError('Плашка пуста. Удалите её или введите текст.')
    if not plan.keep or any(not all(math.isfinite(v) for v in (a,b)) or a<0 or b<=a for a,b in plan.keep):
        raise ValueError('Повреждена дорожка речи.')
    if abs(sum(b-a for a,b in plan.keep)-plan.duration)>.07:
        raise ValueError('Длительность речи не совпадает с дорожкой.')
    if plan.media:
        if abs(sum(m['end']-m['start'] for m in plan.media)-plan.duration)>.1:
            raise ValueError('Длительность исходников не совпадает с дорожкой.')
        for m in plan.media:
            if not all(math.isfinite(m[k]) for k in ('start','end')) or not 0<=m['start']<m['end']:
                raise ValueError('Повреждены границы исходной записи.')
            if check_files and not Path(m['path']).is_file():raise ValueError('Не найден исходник: '+m['path'])
    if plan.sections:
        cursor=0;seen=set()
        for section in plan.sections:
            a,b=section['start'],section['end'];span(a,b)
            if abs(a-cursor)>.035 or section['block_id'] in seen:raise ValueError('Повреждён порядок разборов.')
            cursor=b;seen.add(section['block_id'])
        if abs(cursor-plan.duration)>.035:raise ValueError('Неполная дорожка выпуска.')
        for item in [*plan.inserts,*plan.cards]:
            if not any(item.start>=s['start']-.001 and item.end<=s['end']+.035 for s in plan.sections):
                raise ValueError('Элемент пересекает границу разборов. Сократите его или перенесите целиком в один блок.')
    return plan


class EditHistory:
    def __init__(self,plan):
        self.plan=copy.deepcopy(plan);self.undo_stack=[];self.redo_stack=[]
    def replace(self,plan):
        validate_plan(plan)
        self.undo_stack.append(copy.deepcopy(self.plan));self.undo_stack=self.undo_stack[-50:]
        self.redo_stack.clear();self.plan=copy.deepcopy(plan)
    def undo(self):
        if not self.undo_stack: return False
        self.redo_stack.append(self.plan);self.plan=self.undo_stack.pop();return True
    def redo(self):
        if not self.redo_stack: return False
        self.undo_stack.append(self.plan);self.plan=self.redo_stack.pop();return True


def store_plan(project,index,plan):
    if plan.sections:
        from .episode import store_episode
        return store_episode(project,plan)
    validate_plan(plan)
    block=project.blocks[index]
    block.edit_plan=plan.to_dict();block.edit_key=project_edit_key(project,index)


def saved_plan(project,index):
    block=project.blocks[index]
    if block.edit_plan and block.edit_key==project_edit_key(project,index):
        return validate_plan(Plan.from_dict(copy.deepcopy(block.edit_plan)))
    return None
