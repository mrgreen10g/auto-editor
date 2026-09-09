"""Windows integration: generated scoreboard video -> native OCR -> trimmed MP4."""
import json
import sys
import tempfile
import threading
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw
from hockey_editor.graphics import font
from hockey_editor.media import run, probe
from hockey_editor.model import MatchSource, EventSelection, Project, Block, EventRequest
from hockey_editor.goals import GoalScanner, cut_candidate, montage_block


def check():
    with tempfile.TemporaryDirectory(prefix='hockey-ocr-') as tmp:
        folder = Path(tmp)
        for t in range(18):
            image = Image.new('RGB', (1280, 720), '#e8f0f2'); draw = ImageDraw.Draw(image)
            draw.rectangle((30, 630, 1250, 705), fill='white')
            draw.text((55, 652), 'HOME', font=font(28, True), fill='#112634')
            draw.text((222, 647), '0 | 0' if t < 10 else '1 | 0', font=font(40, True), fill='#112634')
            draw.text((375, 652), 'AWAY', font=font(28, True), fill='#112634')
            draw.text((510, 652), '1ST', font=font(25, True), fill='#112634')
            draw.text((600, 652), f'00:{max(2,8-t):02}', font=font(28, True), fill='#112634')
            draw.rectangle((200+t*15, 300, 230+t*15, 340), fill='#152736')
            image.save(folder/f'{t:03}.png')
        video = folder/'match.mp4'
        run(['-y', '-framerate', '1', '-i', folder/'%03d.png', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', '18', '-r', '30', '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', video])
        source = MatchSource(str(video), 'HOME', 'AWAY')
        scanner = GoalScanner(folder/'cache', log=print)
        data = scanner.scan(source)
        goals = [c for c in data['candidates'] if c['kind'] == 'goal']
        print('OCR_RESULT', json.dumps({'box':data['box'], 'goals':goals, 'observations':data['observations']}))
        assert len(goals) == 1 and goals[0]['score'] == [1, 0], goals
        goal = goals[0]
        assert abs(goal['time']-6) <= 2, goal
        selected = EventSelection(goal['id'], goal['start'], goal['end'], goal['time'], data['signature'], True)
        cut = cut_candidate(source, selected, folder/'cuts', threading.Event())
        assert abs(probe(cut)['duration']-(goal['end']-goal['start'])) < .1
        assert scanner.scan(source) == data
        # Feed the accepted detection through the same cut/placement/render path as the app.
        from hockey_editor.engine import Engine
        from hockey_editor.timeline import Plan, Line, placements
        phrase = 'Команда HOME выходит вперёд после точного броска.'
        block = Block(title='HOME — AWAY', script=phrase, match_ids=[source.id],
                      events=[EventRequest(source.id, phrase, score=[1, 0], selection=selected)])
        project = Project(host=str(video), blocks=[block], matches=[source])
        prepared = montage_block(project, 0, folder/'montage', threading.Event())
        lines = [Line(phrase, 0, 18)]
        inserts, cards, warnings = placements(prepared, lines, {c.path:probe(c.path) for c in prepared.clips}, 18)
        assert len(inserts) == 1
        plan = Plan(0, 18, [(0,18)], lines, inserts, cards, warnings, 18)
        Engine(project, 0, folder/'montage', threading.Event()).render(plan, folder/'result.mp4')
        assert probe(folder/'result.mp4')['audio']
        assert abs(probe(folder/'result.mp4')['duration']-18) < .1

        report = {'status':'ok', 'checks':['native-local-ocr', 'automatic-score-region', 'clock-stop-timing', 'real-video-cut', 'scan-cache', 'detected-event-montage-export']}
        (ROOT/'build').mkdir(exist_ok=True)
        (ROOT/'build'/'ocr-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

if __name__ == '__main__': check()
