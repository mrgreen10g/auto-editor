import hashlib,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from test_mini_app import app_fixture,signed,TOKEN,OWNER
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_server import Gateway,RemoteError,byte_range
from hockey_editor import drive_upload as drive

class StreamTests(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(byte_range('bytes=2-4',10),(2,4,True))
        self.assertEqual(byte_range('bytes=-3',10),(7,9,True))
        self.assertEqual(byte_range('bytes=8-',10),(8,9,True))
        for value in ('bytes=20-','bytes=3-2','bytes=0-1,3-4','bytes=-0'):
            with self.assertRaises(RemoteError):byte_range(value,10)
    def test_http_stream_auth_seek_expiry_and_changed_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=app_fixture(root);bridge=Bridge(app)
            video=root/'result.mp4';video.write_bytes(b'0123456789')
            row=bridge.results.register(video)
            # Main-thread bridge is synchronous in this isolated protocol test.
            bridge.request=bridge.handle
            gateway=Gateway(bridge,dict(token=TOKEN,chat_id=OWNER,mini_url='https://test.ts.net'),port=0)
            base='http://127.0.0.1:'+str(gateway.server.server_address[1])
            def post(route,data,token=''):
                return urlopen(Request(base+'/api/'+route,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token}),timeout=3)
            try:
                with self.assertRaises(HTTPError):post('result-stream',{'id':row['id']})
                with post('auth',{'initData':signed()}) as response:token=json.load(response)['session']
                with post('result-stream',{'id':row['id']},token) as response:url=json.load(response)['url']
                with urlopen(Request(base+url,headers={'Range':'bytes=2-5'})) as response:
                    self.assertEqual(response.status,206);self.assertEqual(response.read(),b'2345');self.assertEqual(response.headers['Content-Range'],'bytes 2-5/10')
                with urlopen(Request(base+url,method='HEAD')) as response:self.assertEqual(response.headers['Content-Length'],'10')
                with self.assertRaises(HTTPError) as error:urlopen(Request(base+url,headers={'Range':'bytes=99-'}))
                self.assertEqual(error.exception.code,416)
                with self.assertRaises(HTTPError):post('result-stream',{'id':'../../host.mp4'},token)
                video.write_bytes(b'changed video')
                with self.assertRaises(HTTPError) as error:urlopen(base+url)
                self.assertEqual(error.exception.code,409)
                gateway.sessions.clear()
                with self.assertRaises(HTTPError) as error:urlopen(base+url)
                self.assertEqual(error.exception.code,401)
            finally:gateway.close()
    def test_results_survive_restart_and_hide_transfer_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);app=app_fixture(root);bridge=Bridge(app);target=root/'ready.mp4';target.write_bytes(b'movie')
            row=bridge.results.register(target);rows=bridge.results.records()
            rows[0]['upload']={'status':'uploading','session':'private-session','file_id':'private-id','account_key':'secret','message':'Uploading'}
            drive.write(bridge.results.file(),rows)
            restored=Bridge(app).results.status()['results'][0]
            self.assertEqual(restored['id'],row['id']);self.assertEqual(restored['upload']['status'],'paused')
            self.assertNotIn('private',json.dumps(restored));self.assertNotIn('path',restored)

class Response:
    def __init__(self,status=200,data=None,headers=None):self.status_code=status;self.data=data or {};self.headers=headers or {}
    def json(self):return self.data

class DriveTests(unittest.TestCase):
    def test_folder_mapping(self):
        self.assertEqual(drive.folder_id('https://drive.google.com/drive/u/0/folders/abcdefghijk?usp=sharing'),'abcdefghijk')
        self.assertEqual([drive.destination(p) for p in ('ru_hockey','uz_football','ru_hockey_shorts','uz_hockey_shorts')],['ru_long','uz_long','ru_shorts','uz_shorts'])
        for value in ('https://evil.test/drive/folders/abcdefghijk','https://drive.google.com/file/d/abcdefghijk/view','../file'):
            with self.assertRaises(ValueError):drive.folder_id(value)
    def test_resume_after_lost_final_reply_without_duplicate_file(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'video.mp4';content=b'a'*(8*1024*1024)+b'end';path.write_bytes(content)
            job={'path':str(path),'identity':[path.stat().st_size,path.stat().st_mtime_ns],'folder':'abcdefghijk'}
            calls=[];completed=False;checkpoint={}
            def save(value):
                snapshot=json.loads(json.dumps(value));checkpoint.clear();checkpoint.update(snapshot)
            def request(method,url,**kw):
                nonlocal completed
                calls.append((method,url,kw))
                if url.endswith('/files/abcdefghijk'):return Response(data={'name':'РУ лонги','mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True}})
                if url.endswith('/generateIds'):return Response(data={'ids':['generated-file']})
                if url.endswith('/files/generated-file'):
                    return Response(data={'id':'generated-file','size':str(len(content)),'md5Checksum':hashlib.md5(content).hexdigest()}) if completed else Response(404)
                if method=='POST':return Response(headers={'Location':drive.UPLOAD+'?upload_id=test'})
                if method=='PUT':
                    header=kw['headers']['Content-Range']
                    if header.startswith('bytes 0-'):return Response(308,headers={'Range':'bytes=0-8388607'})
                    completed=True;raise TimeoutError('Lost final reply')
                raise AssertionError((method,url))
            client=SimpleNamespace(request=request,close=lambda:None)
            with patch.object(drive,'secret',side_effect=lambda value,decode=False:value):
                with self.assertRaises(TimeoutError):drive.upload(job,save,threading.Event(),lambda:(client,'account'))
                self.assertEqual(checkpoint['uploaded'],8388608)
                drive.upload(checkpoint,save,threading.Event(),lambda:(client,'account'))
            self.assertEqual(checkpoint['status'],'completed')
            self.assertEqual(sum(method=='POST' for method,_,_ in calls),1)
            self.assertEqual(sum('/generateIds' in url for _,url,_ in calls),1)
    def test_resume_queries_acknowledged_offset_and_rejects_other_account(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'v.mp4';path.write_bytes(b'abcdef')
            job=dict(path=str(path),identity=[6,path.stat().st_mtime_ns],folder='abcdefghijk',account_key='old')
            client=SimpleNamespace(request=Mock(),close=Mock())
            with self.assertRaises(ValueError):drive.upload(job,Mock(),threading.Event(),lambda:(client,'other'))
            client.request.assert_not_called()
            job.update(account_key='old',file_id='file',md5=hashlib.md5(b'abcdef').hexdigest(),session=drive.UPLOAD+'?upload_id=resume')
            replies=[Response(data={'name':'Folder','mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True}}),Response(404),Response(308,headers={'Range':'bytes=0-2'}),Response(200),Response(data={'size':'6','md5Checksum':job['md5']})]
            client.request=Mock(side_effect=replies)
            with patch.object(drive,'secret',side_effect=lambda value,decode=False:value):
                drive.upload(job,Mock(),threading.Event(),lambda:(client,'old'))
            self.assertEqual(client.request.call_args_list[3].kwargs['data'],b'def')
            self.assertEqual(job['status'],'completed')
