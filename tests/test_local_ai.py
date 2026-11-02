import copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hockey_editor import local_ai as ai

class LocalAITests(unittest.TestCase):
    def test_cache_and_no_mutation(self):
        task=dict(id='one',status='pending',script='Nasaf X2',recognized='Nasaf X2',reason='Не уверен',start=1,end=2)
        plan=SimpleNamespace(review_items=[task]);before=copy.deepcopy(task)
        class Session:
            calls=0
            def __init__(self,cancel):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def judge(self,t):Session.calls+=1;return dict(verdict='equivalent',reason='Совпадает')
        with tempfile.TemporaryDirectory() as folder,patch.object(ai,'Session',Session):
            ai.annotate(plan,folder,threading.Event(),lambda s:None,True)
            self.assertEqual({k:v for k,v in task.items() if k!='ai_review'},before)
            self.assertIn('Совпадает',ai.description(task))
            ai.annotate(plan,folder,threading.Event(),lambda s:None,True)
            self.assertEqual(Session.calls,1)
            task['recognized']='Nasaf 1X';self.assertEqual(ai.description(task),'')
            ai.annotate(plan,folder,threading.Event(),lambda s:None,True)
            self.assertEqual(Session.calls,2)
    def test_errors_do_not_resolve(self):
        task=dict(status='pending',script='s',recognized='h');plan=SimpleNamespace(review_items=[task])
        with tempfile.TemporaryDirectory() as folder,patch.object(ai,'Session',side_effect=ValueError('memory')):
            logs=[];ai.annotate(plan,folder,threading.Event(),logs.append,True)
            self.assertEqual(task['status'],'pending');self.assertNotIn('ai_review',task)
            self.assertIn('memory',logs[-1])
    def test_strict_schema(self):
        for bad in ({},[],{'verdict':'confirmed','reason':'ok'},{'verdict':'equivalent','reason':None}):
            with self.assertRaises(ValueError):ai.valid_result(bad)
    def test_disabled_and_human_decisions(self):
        with patch.object(ai,'enabled',return_value=False),patch.object(ai,'Session') as session:
            ai.annotate(SimpleNamespace(review_items=[{'status':'pending'}]),'',threading.Event(),print)
            session.assert_not_called()
        with patch.object(ai,'Session') as session:
            ai.annotate(SimpleNamespace(review_items=[{'status':'confirmed'}]),'',threading.Event(),print,True)
            session.assert_not_called()
