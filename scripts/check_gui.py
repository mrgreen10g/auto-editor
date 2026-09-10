"""Exercise desktop state transitions on Windows, including old project files."""
import base64
import copy
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hockey_editor.gui import App
from hockey_editor.model import Project, Block, Clip, MatchSource, EventRequest, EventSelection
from hockey_editor.timeline import Plan, Line, Card
from hockey_editor.goals import source_signature, Candidate


def check():
    root = tk.Tk()
    errors = []
    root.report_callback_exception = lambda *exc: errors.append(str(exc[1]))
    app = App(root)
    out = ROOT / 'build'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='hockey-ui-') as tmp:
        tmp = Path(tmp)
        host, clip = tmp / 'presenter.mp4', tmp / 'goal.mp4'
        host.touch()
        clip.touch()
        project = Project(host=str(host), blocks=[Block(title='Тестовый разбор', script='Начинаем разбор матча. Команда выходит вперёд 2:1. Теперь посмотрим статистику бросков.', clips=[Clip(str(clip), '2:1')])])
        path = tmp / 'project.hockeyproj'
        project.version = 1
        project.save(path)
        with patch('hockey_editor.gui.filedialog.askopenfilename', return_value=str(path)):
            app.load()
        root.update()
        app.collect()
        assert app.project.version == 4 and app.project.settings.zoom_max == 1.2
        assert app.project.settings.denoise and app.project.blocks[0].clips[0].phrase == '2:1'
        assert app.page == 'materials' and 'Материалы готовы' in app.readiness.get()
        initial_script = app.project.blocks[0].script
        app.add_block()
        app.title.set('Второй разбор')
        app.script.insert('1.0', 'Другой текст сценария для проверки переключения между разборами.')
        root.update()
        app.blockbox.current(0)
        app.switch_block()
        app.collect()
        assert app.project.blocks[0].script == initial_script
        assert app.project.blocks[1].title == 'Второй разбор'
        # Use an explicit plan only to exercise the UI controller; media tests cover real exports.
        plan = Plan(0, 12, [(0, 12)], [Line('Начинаем разбор матча.', 0, 3), Line('Команда выходит вперёд 2:1.', 3, 7), Line('Теперь посмотрим статистику бросков.', 7, 12, 1.0)], [], [Card(7, 12, 'СТАТИСТИКА', 'Броски: 32 — 36', 2)], [], 12)
        app.display_plan(plan)
        app.linetable.selection_set('2')
        with patch('hockey_editor.gui.simpledialog.askstring', return_value='Броски: 30 — 35') as ask:
            app.edit_card()
            assert ask.call_args.kwargs['initialvalue'] == 'Броски: 32 — 36'
        assert app.project.blocks[0].card_overrides['2'] == 'Броски: 30 — 35'
        app.show_page('review')
        app.primary.invoke()
        assert app.page == 'export'
        app.show_page('settings')
        app.noise.set('Мягко')
        root.update()
        assert app.plan is None and not app.linetable.get_children()
        app.collect()
        assert app.project.settings.noise_reduction == 6
        app.set_busy(True)
        app.set_busy(True)
        assert all(str(w.cget('state')) == 'disabled' for w in app.controls)
        app.show_page('materials')
        app.set_busy(False)
        assert str(app.blockbox.cget('state')) == 'readonly'
        assert str(app.script.cget('state')) == 'normal'
        assert str(app.primary.cget('state')) == 'normal'
        # Exercise actual button -> worker -> queue -> review/export flow without rendering again.
        class FakeEngine:
            def __init__(self, project, *args):
                self.project = project
                assert project is not app.project
            def analyze(self):
                return copy.deepcopy(plan)
            def render(self, value, target):
                Path(target).touch()
                return Path(target)
        def drain():
            deadline = time.monotonic() + 5
            while app.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(.02)
            assert not app.busy
            root.update()
        with patch('hockey_editor.gui.Engine', FakeEngine), patch.object(app, 'cache_path', return_value=tmp / 'cache'):
            app.start(False)
            drain()
            assert app.page == 'review' and app.plan is not None
            target = tmp / 'result.mp4'
            with patch('hockey_editor.gui.filedialog.asksaveasfilename', return_value=str(target)):
                app.start(True)
                drain()
            assert app.result == target and app.page == 'export'
            assert str(app.previewbutton.cget('state')) == 'normal'
        app.script.insert('end', '\nЕщё одна фраза.')
        root.update()
        assert app.plan is None and app.result is None
        assert str(app.previewbutton.cget('state')) == 'disabled'
        # Multiple sources and the scan-result queue must preserve source identity.
        first = MatchSource(str(clip), 'СКА', 'Лада', 'Тест 1')
        second = MatchSource(str(host), 'СКА', 'Динамо', 'Тест 2')
        app.project.matches = [first, second]
        app.project.blocks[0].match_ids = [first.id, second.id]
        event = EventRequest(first.id, 'Команда выходит вперёд 2:1.', score=[2, 1],
                             selection=EventSelection('test', 2, 8, 5, source_signature(first)))
        app.refresh()
        assert len(app.matchtable.get_children()) == 2
        app.handle_match_job('goals', ([event], {}, []))
        assert 'Проверить' in app.primary.cget('text')
        assert len(app.eventtable.get_children()) == 1
        app.eventtable.selection_set('0')
        app.scans[first.id] = {'signature': source_signature(first), 'duration': 12,
                              'candidates': [vars(Candidate('test', [2,1], [1,1], 6, 1, 9, .7))]}
        app.edit_event()
        root.update()
        dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
        assert len(dialogs) == 1
        def descendants(widget):
            return [child for w in widget.winfo_children() for child in [w, *descendants(w)]]
        fields = [w.get() for w in descendants(dialogs[0]) if w.winfo_class() == 'TEntry']
        assert fields == ['2.00', '8.00', '5.00'], fields
        dialogs[0].destroy()
        app.skip_event()
        assert event.skipped
        app.project.blocks[1].match_ids = [first.id]
        assert app.project.blocks[1].match_ids[0] == app.project.blocks[0].match_ids[0]
        saved = tmp / 'v2.hockeyproj'
        app.project.save(saved)
        restored = Project.load(saved)
        assert len(restored.matches) == 2 and restored.blocks[0].events[0].skipped
        # Real timeline editing, rendered audiovisual preview, and retained export plan.
        from hockey_editor.timeline_ui import TimelineEditor
        from hockey_editor.timeline import Insert
        from hockey_editor.editing import saved_plan
        from hockey_editor.media import run
        run(['-y','-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=12','-f','lavfi','-i','sine=f=220:r=16000:d=12',
             '-t','12','-c:v','libx264','-c:a','aac',host])
        run(['-y','-f','lavfi','-i','color=c=red:s=320x180:r=30:d=8','-c:v','libx264',clip])
        app.project=Project(host=str(host),blocks=[Block(title='СКА — Лада',script='Текст для проверки редактирования дорожки и предпросмотра.')])
        app.index=0;app.refresh()
        edited_plan=Plan(0,12,[(0,12)],[Line('Текст',0,12)],
            [Insert(str(clip),6,9,1,'Игра',source_min=.5,source_max=7)],
            [Card(0,5,'РАЗБОР МАТЧА','СКА — Лада'),Card(9,12,'ПРОГНОЗ','Лада\nФора (+2)')],[],12,0)
        app.display_plan(edited_plan);editor=TimelineEditor(app);root.update()
        editor.select(('insert',0))
        for (var,_),value in zip(editor.fields,('5.5','8.5','1.5')):var.set(value)
        editor.edit();assert editor.plan.inserts[0].start==5.5
        editor.undo();assert editor.plan.inserts[0].start==6
        editor.redo();assert editor.plan.inserts[0].start==5.5
        editor.select(('card',1));editor.text.delete('1.0','end');editor.text.insert('1.0','Лада +2');editor.edit()
        editor.apply();assert saved_plan(app.project,0).cards[1].text=='Лада +2'
        with patch.object(app,'cache_path',return_value=tmp/'editor-cache'):
            editor.build_preview()
            deadline=time.monotonic()+120
            while editor.busy and time.monotonic()<deadline:root.update();time.sleep(.03)
        assert not editor.busy and editor.preview_current,editor.status.get()
        editor.player.seek(1,True)
        deadline=time.monotonic()+8
        while editor.player.position<1.5 and time.monotonic()<deadline:root.update();time.sleep(.03)
        assert editor.player.image is not None and editor.player.position>=1.5
        editor.player.stop()
        from PIL import ImageGrab
        bounds=(editor.window.winfo_rootx(),editor.window.winfo_rooty(),editor.window.winfo_rootx()+editor.window.winfo_width(),editor.window.winfo_rooty()+editor.window.winfo_height())
        ImageGrab.grab(bbox=bounds).convert('RGB').save(out/'gui-timeline.jpg',quality=80)
        data=base64.b64encode((out/'gui-timeline.jpg').read_bytes()).decode()
        print('TIMELINE_PREVIEW_START')
        for offset in range(0,len(data),4000):print(data[offset:offset+4000])
        print('TIMELINE_PREVIEW_END')
        editor.close()
        file=tmp/'edited.hockeyproj';app.project.save(file)
        loaded=Project.load(file);assert saved_plan(loaded,0).inserts[0].start==5.5
        # Screenshots contain synthetic data only, never user files or scripts.
        root.geometry(f'{min(1220, root.winfo_screenwidth()-60)}x{min(860, root.winfo_screenheight()-100)}+20+20')
        app.show_page('materials')
        root.update()
        from PIL import ImageGrab
        for key in ('materials', 'review', 'settings'):
            if key == 'review':
                app.display_plan(plan)
            app.show_page(key)
            root.update()
            root.lift()
            time.sleep(.15)
            bounds = (root.winfo_rootx(), root.winfo_rooty(), root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height())
            ImageGrab.grab(bbox=bounds).convert('RGB').save(out / f'gui-{key}.jpg', quality=80)
        data = base64.b64encode((out / 'gui-materials.jpg').read_bytes()).decode()
        print('GUI_PREVIEW_START')
        for i in range(0, len(data), 4000): print(data[i:i+4000])
        print('GUI_PREVIEW_END')
        root.geometry('960x640')
        for key in ('materials', 'review', 'export', 'settings'):
            app.show_page(key)
            root.update()
            for widget in (app.primary, app.cancelbutton, app.heading):
                assert widget.winfo_ismapped(), (key, str(widget), root.geometry())
                assert widget.winfo_rootx() + widget.winfo_width() <= root.winfo_rootx() + root.winfo_width() + 1
                assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height() + 1
        assert not errors, errors
        app.close()
    (out / 'gui-check.json').write_text(json.dumps({'status': 'ok', 'checks': ['v1-project-compatibility', 'block-switching', 'card-editing', 'stale-plan-invalidation', 'busy-control-restoration', 'worker-queue-flow', 'compact-window-layout', 'multiple-source-review-flow', 'v2-project-roundtrip', 'review-retains-custom-trim']}, indent=2), encoding='utf-8')
    print('Desktop workflow and layout checks passed.')


if __name__ == '__main__':
    check()
