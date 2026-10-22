"""Synthetic script and media regressions for RU football / UZ fight Shorts."""
import tempfile,unittest,threading
from pathlib import Path
from unittest.mock import patch
from hockey_editor.model import Project,Block,MatchSource
from hockey_editor.profiles import apply_profile,kit_path
from hockey_editor.folder_import import parse_episode,pair_key
from hockey_editor.timeline import Line,Card,Plan,placements
from hockey_editor.shorts import finish_cards
from hockey_editor.editing import validate_plan

FIGHT_SCRIPT="""Bugun ikkita jangni ko'ramiz!
Leron Kavana — Ramazon Temirov! Petr Yan — Merab Dvalishvili!
Birinchi jang — Leron Kavana va o'zbekistonlik Ramazon Temirov!
Kavana masofada ishlaydi. Temirov kuchli zarbalar beradi.
Tanlovim — total 1,5 raunddan ko'p!
Telegram kanalida boshqa tahlillar bor. Havola tavsifda!
Ikkinchi jang — Petr Yan va Merab Dvalishvili!
Yan zarba beradi. Merab kurashga intiladi.
Agar jang besh raundga belgilangan bo'lsa, tanlovim — total 3,5 raunddan ko'p!
Demak, Kavana — Temirov jangida 1,5 raunddan ko'p, Yan — Dvalishvili bahsida besh raundlik format tasdiqlansa, 3,5 raunddan ko'p!
Ko'rishguncha!
"""

class NewShortsTests(unittest.TestCase):
    def test_profiles_presets_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            for profile,sport,language in [('ru_football_shorts','football','ru'),('uz_combat_shorts','combat','uz')]:
                p=Project();apply_profile(p,profile)
                self.assertEqual((p.settings.width,p.settings.height),(1080,1920))
                self.assertTrue(all(b.sport==sport and b.language==language for b in [p.intro,*p.blocks,p.outro]))
                path=Path(folder)/(profile+'.hockeyproj');p.save(path)
                self.assertEqual(Project.load(path).profile,profile)
            self.assertNotEqual(kit_path('ru_football_shorts'),kit_path('ru_hockey_shorts'))
            self.assertNotEqual(kit_path('uz_combat_shorts'),kit_path('uz_football_shorts'))

    def test_football_parser_and_footage_use_football(self):
        text='Сегодня футбол.\nПервый матч — Арсенал и Челси.\nАрсенал хорошо контролирует мяч и атакует по флангам.\nМой прогноз — тотал больше 2.5.\nВторой матч — Барселона и Реал Мадрид.\nМой прогноз — обе забьют.'
        a,blocks,z=parse_episode(text,'ru_football_shorts')
        self.assertEqual(len(blocks),2);self.assertEqual(z.script,'')
        self.assertTrue(all(b.sport=='football' for b in [a,*blocks,z]))
        self.assertIn('Арсенал',blocks[0].script)
        source=MatchSource('archive.mp4','Arsenal','Chelsea',sport='football')
        blocks[0].match_ids=[source.id]
        from hockey_editor.football_archives import events
        self.assertTrue(events(blocks[0],[source]))
        self.assertTrue(all(e.kind=='play' for e in events(blocks[0],[source])))
        single=parse_episode('Арсенал — Челси\nМой прогноз — тотал больше 2.5.','ru_football_shorts')
        self.assertEqual(len(single[1]),1)
        unheaded=parse_episode('Арсенал играет с Челси.\nМой прогноз — победа Арсенала.','ru_football_shorts')
        self.assertEqual(len(unheaded[1]),1)

    def test_combat_script_hook_promo_recap_and_condition(self):
        a,blocks,z=parse_episode(FIGHT_SCRIPT,'uz_combat_shorts')
        self.assertEqual(len(blocks),2);self.assertIn('ikkita',a.script)
        self.assertEqual(blocks[0].title,'Loner Kavana — Ramazon Temirov')
        self.assertIn('Telegram',blocks[0].script);self.assertTrue(z.script.startswith('Demak'))
        self.assertIn('Agar',blocks[1].forecast);self.assertIn('besh raund',blocks[1].forecast)
        self.assertEqual(pair_key(blocks[0].title,'uz_combat_shorts'),pair_key("Lone'er Kavanagh — Ramazan Temirov",'uz_combat_shorts'))

    def test_spoken_boundaries_ignore_hook_and_middle_telegram(self):
        from hockey_editor.combat_shorts import spoken_ranges
        a,blocks,z=parse_episode(FIGHT_SCRIPT,'uz_combat_shorts');p=Project(profile='uz_combat_shorts',intro=a,blocks=blocks,outro=z)
        segments=[];t=0;expected=[]
        for row in FIGHT_SCRIPT.splitlines():
            if row.startswith(('Birinchi','Ikkinchi','Demak')):expected.append(t)
            words=[]
            for token in row.split():words.append(dict(word=token,start=t,end=t+.3));t+=.4
            segments.append(dict(text=row,start=words[0]['start'],end=words[-1]['end'],words=words))
        spans=spoken_ranges(p,segments,t)
        self.assertEqual([x[0] for x in spans],[0,*expected])
        from hockey_editor.combat import prepare
        prepare(p,segments,t)
        self.assertFalse(any('Не подтверждены границы' in line['review_reason'] for b in blocks for line in b.asr_lines))

    def test_fight_total_and_conditional_recap(self):
        from hockey_editor.combat_shorts import framing_cards
        a,blocks,z=parse_episode(FIGHT_SCRIPT,'uz_combat_shorts');p=Project(profile='uz_combat_shorts',intro=a,blocks=blocks,outro=z)
        for block in blocks:
            text=next(r for r in block.script.splitlines() if 'tanlovim' in r.lower())
            lines=[Line(text,2,8,recognized=text)]
            _,cards,_=placements(block,lines,{},10,shorts=True)
            pick=next(c for c in cards if c.title=='ПРОГНОЗ')
            self.assertEqual(pick.text,block.forecast)
        text=z.script.splitlines()[0];cards,_=framing_cards(p,z,[Line(text,0,15,recognized=text)],15)
        picks=[c for c in cards if c.title=='ПРОГНОЗ']
        self.assertEqual({c.forecast_id for c in picks},{b.uid for b in blocks})
        self.assertTrue(any('besh raund' in c.text for c in picks))
        self.assertLessEqual(picks[0].end,picks[1].start)

    def test_bilingual_names_preserve_people_and_short_surnames(self):
        from hockey_editor.fighters import same_fighter,position,name_index,name_key
        from hockey_editor.fighter_aliases import FIGHTER_NAMES,RANKED_SNAPSHOT
        from hockey_editor.fighter_roster import UFC_NAMES
        known={name_key(n) for n in UFC_NAMES}
        for english,uzbek,variants in FIGHTER_NAMES:
            self.assertIn(name_key(english),known)
            self.assertTrue(same_fighter(english,uzbek),(english,uzbek))
            for v in variants:self.assertTrue(same_fighter(english,v))
        self.assertFalse(same_fighter('Umar Nurmagomedov','Said Nurmagomedov'))
        self.assertFalse(same_fighter('Jon Jones','Mike Jones'))
        self.assertIsNotNone(position('Petr Yan','Yan zarba beradi.'))
        self.assertIsNotNone(position("Lone'er Kavanagh",'Kavana masofani saqlaydi.'))
        self.assertIsNotNone(position('Ramazan Temirov','Temirovning zarbasi kuchli.'))
        self.assertTrue(all(name_key(n) in name_index() for n in RANKED_SNAPSHOT))
        self.assertIsNotNone(position('Khalil Rountree Jr.','Rauntri zarba beradi.'))

    def test_mobile_creation_and_combat_recording_ownership(self):
        from test_mini_app import app_fixture
        from hockey_editor.mini_bridge import Bridge
        from hockey_editor.mobile_inputs import Inputs
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=app_fixture(root);bridge=Bridge(app);inputs=Inputs(bridge,root/'catalog.json')
            for profile,text in [('ru_football_shorts','Арсенал — Челси\nМой прогноз — тотал больше 2.5.'),('uz_combat_shorts',FIGHT_SCRIPT)]:
                ident=inputs.create(dict(parent=str(root),name=profile,profile=profile,request=profile+'-request'))['id']
                inputs.script(dict(id=ident,text=text));draft=inputs.load(ident)
                host=root/(profile+'.mp4');host.write_bytes(b'host')
                draft['files'].append(dict(id='host',role='host',block='',name=host.name,status='ready',path=str(host),home='',away='',fighter=''))
                if profile=='uz_combat_shorts':
                    source=root/'fight.mp4';source.write_bytes(b'fight')
                    draft['files'].append(dict(id='fight',role='match',block=draft['blocks'][0]['uid'],name=source.name,status='ready',path=str(source),home='',away='',fighter='Ramazan Temirov'))
                inputs.save(draft);app.restore_plan=Mock();app.status.set=Mock()
                result=inputs.activate(dict(id=ident,revision=bridge.revision()))
                loaded=Project.load(result['project']);self.assertEqual(loaded.profile,profile)
                self.assertEqual((loaded.settings.width,loaded.settings.height),(1080,1920))
                if profile=='uz_combat_shorts':
                    self.assertEqual(loaded.matches[0].sport,'combat');self.assertEqual(loaded.matches[0].fighter,'Ramazan Temirov')

    def test_total_direction_and_condition_cannot_be_silently_approved(self):
        from hockey_editor.combat_cards import confidence
        block=Block(title='Petr Yan — Merab Dvalishvili',language='uz',sport='combat')
        p=Project(profile='uz_combat_shorts',blocks=[block])
        text="Total 3,5 raunddan ko'p"
        card=Card(0,4,'ПРОГНОЗ',text)
        self.assertTrue(confidence(card,Line(text,0,4,recognized='Total 3,5 raunddan kam'),block,p))
        card.text="Agar besh raund bo'lsa, total 3,5 raunddan ko'p"
        self.assertTrue(confidence(card,Line(card.text,0,4,recognized=text),block,p))

    def test_portrait_art_and_shared_geometry(self):
        from hockey_editor.graphics import card_image
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            for profile,text in [('ru_football_shorts','Арсенал — Челси'),('uz_combat_shorts','Loner Kavana — Ramazon Temirov')]:
                path=Path(folder)/(profile+'.png');card=Card(0,3,'РАЗБОР МАТЧА',text)
                x,y=card_image(card,path,profile=profile)
                with Image.open(path) as im:self.assertLessEqual(x+im.width,720);self.assertLessEqual(y+im.height,1280)
                card.offset_x=10;card.offset_y=20;card.scale=.75
                xx,yy=card_image(card,path,profile=profile);self.assertEqual((xx,yy),(x+10,y+20))

if __name__=='__main__':unittest.main()
