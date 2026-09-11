import unittest,tempfile,threading
from pathlib import Path
import numpy as np
from hockey_editor.model import Project,Block,Clip
from hockey_editor.timeline import keep_ranges,map_time,Line,placements,zoom_windows,Insert
from hockey_editor.alignment import subsequence_dtw,normalized,split_script
from hockey_editor.media import Cancelled

class AlignmentTests(unittest.TestCase):
    def test_locates_script_after_unrelated_intro(self):
        rng=np.random.default_rng(4)
        query=rng.normal(size=(25,13));query/=np.linalg.norm(query,axis=1,keepdims=True)
        source=np.vstack([rng.normal(size=(17,13)),query,rng.normal(size=(11,13))])
        source/=np.linalg.norm(source,axis=1,keepdims=True)
        path,_=subsequence_dtw(source.astype('f'),query.astype('f'))
        np.testing.assert_allclose(path,np.arange(25)+17,atol=.01)
    def test_variable_speaking_rate(self):
        rng=np.random.default_rng(3);q=rng.normal(size=(20,13));q/=np.linalg.norm(q,axis=1,keepdims=True)
        a=np.repeat(q,2,axis=0)
        path,_=subsequence_dtw(a.astype('f'),q.astype('f'))
        self.assertTrue(np.all(np.diff(path)>=1))
        self.assertLess(abs(path[-1]-38),1.1)
    def test_cancel(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):subsequence_dtw(np.ones((5,13)),np.ones((5,13)),cancel)
    def test_decimal_and_sentence_split(self):
        self.assertEqual(split_script('СКА — Лада\nКоэффициент 1.82. Далее матч.'),['СКА — Лада','Коэффициент 1.82.','Далее матч.'])

class TimelineTests(unittest.TestCase):
    def test_audio_and_video_use_identical_frame_ranges(self):
        keep=keep_ranges(10,[(1,2),(5,5.2),(7,7.5)])
        for a,b in keep:self.assertAlmostEqual(a*30,round(a*30));self.assertAlmostEqual(b*30,round(b*30))
        self.assertAlmostEqual(map_time(10,keep),sum(b-a for a,b in keep))
        self.assertAlmostEqual(map_time(1.5,keep),keep[0][1])
    def test_missing_phrase_not_inserted_as_wrong_goal(self):
        b=Block(clips=[Clip('clip','4:3')]);lines=[Line('Лада повела 2:1',0,3)]
        inserts,cards,warnings=placements(b,lines,{'clip':{'duration':8}},3)
        self.assertFalse(inserts);self.assertTrue(warnings)
    def test_insert_does_not_exceed_source(self):
        b=Block(clips=[Clip('clip','3:2',6)]);lines=[Line('Матч',0,1),Line('Обзор игры',1,4),Line('Лада снова повела 3:2',4,8)]
        inserts,_,_=placements(b,lines,{'clip':{'duration':7}},8)
        c=inserts[0];self.assertGreaterEqual(c.source_in,0);self.assertLessEqual(c.source_in+c.end-c.start,7.001)
    def test_zoom_avoids_clips_and_has_static_gaps(self):
        clips=[Insert('x',15,27,0,'goal')];windows=zoom_windows(70,clips)
        self.assertGreaterEqual(len(windows),3)
        for a,b,c,d in windows:self.assertFalse(a<27 and d>15);self.assertLess(a,b);self.assertLess(c,d)
        for w1,w2 in zip(windows,windows[1:]):self.assertGreaterEqual(w2[0]-w1[3],1.59)

class ProjectTests(unittest.TestCase):
    def test_relative_paths_survive_moving_whole_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'проект';folder.mkdir();(folder/'ведущий.mp4').touch()
            p=Project(host=str(folder/'ведущий.mp4'),blocks=[Block(script='Текст сценария')]);p.save(folder/'выпуск.hockeyproj')
            renamed=root/'новая папка';folder.rename(renamed)
            loaded=Project.load(renamed/'выпуск.hockeyproj')
            self.assertTrue(Path(loaded.host).samefile(renamed/'ведущий.mp4'))
            self.assertEqual(loaded.settings.zoom_max,1.2);self.assertTrue(loaded.settings.denoise)
    def test_future_version_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.hockeyproj';p.write_text('{"version":999}')
            with self.assertRaises(ValueError):Project.load(p)

if __name__=='__main__':unittest.main()
