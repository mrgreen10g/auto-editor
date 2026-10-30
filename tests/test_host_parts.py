import unittest,time,threading
from unittest.mock import patch
import test_mobile_inputs as fixtures
from hockey_editor.mini_server import RemoteError

class HostPartsTests(unittest.TestCase):
    setUp=fixtures.InputTests.setUp
    tearDown=fixtures.InputTests.tearDown
    def links(self):return ['https://drive.google.com/file/d/abcdefghijk1/view','https://drive.google.com/file/d/abcdefghijk2/view']
    def test_queue_and_order_persist_without_touching_other_files(self):
        with patch.object(self.inputs,'launch'):
            self.inputs.host_links(dict(id=self.ident,urls=self.links()))
        d=self.inputs.load(self.ident);ids=[r['id'] for r in d['files']]
        self.inputs.host_order(dict(id=self.ident,expected=ids,order=ids[::-1]))
        self.assertEqual([r['id'] for r in self.inputs.load(self.ident)['files']],ids[::-1])
        with self.assertRaises(RemoteError):self.inputs.host_order(dict(id=self.ident,expected=ids,order=ids))
        self.assertEqual(self.inputs.summary(self.inputs.load(self.ident))['hosts'],[])
    def test_bad_batch_has_no_partial_side_effects(self):
        with self.assertRaises(ValueError):self.inputs.host_links(dict(id=self.ident,urls=[self.links()[0],'https://bad.example/x']))
        self.assertEqual(self.inputs.load(self.ident)['files'],[])
    def test_duplicate_links_do_not_duplicate_parts(self):
        with patch.object(self.inputs,'launch'):
            self.inputs.host_links(dict(id=self.ident,urls=self.links()*2))
            self.inputs.host_links(dict(id=self.ident,urls=self.links()))
        self.assertEqual(len(self.inputs.load(self.ident)['files']),2)
    def test_server_downloads_all_parts_without_client_polling(self):
        called=[]
        def fetch(item,path,update,cancel):
            called.append(item['url']);path.write_bytes(b'video')
        with patch('hockey_editor.mobile_downloads.download',side_effect=fetch),patch('hockey_editor.media.probe',return_value=dict(video=True,audio=True,duration=10)):
            self.inputs.host_links(dict(id=self.ident,urls=self.links()))
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                with self.inputs.lock:
                    rows=self.inputs.load(self.ident)['files']
                    if all(r['status']=='ready' for r in rows):break
                time.sleep(.02)
            self.assertEqual([r['status'] for r in rows],['ready','ready'])
            self.assertEqual(called,self.links())
            self.assertEqual(len(set(r['path'] for r in rows)),2)

    def test_microphone_is_optional_and_bound_to_host(self):
        d=self.inputs.load(self.ident)
        with self.assertRaises(RemoteError):self.inputs.new_file(d,dict(role='mic',block='missing',name='microphone.mov'))
        host=self.inputs.new_file(d,dict(role='host',name='camera.mp4'));host['status']='ready'
        mic=self.inputs.new_file(d,dict(role='mic',block=host['id'],name='mic.mov'))
        self.assertEqual(mic['block'],host['id'])
        with self.assertRaises(RemoteError):self.inputs.new_file(d,dict(role='mic',block=host['id'],name='other.mov'))
