import unittest,tempfile,threading
from pathlib import Path
from unittest.mock import Mock,patch
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.profiles import apply_profile,kit_path
from hockey_editor.folder_import import parse_episode,pair_key
from hockey_editor.ru_combat import classify,confidence,named,pair_heading,events
from hockey_editor.timeline import Line,Card,placements

SCRIPT='''Всем привет, сегодня несколько боёв.
Лонер Кавана встречается с Рамазаном Темировым.
Пётр Ян против Мераба Двалишвили в главном бою вечера.
Александр Волкановски встретит Мовсара Евлоева.
Переходим к разбору.
Начинаем с Лонера Каваны и Рамазана Темирова.
Темиров давит и использует борьбу. Кавана работает на дистанции.
Основной прогноз — бой не пройдёт полную дистанцию.
Теперь Пётр Ян против Мераба Двалишвили.
Мераб работает у сетки. Ян отвечает ударами.
Основной прогноз — победа Петра Яна.
И последний бой — Александр Волкановски против Мовсара Евлоева.
Мовсар использует борьбу. Волкановски контролирует дистанцию.
Основной прогноз — бой пройдёт полную дистанцию.
Повторю три основных прогноза.
Лонер Кавана — Рамазан Темиров: бой не пройдёт полную дистанцию.
Пётр Ян — Мераб Двалишвили: победа Петра Яна.
Александр Волкановски — Мовсар Евлоев: бой пройдёт полную дистанцию.
Пишите в комментариях.
'''
SINGLE='''Умар Нурмагомедов — Сон Ядун
Всем привет, обсудим этот бой.
Переходим к разбору.
Умар работает ногами и контролирует дистанцию.
Основная ставка — тотал больше 3,5 раунда.
Более рискованный вариант — победа Умара решением судей.
Итак, мой выбор — ТБ(3,5) раунда.
До встречи!
'''
SHORT='Пётр Ян готовится к бою. Его соперник Мераб Двалишвили.\nЯн контролирует дистанцию.\nМой выбор — тотал больше 2,5 раунда.'

class RussianCombatTests(unittest.TestCase):
 def test_spoken_structure_separates_hook_bouts_and_recap(self):
  for profile in ('ru_combat','ru_combat_shorts'):
   intro,blocks,outro=parse_episode(SCRIPT,profile)
   self.assertEqual(len(blocks),3)
   self.assertTrue(intro.script.startswith('Всем привет'))
   self.assertTrue(outro.script.startswith('Повторю'))
   self.assertEqual([b.forecast for b in blocks],['Бой не пройдёт полную дистанцию','Победа Петра Яна','Бой пройдёт полную дистанцию'])
   self.assertTrue(all(b.script.startswith(('Начинаем','Теперь','И последний')) for b in blocks))
   self.assertNotIn('Повторю',blocks[-1].script)
 def test_metadata_title_and_unheaded_short(self):
  intro,blocks,outro=parse_episode(SINGLE,'ru_combat')
  self.assertTrue(intro.script.startswith('Всем привет'));self.assertTrue(blocks[0].script.startswith('Умар работает'))
  self.assertEqual(blocks[0].forecast,'Тотал больше 3,5 раунда')
  self.assertTrue(outro.script.startswith('Итак'))
  intro,blocks,outro=parse_episode(SHORT,'ru_combat_shorts')
  self.assertFalse(intro.script);self.assertEqual(len(blocks),1);self.assertEqual(blocks[0].script,SHORT)
 def test_unlimited_markers_and_folder_hints(self):
  text='Всем привет.\n'+'\n'.join(f'Разбор{i} Пётр Ян — Мераб Двалишвили\nОсновной прогноз — победа Петра Яна.' for i in range(1,12))
  for profile in ('ru_combat','ru_combat_shorts'):
   _,blocks,_=parse_episode(text,profile);self.assertEqual(len(blocks),11)
   self.assertTrue(all('Разбор' not in b.script and 'Разбор' not in b.title for b in blocks))
   _,blocks,_=parse_episode('Альфа — Бета\nАльфа контролирует дистанцию.',profile,['Альфа — Бета'])
   self.assertEqual(blocks[0].title,'Альфа — Бета')
 def test_names_declension_and_identity(self):
  from hockey_editor.fighters import same_fighter,canonical_name
  from hockey_editor.fighter_russian import NAMES
  self.assertGreater(len(NAMES),200)
  from hockey_editor.fighter_aliases import RANKED_SNAPSHOT
  from hockey_editor.fighters import identity
  self.assertFalse(set(map(identity,RANKED_SNAPSHOT))-set(map(identity,NAMES)))
  for english,russian in NAMES.items():
   self.assertTrue(same_fighter(english,russian),(english,russian))
   self.assertEqual(canonical_name(english,'ru'),russian)
  self.assertEqual(pair_heading('Начинаем с Лонера Каваны и Рамазана Темирова.'),'Лонер Кавана — Рамазан Темиров')
  self.assertEqual(named(['Пётр Ян','Мераб Двалишвили'],'Петра Яна'),['Пётр Ян'])
  self.assertFalse(same_fighter('Умар Нурмагомедов','Хабиб Нурмагомедов'))
  self.assertEqual(pair_key('Пётр Ян — Мераб Двалишвили','ru_combat'),pair_key('Petr Yan — Merab Dvalishvili','ru_combat'))
 def test_recap_binds_each_bet_and_rejects_negation_change(self):
  from hockey_editor.ru_combat import framing_cards
  intro,blocks,outro=parse_episode(SCRIPT,'ru_combat');p=Project(profile='ru_combat',intro=intro,blocks=blocks,outro=outro)
  lines=[Line(s,i*5,(i+1)*5,recognized=s) for i,s in enumerate(outro.script.splitlines())]
  cards,_=framing_cards(p,outro,lines,30)
  self.assertEqual([c.forecast_id for c in cards],[b.uid for b in blocks])
  for c in cards:self.assertFalse(confidence(c,lines[c.line],outro,p))
  c=cards[0];l=lines[c.line];l.recognized=l.recognized.replace('не пройдёт','пройдёт')
  self.assertTrue(confidence(c,l,outro,p))
 def test_conditions_and_total_conflicts(self):
  b=Block(title='Пётр Ян — Мераб Двалишвили',sport='combat',language='ru');p=Project(profile='ru_combat',blocks=[b])
  c=Card(0,5,'ПРОГНОЗ','Тотал больше 3,5 раунда')
  for heard,ok in [('Мой выбор — тотал больше трех с половиной раундов.',True),('Мой выбор — тотал меньше 3,5 раунда.',False),('Мой выбор — тотал больше 2,5 раунда.',False)]:
   self.assertEqual(not bool(confidence(c,Line('Мой выбор — ТБ(3,5) раунда.',0,5,recognized=heard),b,p)),ok)
  title,body=classify('Если будет пять раундов, мой выбор — тотал больше 3,5 раунда.')
  self.assertEqual(title,'ПРОГНОЗ');self.assertTrue(body.startswith('Если'))
  self.assertEqual(classify('Более рискованный вариант — победа Яна решением.')[0],'УСЛОВИЯ ПРОГНОЗА')
 def test_shared_illustrations_are_optional(self):
  s=MatchSource('fight.mp4','','',sport='combat',fighter='Umar Nurmagomedov')
  b=Block(title='Умар Нурмагомедов — Сон Ядун',sport='combat',language='ru',match_ids=[s.id],script='Начнем с Умара. Он контролирует дистанцию. Основная ставка — тотал больше 3,5 раунда.')
  found=events(b,[s]);self.assertEqual(len(found),1);self.assertEqual(found[0].source_id,s.id)
  from hockey_editor.goals import propose,unresolved
  b.events=propose(found,{},[s]);self.assertFalse(unresolved(b));self.assertTrue(b.events[0].skipped)
 def test_profiles_and_graphics(self):
  from hockey_editor.graphics import card_image
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   for profile in ('ru_combat','ru_combat_shorts'):
    p=Project();apply_profile(p,profile)
    self.assertTrue(all(b.language=='ru' and b.sport=='combat' for b in [p.intro,*p.blocks,p.outro]))
    self.assertNotEqual(kit_path(profile),kit_path(profile.replace('ru_','uz_')))
    f=Path(folder)/(profile+'.png')
    for kind,text in [('РАЗБОР МАТЧА','Лонер Кавана — Рамазан Темиров'),('ПРОГНОЗ','Бой не пройдёт полную дистанцию'),('СТАТИСТИКА','Защита от тейкдаунов — 75 процентов')]:
     x,y=card_image(Card(0,5,kind,text),f,{},profile)
     with Image.open(f) as im:
      w,h=(720,1280) if profile.endswith('_shorts') else (1280,720)
      self.assertLessEqual(x+im.width,w);self.assertLessEqual(y+im.height,h)
 def test_mobile_creation_and_fighter_sources(self):
  from test_mini_app import app_fixture
  from hockey_editor.mini_bridge import Bridge
  from hockey_editor.mobile_inputs import Inputs
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);app=app_fixture(root);bridge=Bridge(app);inputs=Inputs(bridge,root/'catalog.json')
   for profile in ('ru_combat','ru_combat_shorts'):
    ident=inputs.create(dict(parent=str(root),name=profile,profile=profile,request=profile))['id']
    inputs.script(dict(id=ident,text=SCRIPT));draft=inputs.load(ident)
    host=root/(profile+'.mp4');host.write_bytes(b'host')
    draft['files'].append(dict(id='host',role='host',block='',name=host.name,status='ready',path=str(host),home='',away='',fighter=''))
    draft['files'].append(dict(id='fight',role='match',block=draft['blocks'][0]['uid'],name=host.name,status='ready',path=str(host),home='',away='',fighter="Lone'er Kavanagh"))
    inputs.save(draft);app.restore_plan=Mock();app.status.set=Mock()
    result=inputs.activate(dict(id=ident,revision=bridge.revision()));loaded=Project.load(result['project'])
    self.assertEqual(loaded.profile,profile);self.assertEqual(len(loaded.blocks),3)
    self.assertEqual(loaded.matches[0].sport,'combat');self.assertEqual(loaded.matches[0].fighter,"Lone'er Kavanagh")

 def test_episode_assembly_with_spoken_boundaries(self):
  from hockey_editor.episode import EpisodeEngine
  from hockey_editor.media import run
  from hockey_editor.review import pending
  from test_ru_speech import segment
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);speech=[];cursor=1
   for row in SCRIPT.strip().splitlines():
    s=segment(cursor,row);speech.append(s);cursor=s['end']+.2
   host=root/'host.mp4'
   run(['-y','-f','lavfi','-i',f'color=c=blue:s=180x320:r=30:d={cursor+1}','-f','lavfi','-i',f'sine=f=220:r=48000:d={cursor+1}','-t',cursor+1,'-c:v','libx264','-preset','ultrafast','-c:a','aac',host])
   disclaimer=root/'disclaimer.mp4'
   run(['-y','-f','lavfi','-i','color=c=black:s=320x180:r=30:d=1','-c:v','libx264',disclaimer])
   for profile in ('ru_combat','ru_combat_shorts'):
    p=Project();apply_profile(p,profile);p.full_video=True
    p.intro,p.blocks,p.outro=parse_episode(SCRIPT,profile)
    p.host=str(host);p.hosts=[str(host)];p.assets={'disclaimer':str(disclaimer)}
    p.settings.auto_rotate=False;p.settings.cut_pauses=False;p.settings.transitions=False
    with patch('hockey_editor.ru_speech.transcribe',return_value=speech):
     plan=EpisodeEngine(p,0,root/profile,threading.Event()).analyze()
    self.assertEqual(len([s for s in plan.sections if s['kind']=='analysis']),3)
    self.assertEqual({c.forecast_id for c in plan.cards if c.title=='ПРОГНОЗ'}, {b.uid for b in p.blocks})
    self.assertFalse(pending(plan))
    self.assertGreater(plan.duration,20)
