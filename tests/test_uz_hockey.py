import copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from hockey_editor.model import Project,Block,MatchSource,EventRequest,EventSelection
from hockey_editor.uz_hockey import parse_script,clean_script,bet,classify,prepare,events,framing_cards,forecast_conflict
from hockey_editor.hockey_names import ALIASES,KHL,identity,pair_in
from hockey_editor.profiles import apply_profile,kit_path
from hockey_editor.timeline import Line,Card
from hockey_editor.goals import source_signature
from hockey_editor.episode import EpisodeEngine
from hockey_editor.media import run
from test_uz_speech import segment

SCRIPT='''NHL | LONG SSENARIY
TORONTO MAPLE LEAFS — MONTREAL CANADIENS
BOSTON BRUINS — NEW YORK RANGERS
KIRISH | 0:00–1:00
Assalomu alaykum. Toronto Montreal va Boston Rangers o'yinlarini tahlil qilamiz. Boshladik!
[МОНТАЖЁРУ:
TORONTO — BOSTON
TOTAL 9 DAN KO'P
https://www.youtube.com/watch?v=ignored
]
1. TORONTO MAPLE LEAFS — MONTREAL CANADIENS | 1:00–4:00
Birinchi uchrashuv Toronto Maple Leafs va Montreal Canadiens.
Toronto uyda hujumda kuchli va raqibga katta bosim beradi.
Mening tanlovim — Toronto 1X va total 4,5 dan ko'p.
2. BOSTON BRUINS — NEW YORK RANGERS | 4:00–7:00
Ikkinchi uchrashuv Boston Bruins va New York Rangers.
Boston uyda hujumda kuchli va raqibga katta bosim beradi.
Mening tanlovim — total 5 dan ko'p.
YAKUN | 7:00–8:00
Xullas do'stlar, bugungi tanlovlarni takrorlaymiz.
Toronto — Montreal:
TORONTO 1X + TOTAL 4,5 DAN KO'P.
Boston — Rangers:
TOTAL 5 DAN KO'P.
Video yoqqan bo'lsa layk bosing. Keyingi videoda ko'rishguncha!'''

def project(host=''):
    a,b,z=parse_script(SCRIPT)
    return Project(host=host,profile='uz_hockey',intro=a,blocks=b,outro=z,full_video=True)

class UzbekHockeyTests(unittest.TestCase):
    def test_import_ignores_index_notes_urls_and_citation_tokens(self):
        p=project();self.assertEqual(len(p.blocks),2)
        text='\n'.join(b.script for b in [p.intro,*p.blocks,p.outro])
        for forbidden in ('youtube','МОНТАЖ','TOTAL 9','1:00'):self.assertNotIn(forbidden,text)
        self.assertEqual(clean_script('Toronto hujum qiladi. :chatgpt-content-reference{index="2"}\nРусская заметка\nhttps://example.com'),'Toronto hujum qiladi.')
        self.assertIn('4,5',p.blocks[0].forecast);self.assertIn('Total: 5',p.blocks[1].forecast)
        self.assertTrue(all(b.language=='uz' and b.sport=='hockey' for b in [p.intro,*p.blocks,p.outro]))

    def test_profile_roundtrip_multiple_archives_and_separate_settings(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.touch();p=project(str(host))
            p.matches=[MatchSource(str(host),'Toronto','Montreal'),MatchSource(str(host),'Toronto','Boston')]
            p.blocks[0].match_ids=[m.id for m in p.matches];p.validate(0)
            p.save(Path(d)/'project.hockeyproj');restored=Project.load(Path(d)/'project.hockeyproj')
            self.assertEqual(restored.profile,'uz_hockey');self.assertEqual(len(restored.blocks[0].match_ids),2)
            self.assertNotEqual(kit_path('uz_hockey'),kit_path('ru_hockey'));self.assertNotEqual(kit_path('uz_hockey'),kit_path('uz_football'))
            apply_profile(p,'ru_hockey');apply_profile(p,'uz_hockey')
            self.assertTrue(all(m.sport=='hockey' for m in p.matches))
            self.assertTrue(all(b.sport=='hockey' for b in p.blocks))

    def test_all_clubs_latin_cyrillic_suffixes_and_ambiguous_cities(self):
        from hockey_editor.nhl import NHL
        self.assertEqual(len(NHL),32);self.assertEqual(len(KHL),24)
        for club,aliases in ALIASES.items():
            self.assertEqual(identity(aliases[0]),club)
        for value,want in [('Torontoning','Toronto Maple Leafs'),('Vankuverga','Vancouver Canucks'),('NY Rangers','New York Rangers'),('Nyu York Aylanders','New York Islanders'),('СКА','СКА'),('CSKA','ЦСКА'),('Dinamo Minsk','Динамо Минск'),('Salavat Yulayev','Салават Юлаев'),('HC Sibir Novosibirsk','Сибирь')]:self.assertEqual(identity(value),want,value)
        for value in ('New York','Dinamo','Moskva','Toronto Boston'):self.assertIsNone(identity(value),value)
        self.assertTrue(pair_in('Torpedo — Spartak','Torpedoning raqibi Spartak.'))

    def test_hockey_markets_preserve_scope_and_direction(self):
        self.assertEqual(bet("Toronto 1X + TOTAL 4,5 DAN KO'P."),'Toronto Maple Leafs 1X\nTotal: 4,5 dan ko‘p')
        self.assertIn('Asosiy vaqt',bet("Asosiy vaqt ichida Vegas g'alabasini tanlayman."))
        self.assertIn('OT va bullitlar bilan',bet("SKA g'alabasi, overtaym va bullitlar bilan."))
        self.assertIn('Faqat overtaymda',bet("SKA g'alabasi overtaymda."))
        self.assertIn('FORA (+1,5)',bet('Torpedo fora +1,5'))
        self.assertIn('FORA (-1,5)',bet('Torpedo fora minus bir yarim'))
        self.assertIn('Toronto Maple Leafs 1X',bet('Toronto bir iks va total to‘rt yarim dan ko‘p'))
        self.assertIn('Boston Bruins\nIndividual total',bet("Boston individual total 2,5 dan ko'p"))
        self.assertTrue(forecast_conflict('Torpedo FORA (+1,5)','Torpedo fora -1,5'))
        self.assertIn('dan kam',bet('Total besh yarim dan kam'))
        self.assertTrue(forecast_conflict('Total: 5 dan ko‘p',"Mening tanlovim total 5 dan kam."))
        self.assertFalse(forecast_conflict('Total: 5 dan ko‘p',"Mening tanlovim total beshta dan ko'p."))
        self.assertIsNone(classify("Mening tanlovim Boston g'alabasi emas.")[0])

    def test_uzbek_retakes_share_cleanup_and_numbers_get_local_review(self):
        from hockey_editor.speech_cleanup import remove_retakes
        from test_workflow_improvements import segment as words
        text="Bugun Toronto juda kuchli o'yin ko'rsatadi va beshta shayba uradi."
        bad=words("Bugun Toronto juda zaif o'yin ko'rsatadi.",0);good=words(text,5)
        _,cuts=remove_retakes([Block(script=text,language='uz',sport='hockey')],[bad,good]);self.assertTrue(cuts)
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.touch();p=project(str(host))
            p.blocks=p.blocks[:1];p.blocks[0].script="Toronto oxirgi uchrashuvda 4 ta shayba urdi. Mening tanlovim total 5 dan ko'p."
            p.recording_times='00:00 00:08 intro\n00:08 00:20 first\n00:20 00:30 outro'
            speech=[segment(0,8,'Assalomu alaykum. Toronto Montreal. Boshladik!'),segment(8,15,'Toronto oxirgi uchrashuvda 7 ta shayba urdi.'),segment(15,20,"Mening tanlovim total 5 dan ko'p."),segment(20,30,"Xullas Toronto Montreal. Total 5 dan ko'p. Ko'rishguncha!")]
            prepare(p,speech,30)
            cards=p.blocks[0].speech_cards.values()
            self.assertTrue(any(c['title']=='СТАТИСТИКА' and c.get('needs_review') for c in cards))
            self.assertFalse(any(c['title']=='ПРОГНОЗ' and c.get('needs_review') for c in cards))

    def test_facts_and_roster_not_every_sentence(self):
        self.assertEqual(classify('Atigi 18 yosh.')[0],'СТАТИСТИКА')
        self.assertEqual(classify('Jamoaga yangi murabbiy Jim Hiller keldi.')[0],'СОСТАВ КОМАНДЫ')
        self.assertEqual(classify("Toronto himoyasi kuchli emas.")[1],"Toronto himoyasi kuchli emas")
        self.assertEqual(classify("Power play Edmontonning asosiy qurollaridan biri bo'lib qoladi.")[0],'ИНФОРМАЦИЯ')
        for text in ['Bu oddiy o‘yin emas.','NHL qaytdi!','Toronto — Montreal.','Havola tavsifda.','Albatta yuz foiz kafolat yo‘q.']:
            self.assertIsNone(classify(text)[0],text)

    def test_historical_subject_and_score_order_match_recording(self):
        s=MatchSource('a','Boston Bruins','New York Rangers')
        b=Block(title='Boston Bruins — New York Rangers',language='uz',sport='hockey',match_ids=[s.id],script="Qiziq tomoni, Rangersning oxirgi tashriflaridan birida Boston ularni 10:2 hisobida mag'lub qilgan. Mening tanlovim — total 5 dan ko'p. 3:3 — mos.")
        found=events(b,[s]);self.assertEqual(len(found),1);self.assertEqual(found[0].score,[10,2]);self.assertEqual(found[0].kind,'result')
        self.assertTrue(found[0].phrase.startswith('Qiziq tomoni'))
        reverse=copy.deepcopy(s);reverse.home,reverse.away=s.away,s.home
        self.assertEqual(events(b,[reverse])[0].score,[2,10])

    def test_archives_follow_team_and_exact_opponent(self):
        a=MatchSource('a','Toronto Maple Leafs','Montreal Canadiens');b=MatchSource('b','Boston Bruins','New York Rangers')
        c=MatchSource('c','Vegas Golden Knights','San Jose Sharks')
        block=Block(title='Toronto Maple Leafs — Boston Bruins',language='uz',sport='hockey',match_ids=[a.id,b.id,c.id],script="Toronto uyda juda kuchli hujum ko'rsatmoqda. Boston esa oxirgi uchrashuvda Rangersni 10:2 hisobida mag'lub qilgan. Mening tanlovim — total 5 dan ko'p.")
        found=events(block,[a,b,c]);self.assertEqual([e.source_id for e in found],[a.id,b.id]);self.assertEqual(found[-1].score,[10,2])
        self.assertFalse(events(block,[c]))

    def test_written_time_hints_do_not_override_spoken_sections_or_create_subtitles(self):
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.touch();p=project(str(host))
            texts=[('Assalomu alaykum. Toronto Montreal. Boston Rangers. Boshladik!',0,8),
                (p.blocks[0].script,8,20),(p.blocks[1].script,20,32),(p.outro.script,32,45)]
            speech=[segment(a,z,t) for t,a,z in texts]
            p.recording_times='00:00 00:08 intro\n00:08 00:20 first\n00:20 00:32 second\n00:32 00:45 outro'
            prepare(p,speech,45)
            self.assertLess(p.blocks[0].asr_lines[0]['start'],10)
            self.assertTrue(all(not l.get('review_reason') for b in p.blocks for l in b.asr_lines))
            cards,_=framing_cards(p,p.intro,[Line(**v) for v in p.intro.asr_lines],45)
            self.assertEqual(len([c for c in cards if c.title=='РАЗБОР МАТЧА']),2)
            self.assertLessEqual(cards[0].end,cards[1].start)
            cards,_=framing_cards(p,p.outro,[Line(**v) for v in p.outro.asr_lines],45)
            self.assertEqual({c.forecast_id for c in cards if c.title=='ПРОГНОЗ'},{b.uid for b in p.blocks})

    def test_logo_folder_understands_khl_translit_and_nhl_names(self):
        from hockey_editor.logos import assign
        with tempfile.TemporaryDirectory() as d:
            for name in ['СКА','ЦСКА','Toronto Maple Leafs','Montreal Canadiens']:Image.new('RGB',(12,12),'red').save(Path(d)/(name+'.png'))
            p=Project(profile='uz_hockey',logo_folder=d,blocks=[Block(title='SKA — CSKA'),Block(title='Toronto — Monreal')]);assign(p)
            self.assertEqual(len(p.team_logos),4)

    def test_empty_asr_keeps_manual_ranges_and_edited_script_updates_pick(self):
        from hockey_editor.framing import forecast_text
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.touch();p=project(str(host))
            p.recording_times='00:00 00:08 intro\n00:08 00:20 first\n00:20 00:32 second\n00:32 00:45 outro'
            prepare(p,[],45)
            self.assertEqual(p.blocks[1].asr_lines[0]['start'],20)
            self.assertEqual(p.outro.asr_lines[-1]['end'],45)
            p.blocks[0].script="Mening tanlovim — Toronto 1X va total 5,5 dan ko'p."
            self.assertIn('5,5',forecast_text(p.blocks[0]))

    def test_full_episode_exports_hockey_footage_intro_and_recap(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);host=d/'host.mp4'
            run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=45','-f','lavfi','-i','sine=f=220:r=48000:d=45','-t',45,'-c:v','libx264','-c:a','aac',host])
            p=project(str(host));p.settings.auto_rotate=False;p.settings.cut_pauses=False;p.settings.zoom=False
            for block,color in zip(p.blocks,['red','lime']):
                file=d/(color+'.mp4');run(['-y','-f','lavfi','-i',f'color=c={color}:s=320x180:r=30:d=4','-f','lavfi','-i','sine=f=440:r=48000:d=4','-t',4,'-c:v','libx264','-c:a','aac',file])
                home,away=block.title.split(' — ');source=MatchSource(str(file),home,away);p.matches.append(source);block.match_ids=[source.id]
            p.assets={'disclaimer':p.matches[0].path}
            p.recording_times='00:00 00:08 intro\n00:08 00:20 first\n00:20 00:32 second\n00:32 00:45 outro'
            speech=[segment(0,8,'Assalomu alaykum. Toronto Montreal. Boston Rangers. Boshladik!'),
                segment(8,10,'Toronto Maple Leafs va Montreal Canadiens.'),segment(10,16,"Toronto uyda hujumda kuchli va raqibga katta bosim beradi."),segment(16,20,"Mening tanlovim Toronto 1X va total 4,5 dan ko'p."),
                segment(20,22,'Boston Bruins va New York Rangers.'),segment(22,28,"Boston uyda hujumda kuchli va raqibga katta bosim beradi."),segment(28,32,"Mening tanlovim total 5 dan ko'p."),
                segment(32,34,'Toronto Montreal.'),segment(34,37,"Toronto 1X va total 4,5 dan ko'p."),segment(37,39,'Boston Rangers.'),segment(39,42,"Total 5 dan ko'p."),segment(42,45,"Keyingi videoda ko'rishguncha!")]
            def scan(scanner,source):
                return dict(signature=source_signature(source),candidates=[dict(id='play',score=None,before=None,time=1.5,start=0,end=3,confidence=.99,note='active hockey',kind='play')])
            with patch('hockey_editor.uz_speech.transcribe',return_value=speech),patch('hockey_editor.goals.GoalScanner.scan',scan):
                engine=EpisodeEngine(p,0,d/'cache',threading.Event());plan=engine.analyze()
            self.assertEqual(len(plan.sections),5)  # disclaimer + four speech sections
            self.assertEqual(len(plan.inserts),2)
            self.assertEqual({c.forecast_id for c in plan.cards if c.title=='ПРОГНОЗ'},{b.uid for b in p.blocks})
            for block in p.blocks:self.assertTrue(any(c.title=='РАЗБОР МАТЧА' and c.text==block.title for c in plan.cards))
            engine.render(plan,d/'full.mp4')
            for i,clip in enumerate(plan.inserts):
                run(['-y','-ss',(clip.start+clip.end)/2,'-i',d/'full.mp4','-frames:v',1,d/'check.png'])
                with Image.open(d/'check.png') as im:
                    r,g,b=im.convert('RGB').getpixel((100,500));self.assertLess(b,50);self.assertGreater(r if i==0 else g,180)

if __name__=='__main__':unittest.main()
