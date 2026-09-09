"""Score changes produce reviewable candidates, never substitute another match."""
from dataclasses import dataclass, asdict
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
from .model import EventSelection, Clip
from .media import probe, run, Cancelled

SCAN_VERSION = 'score-v1'

@dataclass
class Observation:
    time: float
    score: tuple[int, int] | None
    confidence: float = 0.
    clock: int | None = None
    period: str = ''
    goal_banner: bool = False
    banner_side: int | None = None
    ice: float = 0.

@dataclass
class Candidate:
    id: str
    score: list[int] | None
    before: list[int] | None
    time: float
    start: float
    end: float
    confidence: float
    note: str = ''
    period: str = ''
    kind: str = 'goal'

    @property
    def label(self):
        label = ':'.join(map(str, self.score)) if self.score else 'Игра' if self.kind == 'play' else 'Счёт не прочитан'
        return f'{label} · {int(self.time)//60:02}:{int(self.time)%60:02}'


def source_signature(source):
    p = Path(source.path).resolve(); st = p.stat()
    data = [SCAN_VERSION, str(p), st.st_size, st.st_mtime_ns, source.score_box]
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def scan_root():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.cache'))) / 'HockeyAutoEditor' / 'Matches'


def read_image(path):
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert('RGB'))[:, :, ::-1].copy()


def event_time(observations, first, previous, step):
    recent = [o for o in observations if first.time-30 <= o.time < first.time and o.score == previous]
    if recent and recent[-1].clock is not None:
        frozen = [recent[-1]]
        for o in reversed(recent[:-1]):
            if o.clock != frozen[-1].clock or frozen[-1].time-o.time > step*1.6:
                break
            frozen.append(o)
        if len(frozen) >= 2:
            return frozen[-1].time, True
    banners = [o for o in observations if first.time-24 <= o.time <= first.time and o.goal_banner]
    if banners:
        return max(0, banners[0].time-3), False
    last = recent[-1].time if recent else first.time-step
    return max(0, (last+first.time)/2-3), False


def detect_candidates(observations, duration, step=2):
    groups = []
    for o in observations:
        if o.score is None:
            continue
        if groups and groups[-1][-1].score == o.score and o.time-groups[-1][-1].time <= 30:
            groups[-1].append(o)
        else:
            groups.append([o])
    stable = [g for g in groups if len(g) >= 2]
    result = []; baseline = None; last_group = None; seen = set()
    for i, group in enumerate(stable):
        first = group[0]; score = first.score
        if baseline is None:
            baseline = score; last_group = group; continue
        delta = [score[k]-baseline[k] for k in (0, 1)]
        if min(delta) < 0:
            continue  # A replay cannot reset the live baseline.
        if sum(delta) == 0:
            last_group = group; continue
        gap = first.time-last_group[-1].time
        when, clock_clue = event_time(observations, first, baseline, step)
        confidence = .88 if clock_clue else .72
        notes = []
        if sum(delta) != 1 or gap > 20:
            confidence = .45; notes.append('Пропуск счёта: проверьте эпизод.')
        if min(o.confidence for o in group[:2]) < .65:
            confidence = min(confidence, .72); notes.append('Цифры табло прочитаны неуверенно.')
        if i+1 < len(stable) and any(stable[i+1][0].score[k] < score[k] for k in (0, 1)):
            confidence = min(confidence, .5); notes.append('Далее счёт уменьшается: возможен повтор или отмена гола.')
        if score not in seen:
            result.append(Candidate(f'goal-{len(result)}', list(score), list(baseline), when, max(0, when-7),
                                    min(duration, when+5), confidence, ' '.join(notes), first.period))
            seen.add(score)
        baseline = score; last_group = group
    for o in observations:
        if not o.goal_banner or o.banner_side is None:
            continue
        previous = [p for p in observations if o.time-25 <= p.time < o.time and p.score is not None]
        if not previous:
            continue
        before = list(previous[-1].score); score = before.copy(); score[o.banner_side] += 1
        if any(abs(c.time-o.time) < 18 or c.score == score for c in result):
            continue
        when = max(0, o.time-3)
        result.append(Candidate(f'banner-{len(result)}', score, before, when, max(0, when-7), min(duration, when+5),
                                .55, 'Сигнал GOAL: проверьте команду и момент гола.', o.period))
    last_play = -40
    for a, b in zip(observations, observations[1:]):
        if (a.score is not None and a.score == b.score and a.clock is not None and b.clock is not None
                and 0 < abs(a.clock-b.clock) <= step+1 and min(a.ice, b.ice) > .3
                and a.time-last_play >= 40 and a.time >= 4 and a.time+8 <= duration
                and all(abs(a.time-c.time) > 20 for c in result if c.kind == 'goal')):
            result.append(Candidate(f'play-{len(result)}', None, None, a.time+3, a.time, a.time+8, .7,
                                    'Обычный игровой фрагмент. Проверьте картинку.', a.period, 'play'))
            last_play = a.time
            if sum(c.kind == 'play' for c in result) >= 40:
                break
    return sorted(result, key=lambda c: c.time)


class GoalScanner:
    def __init__(self, root=None, cancel=None, log=lambda _: None, reader=None):
        import threading
        self.root = Path(root) if root else scan_root()
        self.cancel = cancel or threading.Event(); self.log = log; self.reader = reader

    def check(self):
        if self.cancel.is_set():
            raise Cancelled('Отменено.')

    def scan(self, source):
        signature = source_signature(source)
        folder = self.root/signature[:24]; folder.mkdir(parents=True, exist_ok=True)
        saved = folder/'goals.json'
        if saved.exists():
            data = json.loads(saved.read_text(encoding='utf-8'))
            if data.get('signature') == signature:
                self.log('Использую сохранённый поиск: '+source.title)
                return data
        info = probe(source.path); duration = info['duration']
        if not info['video'] or not 5 <= duration <= 4*3600:
            raise ValueError('Нужна видеозапись матча длительностью от 5 секунд до 4 часов.')
        frames = folder/'frames'; ready = folder/'frames-ready'
        if not ready.exists():
            if frames.exists(): shutil.rmtree(frames)
            frames.mkdir()
            run(['-y', '-i', source.path, '-an', '-vf', 'fps=1/2,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                 '-q:v', '3', '-start_number', '0', frames/'%06d.jpg'], self.cancel,
                progress=lambda t: self.log(f'Кадры: {min(100,int(t/duration*100))}%'))
            ready.touch()
        files = sorted(frames.glob('*.jpg'))
        if not files: raise ValueError('Не удалось прочитать кадры матча.')
        if self.reader is None:
            from .score_ocr import ScoreReader
            self.reader = ScoreReader()
        sample = sorted(set(min(len(files)-1, n) for n in [0, 1, 3, 5, int(len(files)*.15), int(len(files)*.35), int(len(files)*.6), int(len(files)*.8)]))
        self.reader.locate([read_image(files[i]) for i in sample], self.cancel, self.log, source.score_box)
        observations = []
        for i, file in enumerate(files):
            self.check()
            observations.append(self.reader.read(read_image(file), i*2.))
            if i % 10 == 0:
                self.log(f'Поиск голов: {int((i+1)/len(files)*100)}%')
        if sum(o.score is not None for o in observations) < 2:
            raise ValueError('Счёт прочитан слишком редко. Уточните область двух цифр кнопкой «Область счёта».')
        candidates = detect_candidates(observations, duration)
        for candidate in candidates:
            if candidate.kind != 'goal': continue
            self.check(); self.log('Уточняю момент: '+candidate.label)
            detail = folder/'detail'; detail.mkdir(exist_ok=True)
            start = max(0, candidate.time-8)
            run(['-y', '-ss', start, '-t', min(16, duration-start), '-i', source.path, '-an', '-vf',
                 'fps=2,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                 '-q:v', '3', '-start_number', '0', detail/'%04d.jpg'], self.cancel)
            dense = []
            for i, file in enumerate(sorted(detail.glob('*.jpg'))):
                self.check(); dense.append(self.reader.read(read_image(file), start+i*.5))
            runs = []
            for o in dense:
                if o.clock is None or o.score is None: continue
                if runs and runs[-1][-1].clock == o.clock and o.time-runs[-1][-1].time <= .6:
                    runs[-1].append(o)
                else: runs.append([o])
            plateaus = [g for g in runs if len(g) >= 3 and abs(g[0].time-candidate.time) <= 6
                        and list(g[0].score) in (candidate.before, candidate.score)]
            if plateaus:
                candidate.time = min(plateaus, key=lambda g: abs(g[0].time-candidate.time))[0].time
            else:
                candidate.confidence = min(candidate.confidence, .72)
                candidate.note += ' Момент гола приблизительный.'
            candidate.start = max(0, candidate.time-7); candidate.end = min(duration, candidate.time+5)
            shutil.rmtree(detail)
        data = {'signature': signature, 'duration': duration, 'box': self.reader.box,
                'candidates': [asdict(c) for c in candidates], 'observations': [asdict(o) for o in observations]}
        payload = json.dumps(data, ensure_ascii=False)
        temp = saved.with_suffix('.tmp'); temp.write_text(payload, encoding='utf-8'); temp.replace(saved)
        self.log(f'Поиск готов: {sum(c.kind == "goal" for c in candidates)} голов-кандидатов.')
        return json.loads(payload)


def propose(requests, scans):
    usage = {}
    for event in requests:
        if event.skipped: continue
        data = scans.get(event.source_id)
        if not data:
            event.note = 'Запись не обработана. Проверьте журнал.'; continue
        candidates = [Candidate(**c) for c in data['candidates']]
        candidates = [c for c in candidates if (c.kind == 'play') == (event.kind == 'play')]
        if event.score is not None:
            candidates = [c for c in candidates if c.score == event.score]
        elif event.kind == 'equalizer':
            candidates = [c for c in candidates if c.score and c.score[0] == c.score[1]]
        if event.kind == 'overtime':
            ot = [c for c in candidates if 'OT' in c.period.upper() or 'ОТ' in c.period.upper()]
            if ot: candidates = ot
        if not candidates:
            event.note = 'Подходящий эпизод не найден. Выберите вручную или оставьте ведущего.'; continue
        candidates.sort(key=lambda c: (-c.confidence, c.time))
        index = usage.get(event.source_id, 0) % len(candidates) if event.kind == 'play' else 0
        c = candidates[index]; usage[event.source_id] = usage.get(event.source_id, 0)+1
        confidence = c.confidence
        if event.kind == 'overtime' and not any(x in c.period.upper() for x in ('OT', 'ОТ')):
            confidence = min(confidence, .72)
        event.selection = EventSelection(c.id, c.start, c.end, c.time, data['signature'], confidence >= .85 and not event.note)
        event.note = ' '.join(s for s in (event.note, c.note) if s)
    return requests


def unresolved(block):
    return [e for e in block.events if not e.skipped and (e.selection is None or not e.selection.accepted)]


def cut_candidate(source, selection, directory, cancel):
    if source_signature(source) != selection.source_signature:
        raise ValueError('Запись матча изменилась. Выполните поиск заново.')
    info = probe(source.path)
    if not 0 <= selection.source_start <= selection.event_time <= selection.source_end <= info['duration']+.05:
        raise ValueError('Границы эпизода выходят за запись матча.')
    duration = selection.source_end-selection.source_start
    if not .5 <= duration <= 60: raise ValueError('Длина вставки должна быть от 0,5 до 60 секунд.')
    folder = Path(directory); folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([selection.source_signature, selection.source_start, selection.source_end]).encode()).hexdigest()[:24]
    target = folder/f'goal-{key}.mp4'
    if target.exists(): return target
    temp = target.with_suffix('.partial.mp4')
    try:
        run(['-y', '-ss', selection.source_start, '-i', source.path, '-t', duration, '-an', '-vf',
             'fps=30,scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1',
             '-c:v', 'libx264', '-preset', 'fast', '-crf', '19', '-threads', '2', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', temp], cancel)
        temp.replace(target)
    finally:
        if temp.exists(): temp.unlink()
    return target


def montage_block(project, index, cache, cancel):
    block = copy.deepcopy(project.blocks[index])
    if block.match_ids and not block.events and not block.clips:
        raise ValueError('Сначала выполните поиск голов в исходных матчах.')
    if unresolved(block):
        raise ValueError(f'Проверьте найденные эпизоды: {len(unresolved(block))}. Можно оставить ведущего вместо вставки.')
    sources = {m.id: m for m in project.matches}
    for event in block.events:
        if event.skipped: continue
        selection = event.selection
        path = cut_candidate(sources[event.source_id], selection, Path(cache)/'inserts', cancel)
        block.clips.append(Clip(str(path), event.phrase, selection.event_time-selection.source_start))
    return block
