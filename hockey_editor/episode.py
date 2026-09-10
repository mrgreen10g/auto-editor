"""Ordered analyses from one recording, one editable timeline and one music bed."""
import copy
import hashlib
import json
from pathlib import Path
from .engine import Engine
from .editing import project_edit_key,store_plan,saved_plan,validate_plan
from .timeline import Plan,Card,frame


def episode_key(project):
    data=[(b.uid,project_edit_key(project,i),b.edit_plan) for i,b in enumerate(project.blocks)]
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def saved_episode(project):
    if project.episode_plan and project.episode_key==episode_key(project):
        return validate_plan(Plan.from_dict(copy.deepcopy(project.episode_plan)))
    return None


def trim_overlap(plan,previous_end):
    """Remove duplicated source frames from padding, without losing spoken audio."""
    p=copy.deepcopy(plan);removed=0;keep=[]
    for a,b in p.keep:
        cut=min(b,max(a,previous_end-p.source_start))
        removed+=cut-a
        if b>cut:keep.append((frame(cut),b))
    if removed>1.0:raise ValueError('Разборы пересекаются в записи. Проверьте порядок сценариев и соответствие текстов речи.')
    if not keep:raise ValueError('Разбор целиком пересекается с предыдущим.')
    p.keep=keep;p.duration=frame(sum(b-a for a,b in keep))
    for name in ('lines','inserts','cards'):
        output=[]
        for item in getattr(p,name):
            if item.end<=removed:continue
            trimmed=max(0,removed-item.start)
            item.start=frame(max(0,item.start-removed));item.end=frame(item.end-removed)
            if name=='inserts':item.source_in+=trimmed
            if item.end-item.start>=.15:output.append(item)
        setattr(p,name,output)
    return p


def source_time(plan,output_time):
    cursor=0
    for a,b in plan.keep:
        if output_time<=cursor+b-a:return plan.source_start+a+output_time-cursor
        cursor+=b-a
    return plan.source_start+plan.keep[-1][1]


def crop_padding_at_next_speech(plan,next_plan):
    p=copy.deepcopy(plan)
    last=p.source_start+p.keep[-1][1]
    if next_plan.source_start>=last or not next_plan.lines:return p
    boundary=frame(source_time(next_plan,next_plan.lines[0].start))
    if not last-1<=boundary<last:return p
    limit=boundary-p.source_start
    p.keep=[(a,min(b,limit)) for a,b in p.keep if a<limit]
    p.duration=frame(sum(b-a for a,b in p.keep));p.source_end=boundary
    for name in ('lines','inserts','cards'):
        values=[]
        for item in getattr(p,name):
            item.end=min(item.end,p.duration)
            if item.end-item.start>=.15:values.append(item)
        setattr(p,name,values)
    return p


def combine(project,plans):
    if len(plans)!=len(project.blocks):raise ValueError('Не все разборы подготовлены.')
    plans=[crop_padding_at_next_speech(p,plans[i+1]) if i+1<len(plans) else copy.deepcopy(p) for i,p in enumerate(plans)]
    keep=[];lines=[];inserts=[];cards=[];warnings=[];sections=[];cursor=0;previous=0
    for block,original in zip(project.blocks,plans):
        p=trim_overlap(original,previous)
        if not p.lines:raise ValueError('В разборе нет речи: '+block.title)
        line_start=len(lines)
        absolute=[(frame(p.source_start+a),frame(p.source_start+b)) for a,b in p.keep]
        previous=absolute[-1][1];keep+=absolute
        sections.append({'block_id':block.uid,'title':block.title,'start':cursor,'end':frame(cursor+p.duration),
                         'source_start':p.source_start,'source_end':p.source_end,'keep':p.keep,
                         'line_start':line_start,'line_count':len(p.lines),'rotation':p.rotation})
        for name,target in (('lines',lines),('inserts',inserts),('cards',cards)):
            for item in getattr(p,name):
                item=copy.deepcopy(item);item.start=frame(item.start+cursor);item.end=frame(item.end+cursor)
                if name=='cards' and item.line>=0:item.line+=line_start
                target.append(item)
        if cursor>0:cards.append(Card(cursor,frame(cursor+min(.8,p.duration)),'СМЕНА МАТЧА',block.title))
        warnings.extend(block.title+': '+v for v in p.warnings)
        cursor=frame(cursor+p.duration)
    result=Plan(0,max(p.source_end for p in plans),keep,lines,inserts,cards,warnings,cursor,plans[0].rotation,sections)
    return validate_plan(result)


def store_episode(project,plan):
    validate_plan(plan)
    if [s['block_id'] for s in plan.sections]!=[b.uid for b in project.blocks]:
        raise ValueError('Состав или порядок разборов изменился. Определите тайминги всего выпуска заново.')
    for i,s in enumerate(plan.sections):
        def local(items,cards=False):
            result=[]
            for value in items:
                if value.start<s['start']-.001 or value.end>s['end']+.035:continue
                if cards and value.title=='СМЕНА МАТЧА':continue
                v=copy.deepcopy(value);v.start=frame(v.start-s['start']);v.end=frame(v.end-s['start'])
                if cards and v.line>=0:v.line-=s['line_start']
                result.append(v)
            return result
        lines=copy.deepcopy(plan.lines[s['line_start']:s['line_start']+s['line_count']])
        for l in lines:l.start=frame(l.start-s['start']);l.end=frame(l.end-s['start'])
        part=Plan(s['source_start'],s['source_end'],s['keep'],lines,local(plan.inserts),local(plan.cards,True),[],
                  frame(s['end']-s['start']),s['rotation'])
        store_plan(project,i,part)
    project.episode_plan=plan.to_dict();project.episode_key=episode_key(project)


class EpisodeEngine(Engine):
    def __init__(self,project,index,cache,cancel,log=lambda _:None):
        super().__init__(project,0,cache,cancel,log)

    def validate_all(self):
        if not 1<=len(self.project.blocks)<=4:raise ValueError('В выпуске поддерживается от 1 до 4 разборов.')
        for i,b in enumerate(self.project.blocks):
            try:self.project.validate(i)
            except ValueError as error:raise ValueError(b.title+': '+str(error)) from error

    def analyze(self):
        self.validate_all();self.check()
        restored=saved_episode(self.project)
        if restored:
            self.log('Использую общую дорожку с сохранёнными правками.');return restored
        plans=[];previous=0
        for i,block in enumerate(self.project.blocks):
            self.check();self.log(f'Разбор {i+1}/{len(self.project.blocks)}: {block.title}')
            engine=Engine(self.project,i,self.cache/block.uid,self.cancel,self.log)
            p=engine.analyze(source_floor=max(0,previous-1))
            if p.source_start<previous-1.01:
                raise ValueError('Порядок разборов не совпадает с записью: '+block.title)
            plans.append(p);previous=p.source_end
        plan=combine(self.project,plans);store_episode(self.project,plan);self.save_plan(plan)
        self.log(f'Выпуск готов к проверке: {len(plans)} разбора, {plan.duration:.1f} с.')
        return plan

    def render(self,plan,target,draft=False):
        self.validate_all()
        return super().render(plan,target,draft)
