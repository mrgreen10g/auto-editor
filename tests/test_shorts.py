import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from hockey_editor.model import Project,Block,MatchSource,EventRequest,EventSelection
from hockey_editor.shorts import parse_script,sections,finish_cards,import_archives,archive_scans
from hockey_editor.timeline import Card,Insert,Line,Plan

SCRIPT="""UEFA | SHORTS SSENARIY
70–90 soniya
Fransiya ikki o'yinda oltita gol urdi. Bugungi ikkita tanlovni ko'ramiz.
Birinchi o'yin — Germaniya va Italiya.
Germaniya ikki gol urdi. Muhim raqamlar bor.
Tanlovim — Italiya X2 va total 1,5 dan ko'p.
Aytgancha, YouTube'da aytmaydigan qo'shimcha prognozlarim bor.
Ularni Telegram kanaliga joylayman. Havola tavsifda.
Ikkinchi o'yin — Fransiya va Belgiya.
Fransiya ikki o'yinda oltita gol urdi.
Tanlovim — Fransiya g'alabasi va total 1,5 dan ko'p.
Demak:
Germaniya — Italiya: Italiya X2 va total 1,5 dan ko'p.
Fransiya — Belgiya: Fransiya g'alabasi va total 1,5 dan ko'p.
Layk bosing va kanalga obuna bo'ling!
"""

def project():
    a,b,c=parse_script(SCRIPT)
    return Project(profile='uz_football_shorts',intro=a,blocks=b,outro=c,full_video=True)


def segments(p):
    result=[];t=0
    for block in [p.intro,*p.blocks,p.outro]:
        for line in block.script.splitlines():
            words=[]
            for word in line.split():
                words.append(dict(word=word,start=t,end=t+.3,probability=.99));t+=.32
            result.append(dict(start=words[0]['start'],end=words[-1]['end'],text=line,words=words));t+=.1
    return result


class ShortsTests(unittest.TestCase):
    def test_spoken_script_ignores_title_notes_links_and_hook(self):
        a,b,c=parse_script(SCRIPT+'\n[Здесь вставить статистику]\nhttps://youtube.com/watch?v=test')
        self.assertEqual([v.title for v in b],['Germaniya — Italiya','Fransiya — Belgiya'])
        self.assertNotIn('SSENARIY',a.script)
        self.assertIn('Telegram',b[0].script)
        self.assertTrue(c.script.startswith('Demak:'))
        self.assertNotIn('youtube.com',c.script)

    def test_automatic_boundaries_ignore_middle_telegram(self):
        p=project();ss=segments(p);bounds,_,_=sections(p,ss)
        for n,prefix in [(1,'Birinchi'),(2,'Ikkinchi'),(3,'Demak')]:
            self.assertEqual(bounds[n],next(s['start'] for s in ss if s['text'].startswith(prefix)))

    def test_short_manual_times_accept_middle_promo_without_extra_match(self):
        from hockey_editor.recording_times import parse_times
        raw='00:00 00:07 Начало\n00:08 00:30 Первый матч\n00:30 00:35 ТГ канал\n00:36 01:08 Второй матч\n01:08 01:14 Концовка'
        result=parse_times(raw,2,allow_promos=True)
        self.assertEqual(len(result),4);self.assertEqual(result[1][1],35)

    def test_prepare_has_two_compound_bets_no_invented_intro_pairs(self):
        from hockey_editor.uz_speech import prepare
        from hockey_editor.framing import forecast_text
        p=project()
        with tempfile.TemporaryDirectory() as d:
            host=Path(d)/'host';host.write_bytes(b'test');p.host=str(host)
            prepare(p,segments(p))
        self.assertFalse(any(c['title']=='РАЗБОР МАТЧА' for c in p.intro.speech_cards.values()))
        for block in p.blocks:
            bets=[c for c in block.speech_cards.values() if c['title']=='ПРОГНОЗ']
            self.assertEqual(len(bets),1);self.assertIn('1,5',bets[0]['text'])
            self.assertFalse(bets[0].get('needs_review',False))
        self.assertIn('X2',forecast_text(p.blocks[0]))
        self.assertEqual(len([c for c in p.outro.speech_cards.values() if c['title']=='ПРОГНОЗ']),2)
        self.assertEqual(len([c for c in p.blocks[0].speech_cards.values() if c['title']=='ТЕЛЕГРАМ']),1)

    def test_priority_and_promo_exclusion_preserve_source_bounds(self):
        p=project();p.assets['telegram']='tg.mp4'
        cards=[Card(0,3,'РАЗБОР МАТЧА',p.blocks[0].title),Card(2,5,'СТАТИСТИКА','2 gol'),Card(5,7,'ПРОГНОЗ','X2'),Card(7,10,'ТЕЛЕГРАМ','Telegram')]
        clips=[Insert('game',2,8,10,'game',source_min=0,source_max=30)]
        cards,clips=finish_cards(p,p.blocks[0],[],cards,clips,10)
        self.assertTrue(all(a.end<=b.start for a,b in zip(cards,cards[1:])))
        self.assertEqual([(c.start,c.end,c.source_in) for c in clips],[(3,5,11)])
        self.assertEqual(cards[-1].asset,'tg.mp4')

    def test_vertical_artwork_and_live_preview(self):
        from hockey_editor.graphics import card_image
        from hockey_editor.live_cards import LiveCards
        p=project();p.settings.animate_cards=False;p.settings.wobble=False
        with tempfile.TemporaryDirectory() as d:
            for c in [Card(0,4,'РАЗБОР МАТЧА',p.blocks[0].title),Card(0,4,'ПРОГНОЗ','Italiya X2\nJami gollar: 1,5 dan ko‘p',fixture=p.blocks[0].title),Card(0,4,'СТАТИСТИКА','2 o‘yin — 6 ochko')]:
                path=Path(d)/'card.png';x,y=card_image(c,path,profile=p.profile)
                with Image.open(path) as im:self.assertLessEqual(x+im.width,720);self.assertLessEqual(y+im.height,1150)
                plan=Plan(0,4,[(0,4)],[],[],[c],[],4)
                result=LiveCards(p,d).compose(Image.new('RGB',(360,640)),1,plan)
                self.assertIsNotNone(result.getbbox())

    def test_import_does_not_rescan_or_copy_host_timings(self):
        from hockey_editor.goals import source_signature
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'match.mp4';path.write_bytes(b'video')
            source=MatchSource(str(path),'Germaniya','Italiya',sport='football')
            owner=Block(title='Germaniya — Italiya',match_ids=[source.id],language='uz')
            selection=EventSelection('accepted',1,8,4,source_signature(source),True)
            owner.events=[EventRequest(source.id,'Old long words',kind='play',selection=selection),EventRequest(source.id,'Not accepted',selection=EventSelection('weak',2,8,5,source_signature(source),False))]
            donor=Project(profile='uz_football',host='other-host.mp4',blocks=[owner],matches=[source])
            p=project();before=p.blocks[0].script;count,notes=import_archives(p,donor)
            self.assertEqual(count,1);self.assertEqual(p.blocks[0].script,before);self.assertEqual(p.host,'')
            self.assertEqual(p.blocks[0].asr_lines,[])
            scans=archive_scans(p.blocks[0],p.matches);self.assertIn(source.id,scans)
            p.save(Path(d)/'short.hockeyproj');loaded=Project.load(Path(d)/'short.hockeyproj')
            self.assertEqual(loaded.blocks[0].archive_pool,p.blocks[0].archive_pool)
            path.write_bytes(b'changed recording');self.assertFalse(archive_scans(p.blocks[0],p.matches))

    def test_profile_and_shared_preset_keep_orientation(self):
        from hockey_editor.profiles import apply_profile
        from hockey_editor.preferences import save_preset,apply_preset
        with tempfile.TemporaryDirectory() as d:
            p=Project();file=Path(d)/'settings.json';save_preset(p,'shared',file)
            apply_profile(p,'uz_football_shorts');apply_preset(p,'shared',file)
            self.assertEqual((p.settings.width,p.settings.height),(720,1280))
            apply_profile(p,'ru_hockey');self.assertGreater(p.settings.width,p.settings.height)

if __name__=='__main__':unittest.main()
