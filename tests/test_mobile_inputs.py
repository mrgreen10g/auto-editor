import hashlib,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from hockey_editor.mobile_inputs import Inputs,name,CHUNK
from hockey_editor.mobile_downloads import canonical,drive_download
from hockey_editor.mini_bridge import Bridge
from hockey_editor.mini_server import Gateway,RemoteError
from hockey_editor.model import Block,Project
from test_mini_app import app_fixture,signed,TOKEN,OWNER

class InputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.app=app_fixture(self.root);self.bridge=Bridge(self.app)
        self.inputs=Inputs(self.bridge,self.root/'index.json');self.bridge.inputs=self.inputs
        self.ident=self.inputs.create(dict(parent=str(self.root),name='Выпуск',profile='ru_hockey',request='request-123'))['id']
    def tearDown(self):
        self.inputs.cancel.set()
        if self.inputs.worker:self.inputs.worker.join(5)
        self.tmp.cleanup()
    def upload(self,content=b'abcdef',role='host',filename='host.mp4'):
        return self.inputs.upload_init(dict(id=self.ident,name=filename,size=len(content),fingerprint=hashlib.sha256(content).hexdigest(),role=role))
    def parse(self):
        with patch('hockey_editor.folder_import.parse_episode',return_value=(Block(title='Начало',kind='intro'),[Block(title='СКА — Лада')],Block(title='Конец',kind='outro'))):self.inputs.script(dict(id=self.ident,text='Полный тестовый сценарий.'))
    def test_names_and_persistent_draft_idempotence(self):
        for value in ('../outside','CON','x/y','NUL.mp4','a.','x:y'):
            with self.assertRaises(RemoteError):name(value)
        same=self.inputs.create(dict(parent=str(self.root),name='Выпуск',profile='ru_hockey',request='request-123'))
        self.assertEqual(same['id'],self.ident)
        other=Inputs(self.bridge,self.root/'index.json');self.assertEqual(other.load(self.ident)['name'],'Выпуск')
        with self.assertRaises(RemoteError):self.inputs.create(dict(parent=str(self.root),name='Выпуск',profile='ru_hockey',request='another-123'))
    def test_chunk_retry_resume_and_different_file_rejection(self):
        row=self.upload();data=dict(id=self.ident,file=row['file'],offset=0)
        self.assertEqual(self.inputs.chunk(data,b'abc')['offset'],3)
        self.assertEqual(self.inputs.chunk(data,b'abc')['offset'],3)
        with self.assertRaises(RemoteError):self.inputs.chunk(data,b'xyz')
        self.assertEqual(self.upload()['offset'],3)
        with self.assertRaises(RemoteError):self.inputs.chunk(dict(data,offset=5),b'f')
        self.inputs.chunk(dict(data,offset=3),b'def')
        with patch('hockey_editor.media.probe',return_value={'video':True,'audio':True,'duration':1}):
            self.inputs.finish(data);self.inputs.worker.join(5)
        d=self.inputs.load(self.ident);self.assertEqual(d['files'][0]['status'],'ready');self.assertEqual(Path(d['files'][0]['path']).read_bytes(),b'abcdef')
        self.assertTrue(self.upload()['ready'])
    def test_text_upload_and_no_silent_overwrite_of_assigned_script(self):
        content='Тест сценария'.encode();row=self.upload(content,'script','text.txt');data=dict(id=self.ident,file=row['file'],offset=0);self.inputs.chunk(data,content)
        with patch('hockey_editor.folder_import.parse_episode',return_value=(Block(kind='intro'),[Block(title='СКА — Лада')],Block(kind='outro'))):
            self.inputs.finish(data);self.inputs.worker.join(5)
        d=self.inputs.load(self.ident);self.assertEqual(d['script'],'Тест сценария');self.assertEqual(d['files'][0]['status'],'ready')
        d['files'].append(dict(role='match',status='paused'));self.inputs.save(d)
        with self.assertRaises(RemoteError):self.inputs.script(dict(id=self.ident,text='Иной сценарий'))
    def test_activate_keeps_current_project_and_archive_identity(self):
        self.parse();row=self.upload();data=dict(id=self.ident,file=row['file'],offset=0);self.inputs.chunk(data,b'abcdef')
        with patch('hockey_editor.media.probe',return_value={'video':True,'audio':True,'duration':1}):self.inputs.finish(data);self.inputs.worker.join(5)
        d=self.inputs.load(self.ident);source=self.root/'archive.mp4';source.write_bytes(b'match')
        d['files'].append(dict(id='match1',role='match',block=d['blocks'][0]['uid'],name='Archive',status='ready',path=str(source),home='ЦСКА',away='Спартак',fighter=''));self.inputs.save(d)
        original=self.app.project.blocks[0].script;self.app.restore_plan=Mock();self.app.status.set=Mock()
        result=self.inputs.activate(dict(id=self.ident,revision=self.bridge.revision()))
        self.assertTrue(Path(result['project']).is_file());self.assertEqual(Project.load(self.root/'project.hockeyproj').blocks[0].script,original)
        self.assertEqual(self.app.project.matches[0].home,'ЦСКА');self.assertEqual(self.app.project.blocks[0].title,'СКА — Лада')
        with self.assertRaises(RemoteError):self.inputs.script(dict(id=self.ident,text='new'))
    def test_http_binary_requires_owner_and_origin(self):
        row=self.upload();g=Gateway(self.bridge,dict(token=TOKEN,chat_id=OWNER,mini_url='https://test.ts.net'),port=0)
        base='http://127.0.0.1:'+str(g.server.server_address[1]);session=g.login(signed())
        headers={'Content-Type':'application/octet-stream','X-Draft':self.ident,'X-File':row['file'],'X-Offset':'0'}
        try:
            with self.assertRaises(HTTPError) as error:urlopen(Request(base+'/api/input-chunk',data=b'abc',headers=headers))
            self.assertEqual(error.exception.code,401)
            headers['Authorization']='Bearer '+session;headers['Origin']='https://evil.test'
            with self.assertRaises(HTTPError) as error:urlopen(Request(base+'/api/input-chunk',data=b'abc',headers=headers))
            self.assertEqual(error.exception.code,403);headers.pop('Origin')
            with urlopen(Request(base+'/api/input-chunk',data=b'abc',headers=headers)) as result:self.assertEqual(json.load(result)['offset'],3)
        finally:g.close()
    def test_url_allowlist(self):
        self.assertEqual(canonical('https://youtu.be/abcdefghijk?t=3'),('youtube','https://www.youtube.com/watch?v=abcdefghijk'))
        self.assertEqual(canonical('https://drive.google.com/file/d/abcdefghijkl/view?usp=sharing')[0],'drive')
        for url in ('http://youtube.com/watch?v=abcdefghijk','https://evil.test/file','https://youtube.com.evil.test/watch?v=abcdefghijk','https://youtube.com/playlist?list=test','https://user@youtube.com/watch?v=abcdefghijk','file:///etc/passwd','https://127.0.0.1/'):
            with self.assertRaises(ValueError):canonical(url)
    def test_reuse_keeps_original_path_for_analysis_cache(self):
        self.parse();d=self.inputs.load(self.ident);path=self.root/'archived.mp4';path.write_bytes(b'archive')
        d['files'].append(dict(id='oldmatch',role='match',block=d['blocks'][0]['uid'],name='Archive.mp4',status='ready',path=str(path),home='Амур',away='ЦСКА',fighter=''));self.inputs.save(d)
        old=self.ident;self.ident=self.inputs.create(dict(parent=str(self.root),name='Shorts',profile='ru_hockey',request='shorts-123'))['id'];self.parse()
        block=self.inputs.load(self.ident)['blocks'][0]['uid'];payload=dict(id=self.ident,from_draft=old,file='oldmatch',block=block)
        self.inputs.reuse(payload);self.inputs.reuse(payload)
        files=self.inputs.load(self.ident)['files'];self.assertEqual(len(files),1);self.assertEqual(files[0]['path'],str(path));self.assertEqual(files[0]['home'],'Амур')
    def test_drive_range_resume_and_checksum(self):
        content=b'abcdef';path=self.root/'download.mp4';path.write_bytes(b'abc');calls=[]
        class Response:
            def __init__(self,meta=False):self.status_code=200 if meta else 206;self.headers={} if meta else {'Content-Range':'bytes 3-5/6'}
            def json(self):return dict(mimeType='video/mp4',size='6',md5Checksum=hashlib.md5(content).hexdigest(),modifiedTime='stamp',capabilities={'canDownload':True})
            def iter_content(self,*a):yield b'def'
            def __enter__(self):return self
            def __exit__(self,*a):pass
        class Client:
            def get(self,url,**kw):calls.append(kw);return Response(meta='fields' in kw['params'])
            def close(self):pass
        item=dict(url='https://drive.google.com/file/d/abcdefghijkl/view');updates=[]
        with patch('hockey_editor.drive_upload.session',return_value=(Client(),'account')):drive_download(item,path,lambda **kw:updates.append(kw),threading.Event())
        self.assertEqual(path.read_bytes(),content);self.assertEqual(calls[1]['headers']['Range'],'bytes=3-5');self.assertEqual(updates[-1]['received'],6)

if __name__=='__main__':unittest.main()
