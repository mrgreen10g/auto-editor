"""Synthetic fixtures: Uzbek hockey uses shared Shorts framing and archive cache."""
import tempfile,unittest
from pathlib import Path
from hockey_editor.model import Project,Block,MatchSource,EventRequest,EventSelection
from hockey_editor.uz_hockey_shorts import parse_script
from hockey_editor.uz_hockey import prepare,classify
from hockey_editor.shorts import sections,import_archives,archive_scans
from hockey_editor.profiles import apply_profile
from test_shorts import segments

SCRIPT="""NHL | SHORTS SSENARIY
70–90 soniya
Bugun uchta uchrashuvni ko'ramiz.
Birinchi o'yin — Boston va Toronto.
Boston ikki o'yinda beshta shayba urdi.
Tanlovim — Boston 1X.
Telegram kanaliga obuna bo'ling. Havola tavsifda.
Ikkinchi o'yin — Dallas va Edmonton.
Tanlovim — total 4,5 dan ko'p.
Va Utah Mammoth — Chicago.
Tanlovim — Utahning yakuniy g'alabasi, overtime va bullitlar bilan.
Demak:
Boston — 1X.
Dallas — Edmonton — total 4,5 dan ko'p.
Utah — yakuniy g'alaba.
Layk bosing!
"""
def project():
    a,b,c=parse_script(SCRIPT)
    return Project(profile='uz_hockey_shorts',intro=a,blocks=b,outro=c,full_video=True)

class UzbekHockeyShortsTests(unittest.TestCase):
    def test_profile_persists_language_sport_and_portrait(self):
        p=Project();apply_profile(p,'uz_hockey_shorts')
        self.assertEqual((p.settings.width,p.settings.height),(1080,1920))
        self.assertEqual((p.intro.language,p.intro.sport),('uz','hockey'))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'p.hockeyproj';p.save(path);q=Project.load(path)
            self.assertEqual(q.profile,p.profile);self.assertEqual(q.intro.sport,'hockey')

    def test_three_pairs_and_nonordinal_third_ignore_notes(self):
        a,b,c=parse_script(SCRIPT+'\n[Здесь вставить матч]\nhttps://youtube.com/watch?v=example')
        self.assertEqual([x.title for x in b],['Boston Bruins — Toronto Maple Leafs','Dallas Stars — Edmonton Oilers','Utah Mammoth — Chicago Blackhawks'])
        self.assertTrue(all(x.sport=='hockey' for x in [a,*b,c]))
        self.assertIn('OT va bullitlar',b[-1].forecast)
        self.assertNotIn('youtube',c.script);self.assertNotIn('SSENARIY',a.script)

    def test_boundaries_keep_final_win_in_analysis_and_all_three_bets(self):
        p=project();ss=segments(p);bounds,_,_=sections(p,ss)
        for n,prefix in [(1,'Birinchi'),(2,'Ikkinchi'),(3,'Va Utah'),(4,'Demak')]:
            self.assertEqual(bounds[n],next(s['start'] for s in ss if s['text'].startswith(prefix)))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'host';path.write_bytes(b'test');p.host=str(path);prepare(p,ss,ss[-1]["end"])
        for b in p.blocks:
            bets=[c for c in b.speech_cards.values() if c['title']=='ПРОГНОЗ']
            self.assertEqual(len(bets),1);self.assertFalse(bets[0].get('needs_review'))
        from hockey_editor.uz_hockey import framing_cards
        from hockey_editor.timeline import Line
        cards,_=framing_cards(p,p.outro,[Line(**v) for v in p.outro.asr_lines],ss[-1]['end'])
        self.assertEqual(len([c for c in cards if c.title=='ПРОГНОЗ']),3)
        self.assertTrue(any(c['title']=='ТЕЛЕГРАМ' for c in p.blocks[0].speech_cards.values()))
        self.assertNotEqual(classify("Shuning uchun sof g'alabani olmayman.")[0],'СТАТИСТИКА')

    def test_accepted_hockey_archive_reuse(self):
        from hockey_editor.goals import source_signature
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'match.mp4';path.write_bytes(b'video')
            src=MatchSource(str(path),'Boston Bruins','Toronto Maple Leafs',sport='hockey')
            owner=Block(title='Boston Bruins — Toronto Maple Leafs',match_ids=[src.id],language='uz',sport='hockey')
            owner.events=[EventRequest(src.id,'Archive',kind='play',selection=EventSelection('accepted',1,8,4,source_signature(src),True))]
            donor=Project(profile='uz_hockey',blocks=[owner],matches=[src]);p=project()
            count,_=import_archives(p,donor);self.assertEqual(count,1)
            self.assertIn(src.id,archive_scans(p.blocks[0],p.matches))
            self.assertEqual(p.blocks[0].asr_lines,[])
