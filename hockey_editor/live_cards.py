"""Text overlays composited onto a clean preview, using the export artwork."""
import copy,hashlib,json,math
from pathlib import Path
from PIL import Image
from .graphics import card_image
from .timeline import game_transitions


def base_plan(plan):
    result=copy.deepcopy(plan);result.cards=[c for c in result.cards if c.asset]
    return result


def base_key(plan):
    data=base_plan(plan).to_dict()
    # These annotations don't alter video or audio.
    for key in ('review_items','edit_baseline','input_key','warnings','lines'):data.pop(key,None)
    for c in data['cards']:
        for key in ('review_id','review_reason','forecast_id','line'):c.pop(key,None)
    return json.dumps(data,sort_keys=True,ensure_ascii=False)


class LiveCards:
    def __init__(self,project,cache):
        self.project=project;self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        self.images={}

    def artwork(self,card):
        key=(card.title,card.text)
        if key not in self.images:
            filename=self.cache/(hashlib.sha256(repr(key).encode()).hexdigest()+'.png')
            x,y=card_image(card,filename,self.project.team_logos,self.project.profile)
            with Image.open(filename) as source:im=source.convert('RGBA')
            self.images[key]=(im,x,y)
            if len(self.images)>128:self.images.pop(next(iter(self.images)))
        return self.images[key]

    def compose(self,source,t,plan):
        result=source.convert('RGBA');sx=result.width/1280;sy=result.height/720;s=self.project.settings
        for i,c in enumerate(plan.cards):
            if c.asset or c.title in ('АРХИВНЫЕ КАДРЫ','КАДРЫ МАТЧА') or not c.start<=t<c.end:continue
            if c.title=='РАЗБОР МАТЧА' and any(v.start<=t<=v.end+tail for v,tail,_,_ in game_transitions(plan)):continue
            image,x,y=self.artwork(c);elapsed=t-c.start;left=c.end-t
            divider=c.title in ('СМЕНА МАТЧА','ИТОГИ ВЫПУСКА');edge=min(.25,(c.end-c.start)/3)
            animate=(s.transitions if divider else s.animate_cards) and c.title!='ПОДПИСКА'
            image=image.resize((max(1,round(image.width*sx)),max(1,round(image.height*sy))),Image.Resampling.BILINEAR)
            if s.wobble and not divider and c.title!='ПОДПИСКА':
                image=image.rotate(-.2*math.sin(2*math.pi*elapsed/4+i),resample=Image.Resampling.BICUBIC)
                x+=3*math.sin(2*math.pi*elapsed/3.7+i);y+=2*math.sin(2*math.pi*elapsed/4.3+i)
            if animate:
                opacity=min(1,elapsed/edge,left/edge)
                image.putalpha(image.getchannel('A').point(lambda v:round(v*opacity)))
                if divider:x+=1280*max(0,1-elapsed/edge)**2
                else:y+=16*max(0,1-elapsed/edge)**2+16*max(0,1-left/edge)**2
            result.alpha_composite(image,(round(x*sx),round(y*sy)))
        return result.convert('RGB')
