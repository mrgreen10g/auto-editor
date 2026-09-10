import copy
import tempfile
import threading
import unittest
from pathlib import Path
from PIL import Image,ImageDraw
from hockey_editor.model import Project,Block,MatchSource,EventRequest,Clip
from hockey_editor.goals import Candidate,propose
from hockey_editor.gameplay import gameplay_ranges,gameplay_candidates,bound_goal
from hockey_editor.timeline import Plan,Line,Insert,Card,placements
from hockey_editor.graphics import card_image
from hockey_editor.editing import EditHistory,validate_plan,store_plan,saved_plan


class V04Tests(unittest.TestCase):
    def test_non_game_motion_never_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[]
            for i in range(30):
                image=Image.new('RGB',(320,180),'#614528');d=ImageDraw.Draw(image)
                d.ellipse((30+i,20,230+i,170),fill='#d4a875')
                p=Path(tmp)/f'{i:03}.jpg';image.save(p);files.append(p)
            self.assertEqual(gameplay_candidates(files,15,threading.Event(),.5),[])

    def test_game_runs_stop_before_crowd_and_closeups(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[]
            for i in range(48):
                im=Image.new('RGB',(320,180),'#e8eef0' if 4<=i<20 or i>=27 else '#78462a')
                d=ImageDraw.Draw(im);d.rectangle((30+i*3%220,70,47+i*3%220,110),fill='#142637')
                p=Path(tmp)/f'{i:03}.jpg';im.save(p);files.append(p)
            ranges=gameplay_ranges(files,24,threading.Event(),.5)
            self.assertEqual(len(ranges),2)
            self.assertTrue(all(b<10 or a>13 for a,b in ranges))
            c=Candidate('g',[1,0],[0,0],9,2,15,.72)
            self.assertTrue(bound_goal(c,ranges));self.assertLess(c.end,10)

    def test_approximate_goal_is_not_replaced_by_generic_play(self):
        for score in ([1,2],[3,3],[4,3]):
            source=MatchSource('one.mp4','СКА','Лада')
            goal=Candidate('goal',score,[1,1],20,13,22,.72)
            play=Candidate('play',None,None,6,2,10,.86,kind='play')
            event=EventRequest(source.id,'Описание гола',score=score)
            propose([event],{source.id:{'signature':'s','candidates':[vars(play),vars(goal)]}},[source],True)
            self.assertEqual(event.selection.candidate_id,'goal');self.assertTrue(event.selection.accepted)
            goal.confidence=.45
            propose([event],{source.id:{'signature':'s','candidates':[vars(play),vars(goal)]}},[source],True)
            self.assertEqual(event.selection.candidate_id,'goal');self.assertFalse(event.selection.accepted)

    def test_overtime_without_period_uses_latest_goal(self):
        event=EventRequest('a','Победа в овертайме',kind='overtime')
        goals=[Candidate('first',[1,0],[0,0],20,13,22,.99),Candidate('last',[4,3],[3,3],80,73,82,.72)]
        propose([event],{'a':{'signature':'s','candidates':[vars(c) for c in goals]}})
        self.assertEqual(event.selection.candidate_id,'last')

    def test_archive_rotation_balances_three_sources(self):
        sources=[MatchSource(str(i),'СКА' if i==0 else 'Лада',str(i)) for i in range(3)]
        scans={m.id:{'signature':m.id,'candidates':[vars(Candidate(str(j),None,None,j*12+4,j*12,j*12+8,.86,kind='play')) for j in range(3)]} for m in sources}
        events=[EventRequest('','Форма команды',kind='play',requested_teams=['Лада']) for _ in range(6)]
        propose(events,scans,sources,True)
        self.assertEqual(sorted(sum(e.source_id==m.id for e in events) for m in sources),[2,2,2])
        self.assertTrue(all(a.source_id!=b.source_id for a,b in zip(events,events[1:])))

    def test_density_preserves_explicit_goals_and_removes_context_cards(self):
        lines=[Line('Вступление',0,5)]+[Line(f'Фраза {i}',5+i*5,10+i*5) for i in range(10)]
        clips=[Clip('game',l.text,3,'Архивные кадры · СКА — Лада',kind='score' if i==5 else 'play') for i,l in enumerate(lines[1:])]
        block=Block(clips=clips)
        plans=[placements(block,lines,{'game':{'duration':8}},55,f) for f in ('low','normal','high')]
        self.assertLess(len(plans[0][0]),len(plans[-1][0]))
        for inserts,cards,_ in plans:
            self.assertTrue(any(c.label=='Фраза 5' for c in inserts))
            self.assertTrue(all(c.start>=5 for c in inserts))
            self.assertFalse(any('КАДРЫ' in c.title for c in cards))

    def test_short_forecast_and_stats_are_compact_top_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            for title,text in [('ПРОГНОЗ','Лада\nФора (+2)'),('ОЖИДАЕМЫЙ СЧЁТ','3:2 или 4:2 · СКА'),('СТАТИСТИКА','Броски: 36 — 32')]:
                p=Path(tmp)/'card.png';x,y=card_image(Card(0,5,title,text),p)
                with Image.open(p) as im:self.assertLess(im.width,460)
                self.assertLess(x,60);self.assertLess(y,60)

    def test_edit_history_validates_bounds_and_roundtrips_portably(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);media=root/'game.mp4';media.touch()
            project=Project(host=str(media),blocks=[Block(script='Текст достаточно длинный для анализа и монтажа.')])
            plan=Plan(0,20,[(0,20)],[Line('Фраза',0,20)],[Insert(str(media),6,10,2,'Игра',source_min=1,source_max=9)],[Card(0,5,'РАЗБОР МАТЧА','СКА — Лада')],[],20)
            history=EditHistory(plan);edited=copy.deepcopy(plan);edited.inserts[0].start=7;edited.inserts[0].end=11
            history.replace(edited);self.assertTrue(history.undo());self.assertEqual(history.plan.inserts[0].start,6)
            self.assertTrue(history.redo());self.assertEqual(history.plan.inserts[0].start,7)
            invalid=copy.deepcopy(edited);invalid.inserts[0].source_in=8
            with self.assertRaisesRegex(ValueError,'конец'):history.replace(invalid)
            invalid=copy.deepcopy(edited);invalid.inserts.append(copy.deepcopy(invalid.inserts[0]))
            with self.assertRaisesRegex(ValueError,'пересекаются'):validate_plan(invalid)
            store_plan(project,0,edited);file=root/'project.hockeyproj';project.save(file)
            loaded=Project.load(file);self.assertEqual(saved_plan(loaded,0).inserts[0].start,7)
            self.assertIn('"path": "game.mp4"',file.read_text(encoding='utf8'))
            loaded.blocks[0].script+=' Изменение.';self.assertIsNone(saved_plan(loaded,0))
