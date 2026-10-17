import copy,hashlib,hmac,json,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from hockey_editor.mini_server import validate_init,validate_url,Gateway,RemoteError
from hockey_editor.mini_bridge import Bridge
from hockey_editor.model import Project,Block,MatchSource,EventRequest,EventSelection
from hockey_editor.timeline import Plan,Card,Line

TOKEN='123:test-token';OWNER='321'
def signed(user=OWNER,date=None,token=TOKEN):
    data=dict(auth_date=str(int(time.time() if date is None else date)),user=json.dumps({'id':int(user),'first_name':'Test'}),query_id='test')
    key=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
    data['hash']=hmac.new(key,'\n'.join(k+'='+v for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(data)

def app_fixture(root):
    host=root/'host.mp4';host.write_bytes(b'fixture')
    b=Block(title='СКА — Лада',script='Команда забила три гола.');project=Project(host=str(host),blocks=[b])
    card=Card(1,4,'СТАТИСТИКА','Три гола',0,review_id='review-1')
    plan=Plan(0,8,[(0,8)],[Line(b.script,0,5)],[],[card],[],8)
    plan.review_items=[dict(id='review-1',status='pending',block_id=b.uid,script=b.script,recognized='команда забила три гола',reason='Проверить число',start=1,end=4)]
    app=SimpleNamespace(project=project,plan=plan,project_path=root/'project.hockeyproj',index=0,busy=False,result=None,scans={},log_lines=[],root=SimpleNamespace(grab_current=lambda:None),status=SimpleNamespace(get=lambda:'Готово'),cache_path=lambda:root,collect=lambda:None,refresh=lambda:None,refresh_events=lambda:None,update_summary=lambda:None)
    def display(plan):app.plan=plan;app.project.blocks[0].edit_plan=plan.to_dict()
    def invalidate():app.plan=None;app.result=None
    app.display_plan=display;app.invalidate=invalidate
    return app

class MiniAuthTests(unittest.TestCase):
    def test_valid_owner_and_reject_tampering_expiry_duplicates(self):
        self.assertEqual(validate_init(signed(),TOKEN,OWNER),OWNER)
        for data in (signed(user=999),signed(date=time.time()-700),signed(date=time.time()+60),signed(token='other'),signed()+'&auth_date=1'):
            with self.assertRaises(RemoteError):validate_init(data,TOKEN,OWNER)
    def test_https_url(self):
        self.assertEqual(validate_url('https://server.example.ts.net/'),'https://server.example.ts.net')
        for value in ('http://localhost','https://u:secret@host','https://host/path','https://host?token=x'):
            with self.assertRaises(ValueError):validate_url(value)
    def test_http_auth_media_and_unknown_paths(self):
        bridge=SimpleNamespace(request=Mock(return_value={'items':[]}))
        gateway=Gateway(bridge,dict(token=TOKEN,chat_id=OWNER,mini_url='https://example.ts.net'),port=0)
        base='http://127.0.0.1:'+str(gateway.server.server_address[1])
        def post(path,data,session='',origin=None):
            headers={'Content-Type':'application/json','Authorization':'Bearer '+session}
            if origin:headers['Origin']=origin
            return urlopen(Request(base+path,data=json.dumps(data).encode(),headers=headers),timeout=3)
        try:
            with urlopen(base) as response:self.assertIn(b'AUTO EDITOR',response.read())
            for path in ('/api/state','/api/media','/api/action'):
                with self.assertRaises(HTTPError) as error:post(path,{})
                self.assertEqual(error.exception.code,401)
            bridge.request.assert_not_called()
            with post('/api/auth',{'initData':signed()}) as response:session=json.load(response)['session']
            with post('/api/state',{},session) as response:self.assertEqual(json.load(response),{'items':[]})
            with self.assertRaises(HTTPError) as error:post('/api/action',{},session,'https://evil.example')
            self.assertEqual(error.exception.code,403)
            with self.assertRaises(HTTPError):urlopen(base+'/../../notifications.py')
        finally:gateway.close()

class MiniReviewTests(unittest.TestCase):
    def test_card_edit_persist_stale_rejection_and_undo(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));bridge=Bridge(app);revision=bridge.revision()
            detail=bridge.item(dict(id='card:review-1',revision=revision))
            self.assertEqual(detail['recognized'],'команда забила три гола')
            result=bridge.action(dict(id='card:review-1',revision=revision,decision='confirmed',text='Четыре гола',start=2,end=4))
            self.assertTrue(result['ok']);self.assertEqual(app.plan.cards[0].text,'Четыре гола')
            saved=Project.load(app.project_path);self.assertEqual(saved.blocks[0].edit_plan['cards'][0]['text'],'Четыре гола')
            with self.assertRaises(RemoteError):bridge.action(dict(id='card:review-1',revision=revision,decision='deleted'))
            bridge.action(dict(revision=bridge.revision(),decision='undo'))
            self.assertEqual(app.plan.cards[0].text,'Три гола');self.assertEqual(app.plan.review_items[0]['status'],'pending')
    def test_busy_modal_and_save_failure_do_not_apply(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));bridge=Bridge(app)
            app.busy=True
            with self.assertRaises(RemoteError):bridge.action(dict(id='card:review-1',revision=bridge.revision(),decision='deleted'))
            app.busy=False;app.root.grab_current=lambda:object()
            with self.assertRaises(RemoteError):bridge.action(dict(id='card:review-1',revision=bridge.revision(),decision='deleted'))
            app.root.grab_current=lambda:None
            with patch.object(bridge,'checkpoint',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):bridge.action(dict(id='card:review-1',revision=bridge.revision(),decision='deleted'))
            self.assertEqual(len(app.plan.cards),1)
    def test_source_change_invalidates_revision(self):
        with tempfile.TemporaryDirectory() as d:
            app=app_fixture(Path(d));bridge=Bridge(app);rev=bridge.revision()
            Path(app.project.host).write_bytes(b'changed')
            with self.assertRaises(RemoteError):bridge.item(dict(id='card:review-1',revision=rev))
    def test_clip_confirm_trim_skip_and_unknown_candidate(self):
        from hockey_editor.goals import source_signature
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=app_fixture(root);source=MatchSource(app.project.host,'СКА','Лада');app.project.matches=[source]
            block=app.project.blocks[0];block.match_ids=[source.id];event=EventRequest(source.id,'Три гола',selection=EventSelection('c',1,5,3,source_signature(source),False));block.events=[event]
            bridge=Bridge(app);ident='clip:'+block.uid+':0';detail=bridge.item(dict(id=ident,revision=bridge.revision()))
            with patch('hockey_editor.media.probe',return_value={'duration':8}):
                with self.assertRaises(RemoteError):bridge.action(dict(id=ident,revision=bridge.revision(),decision='confirmed',choice='unknown'))
                bridge.action(dict(id=ident,revision=bridge.revision(),decision='confirmed',choice=detail['choice']['key'],start=2,end=5,time=3))
            self.assertTrue(app.project.blocks[0].events[0].selection.accepted);self.assertIsNone(app.plan)
            bridge.action(dict(id=ident,revision=bridge.revision(),decision='deleted'))
            self.assertTrue(app.project.blocks[0].events[0].skipped)
    def test_queued_expired_write_is_not_executed(self):
        with tempfile.TemporaryDirectory() as d:
            bridge=Bridge(app_fixture(Path(d)));event=threading.Event();command=dict(kind='action',data={},deadline=0,event=event)
            bridge.commands.put(command);bridge.drain();self.assertTrue(event.is_set());self.assertIn('error',command)
