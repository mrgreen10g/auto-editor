import copy,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.timeline import Plan,Line,Card
from hockey_editor.editing import validate_plan
from hockey_editor.episode import trim_overlap,combine
from hockey_editor.preferences import presets,save_preset,apply_preset
from hockey_editor.script_input import clean_script,read_script
from hockey_editor.uzbek import parse_script,classify,events
from hockey_editor.uz_forecasts import features,match_forecasts
from hockey_editor.uz_speech import recap_cue,recognition_prompt,recording_key
from hockey_editor.uz_hockey_support import check_script,forecast_span
from hockey_editor.uz_hockey import numeric,prepare,framing_cards
from hockey_editor.team_names import football_identity,football_positions
from hockey_editor.football_names import NATIONAL
from test_uz_speech import segment
from test_uz_hockey import project as hockey_project

class UzbekUpdateTests(unittest.TestCase):
 def test_telegram_survives_short_and_removed_lines_at_join(self):
  p=Plan(0,3,[(0,3)],[Line('short',0,.1),Line('Telegram havola',.1,2),Line('end',2,3)],[],[Card(.1,2,'ТЕЛЕГРАМ','Telegram',1)],[],3)
  p.edit_baseline={'cards':[vars(copy.copy(p.cards[0]))]}
  for previous,expected in [(0,1),(.1,0)]:
   out=trim_overlap(p,previous)
   self.assertEqual(out.cards[0].line,expected)
   self.assertEqual(out.edit_baseline['cards'][0]['line'],expected)
   validate_plan(out,False)
  project=Project(blocks=[Block(title='a'),Block(title='b')])
  q=Plan(3,5,[(0,2)],[Line('second',0,2)],[],[],[],2)
  validate_plan(combine(project,[p,q]),False)

 def test_presets_visible_across_profiles_without_switching_sport(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'prefs.json';ru=Project();ru.settings.noise_reduction=17
   save_preset(ru,'Voice',path)
   uz=Project(profile='uz_hockey',blocks=[Block(language='uz',sport='hockey',script='unchanged')])
   apply_preset(uz,'Voice',path)
   self.assertEqual(uz.settings.noise_reduction,17);self.assertEqual(uz.profile,'uz_hockey');self.assertEqual(uz.blocks[0].script,'unchanged')
   data=json.loads(path.read_text());data['ru_hockey']={'presets':{'Voice':{'settings':{'noise_reduction':8}}}};path.write_text(json.dumps(data))
   self.assertEqual(len(presets('uz_combat',path)),2)
   apply_preset(uz,'Voice [ru_hockey]',path);self.assertEqual(uz.settings.noise_reduction,8)

 def test_docx_cleanup_numbered_pairs_and_new_picks(self):
  text="KIRISH | 0:00–0:30\n[САРДОР]\nBugun Germaniya va Serbiya haqida gapiramiz.\n1. GERMANIYA — SERBIYA | 0:30–2:00\nGermaniya uyda kuchli o'ynaydi.\nTanlovim — Germaniya g'alabasi.\nYAKUN\nDemak bugungi tanlovim Germaniya g'alabasi.\n[МОНТАЖЁРУ: English note]\nhttps://example.org\n:chatgpt-content-reference{index=1}"
  import xml.sax.saxutils as xml
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'script.docx'
   with zipfile.ZipFile(path,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'+''.join('<w:p><w:r><w:t>'+xml.escape(l)+'</w:t></w:r></w:p>' for l in text.splitlines())+'</w:document>')
   a,bs,z=parse_script(read_script(path))
  self.assertEqual(bs[0].title,'Germaniya — Serbiya')
  for bad in ['САРДОР','English note','http','chatgpt']:self.assertNotIn(bad,a.script+bs[0].script+z.script)
  for text in ["Tanlovim — Germaniya g'alabasi.","Ikkinchi tanlovim — Portugaliya yutqazmaydi va total 1,5 dan ko'p.","Uchinchi tanlovim — Norvegiya X2 va total 1,5 dan ko'p."]:
   self.assertEqual(classify(text)[0],'ПРОГНОЗ')
  self.assertTrue(features("Portugaliya yutqazmaydi va total bir butun beshdan ko'p")['double'])
  self.assertNotEqual(classify('Goncalo Ramos goli 1:0 g‘alaba berdi.')[0],'УСЛОВИЯ ПРОГНОЗА')

 def test_national_catalog_and_player_prompt_have_no_results(self):
  self.assertEqual(len(NATIONAL),56)
  from hockey_editor.team_names import football_names
  self.assertEqual(football_names('Northern Ireland — Denmark'),['Shimoliy Irlandiya','Daniya'])
  from hockey_editor.football_players import PLAYERS,mentioned_names
  self.assertEqual(len(PLAYERS),72)
  self.assertIn('Gonçalo Ramos',mentioned_names('Goncalo Ramosning goli'))
  for alias,name in [('Germany','Germaniya'),('Wales','Uels'),('Norway','Norvegiya'),('Сербия','Serbiya')]:
   self.assertEqual(football_identity(alias),name);self.assertTrue(football_positions(name,name+'ning hujumi'))
  p=Project(profile='uz_football',blocks=[Block(title='Uels — Norvegiya',script='Erling Haaland 16 gol. [МОНТАЖЁРУ: Wrong Person 99]')])
  prompt=recognition_prompt(p)
  self.assertIn('Erling Haaland',prompt);self.assertNotIn('Wrong Person',prompt);self.assertNotIn('16',prompt);self.assertNotIn('99',prompt)
  with tempfile.NamedTemporaryFile() as h:
   p.host=h.name;first=recording_key(p);p.blocks[0].script+=' Martin Odegaard.';self.assertNotEqual(recording_key(p),first)

 def test_football_archives_prioritize_fixture_then_related_archive(self):
  a=MatchSource('a','Germaniya','Niderlandiya',sport='football');b=MatchSource('b','Germaniya','Gretsiya',sport='football');c=MatchSource('c','Norvegiya','Uels',sport='football')
  block=Block(title='Germaniya — Serbiya',language='uz',match_ids=[a.id,b.id,c.id],script="Germaniya Niderlandiyaga qarshi kuchli hujum qiladi.\nGermaniya Gretsiyaga qarshi o'yin o'tkazdi.\nGermaniya Serbiyaga qarshi maydonda hujum qiladi.")
  found=events(block,[a,b,c]);self.assertEqual([e.source_id for e in found[:2]],[a.id,b.id]);self.assertIn(found[-1].source_id,[a.id,b.id]);self.assertTrue(all(e.score is None for e in found))

 def test_football_future_pick_and_merged_recap(self):
  bs=[Block(title='Germaniya — Serbiya'),Block(title='Daniya — Portugaliya')]
  refs={bs[0].uid:'Germaniya g‘alabasi',bs[1].uid:'Portugaliya X2'}
  data=[segment(70,78,'Shu sababli Germaniya g‘alabasi kutilmoqda.')]
  self.assertFalse(match_forecasts(data,0,100,[bs[0]],refs,False)[0]['needs_review'])
  data=[segment(0,10,'Germaniya Serbiya Germaniya qalabasi, Daniya Portugaliya Portugaliya X2 variant.')]
  found=match_forecasts(data,0,11,bs,refs);self.assertEqual(len(found),2);self.assertLessEqual(found[0]['end'],found[1]['start'])
  self.assertTrue(recap_cue('Deming bugungi uchta o‘yin bo‘yicha tanlovimiz'))
  self.assertFalse(recap_cue('Xullasikaro uchinchi o‘yin tanlovimiz total besh'))

 def test_decoder_uses_vocabulary_beam_search_and_cache(self):
  from types import SimpleNamespace
  import threading
  from hockey_editor.uz_speech import transcribe
  from unittest.mock import MagicMock
  decoder=MagicMock()
  decoder.transcribe.return_value=([SimpleNamespace(text='Erling Haaland hujum qiladi.',end=2,words=[SimpleNamespace(word='Haaland',start=0,end=2,probability=.9)])],None)
  constructor=MagicMock(return_value=decoder)
  with tempfile.TemporaryDirectory() as d:
   host=Path(d)/'host';host.touch();p=Project(host=str(host),profile='uz_football',blocks=[Block(title='Uels — Norvegiya',script='Erling Haaland hujum qiladi.')])
   with patch.dict('sys.modules',{'faster_whisper':SimpleNamespace(WhisperModel=constructor)}), patch('hockey_editor.uz_speech.model_path',return_value=Path(d)), patch('hockey_editor.host_media.analysis_source',return_value=(host,None,None)), patch('hockey_editor.uz_speech.run'), patch('hockey_editor.uz_refine.refine',side_effect=lambda model,audio,result,*args:result):
    first=transcribe(p,d,threading.Event(),lambda x:None)
    self.assertEqual(transcribe(p,d,threading.Event(),lambda x:None),first)
   self.assertEqual(decoder.transcribe.call_count,1)
   args=decoder.transcribe.call_args.kwargs
   self.assertEqual(args['beam_size'],5);self.assertIn('Erling Haaland',args['initial_prompt'])

 def test_mismatched_hockey_script_rejected_only_on_positive_evidence(self):
  p=hockey_project()
  data=[segment(i*20,(i+1)*20,'Colorado Los Angeles Philadelphia Pittsburgh o‘yini.') for i in range(4)]
  with self.assertRaisesRegex(ValueError,'Видео и сценарий'):check_script(p,data)
  check_script(p,[segment(0,100,'No recognizable names')])

 def test_noisy_hockey_numbers_and_archive_without_explicit_match(self):
  from hockey_editor.uz_hockey import events as hockey_events
  self.assertIn('5 dan',numeric('total beshtadan ko‘p'))
  p=hockey_project();b=p.blocks[0]
  ss=[segment(70,80,'Taronto asosiy vaqti yutqazmini va total to‘riyamtidan ko‘p degan varianti qildik.')]
  pick=forecast_span(b,ss,0,100);self.assertIsNotNone(pick);self.assertIn('1X',pick[3]);self.assertTrue(pick[4])
  source=MatchSource('a','Toronto','Montreal');b.match_ids=[source.id];b.asr_lines=[dict(text='Bu safar maydonda hujum ancha faol bo‘ladi.',start=0,end=8)]
  found=hockey_events(b,[source]);self.assertTrue(found);self.assertEqual(found[0].phrase,b.asr_lines[0]['text'])

if __name__=='__main__':unittest.main()
