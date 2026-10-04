import copy,json,tempfile,threading,unittest
from pathlib import Path
from PIL import Image
from hockey_editor.model import Project,Block,Settings
from hockey_editor.timeline import Line,Plan,Card
from hockey_editor.subtitles import cut_words,caption_events,write_ass
from hockey_editor.media import run,probe
from hockey_editor.engine import Engine
from hockey_editor.live_cards import base_key

class SubtitleTests(unittest.TestCase):
    def test_cut_words_follow_removed_pause(self):
        old=Line('Первое второе',10,14,words=[dict(word='Первое',start=0,end=1),dict(word='второе',start=3,end=4)])
        line=Line(old.text,0,2)
        self.assertEqual(cut_words(old,line,10,[(0,1),(3,4)]),[dict(word='Первое',start=0,end=1),dict(word='второе',start=1,end=2)])

    def test_word_highlight_and_promo_exclusion_survive_serialization(self):
        line=Line('Три точных слова',0,3,words=[dict(word=w,start=i,end=i+1) for i,w in enumerate('Три точных слова'.split())])
        plan=Plan(0,3,[(0,3)],[line],[],[Card(1,2,'ТЕЛЕГРАМ','tg',asset='tg')],[],3)
        events=caption_events(plan)
        self.assertEqual([e['words'][e['active']] for e in events],['Три','слова'])
        self.assertTrue(all(e['end']<=1 or e['start']>=2 for e in events))
        self.assertEqual(caption_events(Plan.from_dict(json.loads(json.dumps(plan.to_dict())))),events)
        moved=copy.deepcopy(plan);moved.lines[0].start+=5;moved.lines[0].end+=5;moved.duration=8
        self.assertEqual(caption_events(moved)[0]['start'],5)

    def test_setting_roundtrips_in_project_and_preset(self):
        from hockey_editor.preferences import save_preset,apply_preset
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);p=Project(profile='ru_hockey_shorts');p.settings.subtitles=True
            p.save(d/'project.hockeyproj')
            self.assertTrue(Project.load(d/'project.hockeyproj').settings.subtitles)
            save_preset(p,'Shorts',d/'presets.json');p.settings.subtitles=False
            apply_preset(p,'Shorts',d/'presets.json');self.assertTrue(p.settings.subtitles)

    def test_legacy_phrases_have_no_fake_word_highlight(self):
        plan=Plan(0,4,[(0,4)],[Line('Старый сохранённый проект',0,4)],[],[],[],4)
        events=caption_events(plan);self.assertTrue(events);self.assertTrue(all(e['active']==-1 for e in events))

    def test_toggle_and_words_invalidate_preview(self):
        p=Project(profile='ru_hockey_shorts');plan=Plan(0,2,[(0,2)],[Line('Речь',0,2)],[],[],[],2)
        before=base_key(plan,p);p.settings.subtitles=True
        self.assertNotEqual(base_key(plan,p),before)
        before=base_key(plan,p);plan.lines[0].words=[dict(word='Правка',start=.2,end=1)]
        self.assertNotEqual(base_key(plan,p),before)

    def test_ass_text_cannot_inject_overrides(self):
        with tempfile.TemporaryDirectory() as d:
            plan=Plan(0,1,[(0,1)],[Line(r'{\pos(0,0)}текст',0,1)],[],[],[],1)
            path=Path(d)/'captions.ass';write_ass(plan,path)
            self.assertNotIn(r'{\pos(0,0)}',path.read_text(encoding='utf-8-sig'))

    def test_real_export_with_apostrophe_path_and_optional_captions(self):
        with tempfile.TemporaryDirectory(prefix="captions'") as folder:
            d=Path(folder)
            run(['-y','-f','lavfi','-i','color=c=blue:s=180x320:r=30:d=2','-f','lavfi','-i','sine=f=220:r=48000:d=2','-t',2,'-c:v','libx264','-c:a','aac',d/'host.mp4'])
            p=Project(host=str(d/'host.mp4'),profile='ru_hockey_shorts',blocks=[Block(script='Прогноз на матч команд сегодня.')],settings=Settings(width=720,height=1280,auto_rotate=False,zoom=False,denoise=False,color=False,subtitles=True))
            words=[dict(word=w,start=i*.5,end=(i+1)*.5) for i,w in enumerate('Жду победу в матче'.split())]
            plan=Plan(0,2,[(0,2)],[Line('Жду победу в матче',0,2,words=words)],[],[],[],2,0)
            engine=Engine(p,0,d/'cache',threading.Event())
            for on in (True,False):
                p.settings.subtitles=on;target=d/f'output-{on}.mp4';engine.render(plan,target,draft=True)
                self.assertEqual((probe(target)['width'],probe(target)['height']),(360,640))
                image=d/f'frame-{on}.png';run(['-y','-ss',.7,'-i',target,'-frames:v',1,image])
                with Image.open(image) as im:
                    bright=sum(r>150 and g>130 for r,g,b in im.crop((20,570,330,615)).getdata())
                if on:self.assertGreater(bright,100)
                else:self.assertEqual(bright,0)

if __name__=='__main__':unittest.main()
