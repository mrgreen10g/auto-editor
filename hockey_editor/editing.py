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
        if not c.text.strip(): raise ValueError('Плашка пуста. Удалите её или введите текст.')
    if not plan.keep or any(not all(math.isfinite(v) for v in (a,b)) or a<0 or b<=a for a,b in plan.keep):
        raise ValueError('Повреждена дорожка речи.')
    if abs(sum(b-a for a,b in plan.keep)-plan.duration)>.07:
        raise ValueError('Длительность речи не совпадает с дорожкой.')
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
    validate_plan(plan)
    block=project.blocks[index]
    block.edit_plan=plan.to_dict();block.edit_key=project_edit_key(project,index)


def saved_plan(project,index):
    block=project.blocks[index]
    if block.edit_plan and block.edit_key==project_edit_key(project,index):
        return validate_plan(Plan.from_dict(copy.deepcopy(block.edit_plan)))
    return None
