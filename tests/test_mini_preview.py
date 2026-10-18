import copy,tempfile,unittest
from pathlib import Path
from test_mini_app import app_fixture
from hockey_editor.mini_preview import snapshot
from hockey_editor.mini_server import RemoteError
from hockey_editor.mini_bridge import Bridge
from hockey_editor.timeline import Card,Insert
from hockey_editor.editing import validate_plan

class MiniPreviewTests(unittest.TestCase):
    def test_snapshot_keeps_cuts_and_neighbours_without_mutating_project(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));p=app.plan
            p.source_start=10;p.source_end=20;p.keep=[(0,3),(5,10)]
            p.cards.append(Card(4,7,'ИНФОРМАЦИЯ','Соседняя плашка'))
            p.inserts=[Insert(app.project.host,2,6,15,'Матч',source_min=15,source_max=19)]
            before=copy.deepcopy(p.to_dict())
            spec=snapshot(app.project,p,0,p.review_items[0],p.cards[0],dict(start=3,end=5,text='Новый текст'))
            result=spec['plan']
            self.assertEqual(result.duration,4)
            self.assertEqual([(m['start'],m['end']) for m in result.media],[(12,13),(15,18)])
            self.assertEqual((result.cards[0].start,result.cards[0].end,result.cards[0].text),(1,3,'Новый текст'))
            self.assertEqual(len(result.cards),2);self.assertEqual(result.inserts[0].source_in,15)
            validate_plan(result);self.assertEqual(p.to_dict(),before)
            self.assertIsNot(spec['project'],app.project)
    def test_bounded_preview_and_bad_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));p=app.plan;p.duration=100;p.source_end=100;p.keep=[(0,100)];p.cards[0].end=90
            spec=snapshot(app.project,p,0,p.review_items[0],p.cards[0],{})
            self.assertEqual(spec['plan'].duration,20)
            for values in (dict(start=-1),dict(end=101),dict(start=float('nan')),dict(end=1.01),dict(text='')):
                with self.assertRaises(RemoteError):snapshot(app.project,p,0,p.review_items[0],p.cards[0],values)
    def test_review_filters_have_structured_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));item=Bridge(app).state()['items'][0]
            self.assertEqual(item['block'],app.project.blocks[0].uid)
            self.assertEqual(item['block_title'],'СКА — Лада')
            self.assertEqual(item['category'],'Статистика')
    def test_deleted_card_preview_and_forecast_group_are_detached(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));p=app.plan;card=p.cards.pop()
            card.title='ПРОГНОЗ';card.forecast_id=app.project.blocks[0].uid
            p.cards.append(Card(4,6,'ПРОГНОЗ','Старый повтор',forecast_id=card.forecast_id))
            result=snapshot(app.project,p,0,p.review_items[0],card,dict(text='Новая ставка',owner=card.forecast_id))['plan']
            self.assertEqual([c.text for c in result.cards],['Новая ставка','Новая ставка'])
            self.assertEqual(len(p.cards),1);self.assertEqual(p.cards[0].text,'Старый повтор')
