"""Fight inserts are optional illustrations, not a phrase-by-phrase review queue."""
import copy,tempfile,unittest
from pathlib import Path
from dataclasses import asdict
from hockey_editor.model import Project,Block,MatchSource,EventRequest,EventSelection
from hockey_editor.combat import events,migrate_optional_archives
from hockey_editor.combat_scan import confident_fight,illustration_candidates,DETECTOR_VERSION
from hockey_editor.goals import propose,unresolved

class FightIllustrationTests(unittest.TestCase):
    def test_slow_live_fight_is_enough_no_strike_required(self):
        clock=[[t,100-t,.95] for t in range(0,22,2)]
        self.assertTrue(confident_fight(.5,4,clock,[.3]*44,[False]*44))
        self.assertGreater(len(illustration_candidates(clock,[.3]*44,[False]*44,22)),0)

    def test_ad_walkout_frozen_clock_missing_clock_cut_and_still_are_rejected(self):
        clock=[[t,100-t,.95] for t in range(0,8,2)]
        for bad in ([[t,None,0] for t,_,_ in clock], [[t,100,.95] for t,_,_ in clock], [[0,100,.95],[2,None,0],[4,96,.95],[6,94,.95]], [[0,100,.95],[2,98,.95],[4,100,.95],[6,102,.95]]):
            self.assertFalse(confident_fight(.5,4,bad,[2.]*16,[False]*16))
        self.assertFalse(confident_fight(.5,4,clock,[2.]*16,[False,False,True]+[False]*13))
        self.assertFalse(confident_fight(.5,4,clock,[0.]*16,[False]*16))

    def test_many_slots_with_few_clips_never_create_mandatory_queue(self):
        source=MatchSource('fight.mp4','','',sport='combat',fighter='Petr Yan')
        b=Block(sport='combat',events=[EventRequest(source.id,'Yan kurash va bosim.','play',requested_teams=[source.fighter]) for _ in range(108)])
        candidates=[dict(id=str(i),start=i*6,end=i*6+3.5,time=i*6+1,confidence=.86,kind='play',note='Live fight') for i in range(4)]
        scans={source.id:dict(signature='s',fighter=source.fighter,detector_version=DETECTOR_VERSION,candidates=candidates)}
        propose(b.events,scans,[source])
        self.assertEqual(len(unresolved(b)),0)
        self.assertEqual(sum(bool(e.selection and e.selection.accepted) for e in b.events),4)
        self.assertEqual(sum(e.skipped for e in b.events),104)
        self.assertEqual(len({e.selection.candidate_id for e in b.events if e.selection}),4)

    def test_legacy_queue_removed_preserving_authored_trims(self):
        accepted=EventRequest('s','Yan zarba.','play',selection=EventSelection('manual',4,9,6,'sig',True))
        pending=EventRequest('s','Yan himoya.','play',selection=EventSelection('weak',10,13,11,'sig',False))
        skipped=EventRequest('s','Yan bosim.','play',skipped=True,note='User decision')
        p=Project(profile='uz_combat',blocks=[Block(sport='combat',events=[accepted,pending,skipped,EventRequest('s','No footage','play')])])
        before=asdict(accepted);manual=asdict(skipped)
        migrate_optional_archives(p);migrate_optional_archives(p)
        self.assertEqual(asdict(accepted),before);self.assertEqual(asdict(skipped),manual)
        self.assertFalse(unresolved(p.blocks[0]));self.assertFalse(pending.selection.accepted)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'p.hockeyproj';p.save(path);q=Project.load(path)
            self.assertFalse(unresolved(q.blocks[0]));self.assertEqual(asdict(q.blocks[0].events[0]),before)

    def test_only_fight_description_slots_not_biography_cta_or_bet(self):
        s=MatchSource('a','','',sport='combat',fighter='Petr Yan')
        b=Block(title='Petr Yan — Merab Dvalishvili',sport='combat',language='uz',match_ids=[s.id],script="Yan rossiyalik jangchi. Yan 33 yoshda. Yan rekordi yaxshi. Yan masofani saqlaydi. Yan kurashdan himoyalanadi. Telegram kanaliga obuna bo'ling. Tanlovim — Yan g'alabasi.")
        found=events(b,[s]);self.assertEqual(len(found),2)
        self.assertTrue(all('masofa' in e.phrase or 'himoya' in e.phrase for e in found))

    def test_missing_or_wrong_owner_never_auto_accepted(self):
        s=MatchSource('a','','',sport='combat',fighter='Petr Yan')
        for who in ('Merab Dvalishvili',''):
            e=EventRequest(s.id,'Fight','play',requested_teams=[who])
            propose([e],{s.id:dict(signature='s',fighter=s.fighter,detector_version=DETECTOR_VERSION,candidates=[dict(id='one',start=0,end=3,time=1,confidence=.99,kind='play',note='fight')])},[s])
            self.assertIsNone(e.selection);self.assertTrue(e.skipped)

    def test_completed_visual_analysis_reused_without_frame_extraction(self):
        import json
        from unittest.mock import Mock,patch
        from hockey_editor.combat_scan import scan
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cache=root/'sig';cache.mkdir()
            state=dict(count=44,motion=[.3]*44,cuts=[False]*44,observations=[[t,100-t,.95] for t in range(0,22,2)],clock_box=None)
            (cache/'combat-analysis-v1.json').write_text(json.dumps(state))
            source=MatchSource('fight.mp4','','',sport='combat',fighter='Petr Yan')
            scanner=Mock(root=root)
            with patch('hockey_editor.goals.source_signature',return_value='sig'),patch('hockey_editor.combat_scan.probe',return_value=dict(duration=22,video=True)),patch('hockey_editor.scan_cache.single_frames') as frames:
                result=scan(source,scanner)
                frames.assert_not_called()
            self.assertEqual(result['detector_version'],DETECTOR_VERSION)
            self.assertGreater(len(result['candidates']),0)
