"""Full-episode sources, speech-bound alpha graphics and edit persistence."""
import copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
from hockey_editor.model import Project,Block
from hockey_editor.timeline import Plan,Line,Card
from hockey_editor.framing import prepared_script,framing_cards,split_full_script,pair_matches
from hockey_editor.host_media import media_ranges,slice_media,analysis_source
from hockey_editor.episode import combine,assembly_project,store_episode,saved_episode
from hockey_editor.editing import validate_plan
from hockey_editor.media import run,probe
INTRO='Всем привет! Сегодня московское «Динамо» принимает «Адмирал», СКА сыграет с «Ладой», а ЦСКА встретится с «Торпедо». Дополнительные ставки публикую в телеграм-канале. Ссылка находится в описании. Переходим к разбору.'
OUTRO='Итак, повторю варианты. В матче Динамо — Адмирал беру «Адмирал» с форой плюс два. Во встрече СКА — Лада выбираю «Ладу» с форой плюс два. В матче ЦСКА — Торпедо мой основной вариант — «Торпедо» с форой плюс полторы. Дополнительные прогнозы публикую в телеграм-канале. Ссылка находится в описании. Подписывайтесь, ставьте лайк. Всем удачи и до встречи в следующем разборе!'
def project():
 p=Project(blocks=[Block(title=t,script='Мой выбор — '+bet,uid=str(i)) for i,(t,bet) in enumerate([('Динамо Москва — Адмирал','«Адмирал» с форой плюс два.'),('СКА — Лада','«Лада» с форой плюс два.'),('ЦСКА — Торпедо','«Торпедо» с форой плюс полторы шайбы.')])]);p.intro.script=INTRO;p.outro.script=OUTRO;p.assets={'telegram':'tg.mov','subscribe':'sub.mov'};p.full_video=True;return p
def lines(block):return [Line(t,i*3,(i+1)*3) for i,t in enumerate(prepared_script(block).splitlines())]
class V06Tests(unittest.TestCase):
 def test_intro_pairs_and_telegram_link(self):
  p=project();ls=lines(p.intro);cards,_=framing_cards(assembly_project(p),p.intro,ls,ls[-1].end)
  matches=[c for c in cards if c.title=='РАЗБОР МАТЧА'];self.assertEqual([c.text for c in matches],[b.title for b in p.blocks]);self.assertTrue(all(a.end<=b.start for a,b in zip(matches,matches[1:])))
  tg=next(c for c in cards if c.asset);self.assertEqual((tg.start,tg.end),(ls[tg.line].start,ls[tg.line].end));self.assertIn('Ссылка находится в описании',ls[tg.line].text);self.assertFalse(pair_matches('ЦСКА — Лада',p.blocks[1]))
 def test_outro_shared_forecasts_whole_subscription(self):
  p=project();ls=lines(p.outro);p.blocks[0].edit_plan={'cards':[{'title':'ПРОГНОЗ','text':'Адмирал\nФора (+2) · правка'}]}
  with patch('hockey_editor.framing.probe',return_value={'duration':4}):cards,_=framing_cards(assembly_project(p),p.outro,ls,ls[-1].end)
  bets=[c for c in cards if c.title=='ПРОГНОЗ'];self.assertEqual([c.forecast_id for c in bets],['0','1','2']);self.assertIn('правка',bets[0].text)
  sub=next(c for c in cards if c.title=='ПОДПИСКА');self.assertEqual(sub.end-sub.start,4);self.assertLessEqual(sub.end,ls[-1].end);self.assertTrue(all(c.title in ('ПРОГНОЗ','ТЕЛЕГРАМ','ПОДПИСКА') for c in cards))
  with patch('hockey_editor.framing.probe',return_value={'duration':30}):
   with self.assertRaisesRegex(ValueError,'длиннее'):framing_cards(assembly_project(p),p.outro,ls,ls[-1].end)
 def test_import_heading_not_statistics(self):
  text=INTRO+'\nДинамо Москва — Адмирал\nДва матча — две победы.\nМой выбор — «Адмирал» с форой плюс два.\nСКА — Лада\nСчёт — 3:2.\n'+OUTRO
  intro,blocks,outro=split_full_script(text);self.assertEqual(len(blocks),2);self.assertEqual(intro,INTRO);self.assertEqual(outro,OUTRO);self.assertIn('Два матча',blocks[0][1])
 def test_source_boundary_without_video_proxy(self):
  p=Project(host='first.mp4',hosts=['first.mp4','second.mp4']);p.settings.auto_rotate=False
  plan=Plan(0,10,[(3,7)],[Line('Фраза через стык',0,4)],[],[],[],4);parts=[{'path':'first.mp4','offset':0,'duration':5},{'path':'second.mp4','offset':5,'duration':5}]
  media=media_ranges(p,plan,parts,Path('.'),threading.Event(),print)
  self.assertEqual([(m['path'],m['start'],m['end']) for m in media],[('first.mp4',3,5),('second.mp4',0,2)]);self.assertEqual([(m['start'],m['end']) for m in slice_media(media,1,3)],[(4,5),(0,1)])
 def test_full_project_roundtrip(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);host=root/'host.mp4';host.touch();tg=root/'telegram.mov';tg.touch();p=project();p.host=str(host);p.hosts=[str(host),str(host)];p.assets={'telegram':str(tg)};runtime=assembly_project(p);plans=[]
   for i,b in enumerate(runtime.blocks):
    title='ПРОГНОЗ' if b.kind=='analysis' else 'ИНФОРМАЦИЯ';plans.append(Plan(i*5,i*5+4,[(0,4)],[Line(b.title,0,4)],[],[Card(0,4,title,'Текст')],[],4,0,[],[{'path':str(host),'start':0,'end':4,'rotation':0,'kind':'host'}]))
   merged=combine(runtime,plans);store_episode(p,merged);p.save(root/'saved.hockeyproj');loaded=Project.load(root/'saved.hockeyproj');restored=saved_episode(loaded)
   self.assertIsNotNone(restored);self.assertTrue(loaded.full_video);self.assertEqual(loaded.hosts,p.hosts);self.assertEqual(restored.media[0]['path'],str(host));self.assertEqual(loaded.intro.script,INTRO)
   loaded.hosts.append(str(tg));self.assertIsNone(saved_episode(loaded))
 def test_real_video_join_and_alpha(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);cancel=threading.Event()
   for name,color in [('one','blue'),('two','green')]:run(['-y','-f','lavfi','-i',f'color={color}:s=320x180:r=30:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-shortest',root/(name+'.mp4')])
   im=Image.new('RGBA',(320,180));im.paste((255,255,0,255),(120,25,200,155));im.save(root/'alpha.png');run(['-y','-loop','1','-i',root/'alpha.png','-t','2','-r','30','-c:v','qtrle','-pix_fmt','argb',root/'tg.mov'])
   p=Project(host=str(root/'one.mp4'),hosts=[str(root/'one.mp4'),str(root/'two.mp4')],blocks=[Block(script='Достаточно длинный текст сценария для проверки.')]);p.settings.auto_rotate=False;p.settings.zoom=False;p.settings.color=False;p.settings.denoise=False;p.settings.wobble=False;p.settings.animate_cards=False
   audio,duration,parts=analysis_source(p,root,cancel,print);self.assertTrue(str(audio).endswith('.wav'));self.assertEqual(duration,4)
   plan=Plan(0,4,[(0,4)],[Line('Канал и ссылка',0,1.5)],[],[Card(0,1.5,'ТЕЛЕГРАМ','Канал',0,str(root/'tg.mov'))],[],4,0,[],[{'path':str(root/'one.mp4'),'start':0,'end':2,'rotation':0,'kind':'host'},{'path':str(root/'two.mp4'),'start':0,'end':2,'rotation':0,'kind':'host'}])
   from hockey_editor.engine import Engine
   result=Engine(p,0,root/'cache',cancel).render(plan,root/'result.mp4',draft=True);self.assertAlmostEqual(probe(result)['duration'],4,delta=.1)
   for t,name in [(1,'before'),(3,'after')]:run(['-y','-ss',t,'-i',result,'-frames:v','1',root/(name+'.png')])
   before=np.array(Image.open(root/'before.png').convert('RGB'));after=np.array(Image.open(root/'after.png').convert('RGB'));self.assertGreater(before[170,60,0],150);self.assertGreater(before[100,500,2],200);self.assertGreater(after[100,500,1],80);self.assertLess(after[100,500,2],30)
   with self.assertRaisesRegex(ValueError,'ровно фразу'):
    broken=copy.deepcopy(plan);broken.cards[0].end=1;validate_plan(broken)
