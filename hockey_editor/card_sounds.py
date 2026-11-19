"""Quiet synthesized accents. No samples, licenses, or voice gain automation."""
import hashlib,math,struct,wave

def create(plan,settings,cache):
 level=float(settings.card_sound_volume)
 if not math.isfinite(level):raise ValueError('Громкость анимаций должна быть от 0 до 100%.')
 if not settings.animate_cards or level<=0:return None
 starts=[]
 for card in sorted(plan.cards,key=lambda c:c.start):
  if card.visual and not card.asset and card.end-card.start>=1 and (not starts or card.start-starts[-1]>=1.2):starts.append(card.start)
 if not starts:return None
 rate=24000;level=min(100,level)/100
 key=hashlib.sha256(repr((starts,plan.duration,level)).encode()).hexdigest()[:16]
 path=cache/f'card-sounds-{key}.wav'
 if path.is_file():return path
 events=[round(t*rate) for t in starts];length=round(.14*rate)
 tone=[.10*level*math.sin(math.pi*i/length)**2*(.75*math.sin(2*math.pi*820*i/rate)+.25*math.sin(2*math.pi*1230*i/rate)) for i in range(length)]
 temp=path.with_suffix('.partial.wav')
 try:
  with wave.open(str(temp),'wb') as out:
   out.setparams((1,2,rate,0,'NONE','not compressed'))
   for offset in range(0,round(plan.duration*rate),rate):
    n=min(rate,round(plan.duration*rate)-offset);chunk=[0.]*n
    for event in events:
     a=max(offset,event);b=min(offset+n,event+length)
     for j in range(a,b):chunk[j-offset]+=tone[j-event]
    out.writeframes(struct.pack('<'+'h'*n,*(round(max(-1,min(1,v))*32767) for v in chunk)))
  temp.replace(path)
 finally:
  if temp.exists():temp.unlink()
 return path
