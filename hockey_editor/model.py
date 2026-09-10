"""Portable, versioned projects. Media stays on the user's computer."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json, math, os, uuid

@dataclass
class Clip:
    path: str
    phrase: str
    goal_time: float | None = None
    context_label: str = ''
    origin_path: str = ''
    origin_start: float = 0.
    kind: str = 'score'
    flexible_source: bool = False

@dataclass
class MatchSource:
    path: str
    home: str
    away: str
    date: str = ''
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    score_box: list[float] | None = None

    @property
    def title(self):
        return f'{self.home} — {self.away}' + (f' · {self.date}' if self.date else '')

@dataclass
class EventSelection:
    candidate_id: str
    source_start: float
    source_end: float
    event_time: float
    source_signature: str
    accepted: bool = False
    context_label: str = ''

@dataclass
class EventRequest:
    source_id: str
    phrase: str
    kind: str = 'score'
    score: list[int] | None = None
    selection: EventSelection | None = None
    skipped: bool = False
    note: str = ''
    requested_teams: list[str] = field(default_factory=list)
    flexible_source: bool = False

@dataclass
class Settings:
    rotate: int = 0
    auto_rotate: bool = True
    use_manual_clips: bool = False
    allow_other_matches: bool = True
    insert_frequency: str = 'normal'
    zoom_max: float = 1.20
    zoom: bool = True
    transitions: bool = True
    animate_cards: bool = True
    wobble: bool = True
    denoise: bool = True
    noise_reduction: int = 10
    cut_pauses: bool = True
    color: bool = True
    music_db: float = -28.0
    width: int = 1280
    height: int = 720
    fps: int = 30

@dataclass
class Block:
    title: str = 'Новый разбор'
    script: str = ''
    clips: list[Clip] = field(default_factory=list)
    card_overrides: dict[str, str] = field(default_factory=dict)
    match_ids: list[str] = field(default_factory=list)
    events: list[EventRequest] = field(default_factory=list)
    edit_plan: dict | None = None
    edit_key: str = ''

@dataclass
class Project:
    version: int = 4
    host: str = ''
    music: str = ''
    blocks: list[Block] = field(default_factory=lambda: [Block()])
    settings: Settings = field(default_factory=Settings)
    matches: list[MatchSource] = field(default_factory=list)
    team_logos: dict[str, str] = field(default_factory=dict)

    def validate(self, index=0):
        if not self.host or not Path(self.host).is_file():
            raise ValueError('Выберите существующий файл ведущего.')
        if not 0 <= index < len(self.blocks):
            raise ValueError('Выберите разбор.')
        block = self.blocks[index]
        if len(block.script.strip()) < 30:
            raise ValueError('Вставьте сценарий выбранного разбора.')
        if self.music and not Path(self.music).is_file():
            raise ValueError('Музыка не найдена. Выберите файл заново или очистите поле.')
        for c in block.clips if self.settings.use_manual_clips else []:
            if not Path(c.path).is_file():
                raise ValueError(f'Не найден игровой фрагмент: {c.path}')
            if not c.phrase.strip():
                raise ValueError('Для каждой вставки укажите слова из сценария, например 3:2.')
            if c.goal_time is not None and (not math.isfinite(c.goal_time) or c.goal_time < 0):
                raise ValueError('Некорректное положение события внутри вставки.')
        ids = {m.id: m for m in self.matches}
        if len(ids) != len(self.matches):
            raise ValueError('Повторяющиеся идентификаторы записей матча.')
        used_sources={e.source_id for e in block.events if e.selection and not e.skipped}
        for ident in block.match_ids:
            if ident not in ids:
                raise ValueError('Не найдена запись матча в проекте.')
            m = ids[ident]
            if (ident in used_sources and not Path(m.path).is_file()) or not m.home.strip() or not m.away.strip():
                raise ValueError('Проверьте файл и названия команд: ' + m.title)
            box = m.score_box
            if box is not None and (len(box) != 4 or not all(math.isfinite(v) for v in box)
                    or not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1):
                raise ValueError('Некорректная область табло.')
        for event in block.events:
            if event.source_id not in block.match_ids and not (not event.source_id and (event.skipped or event.selection is None)):
                raise ValueError('Событие относится к записи вне этого разбора.')
            if event.kind not in ('score', 'equalizer', 'overtime', 'play'):
                raise ValueError('Неизвестный тип события.')
            if event.score is not None and (len(event.score) != 2 or any(type(n) is not int or not 0 <= n <= 15 for n in event.score)):
                raise ValueError('Некорректный счёт события.')
            c = event.selection
            if c and (not all(math.isfinite(v) for v in (c.source_start, c.event_time, c.source_end))
                      or not 0 <= c.source_start <= c.event_time <= c.source_end or c.source_end <= c.source_start):
                raise ValueError('Некорректные границы игрового эпизода.')
        s = self.settings
        if s.insert_frequency not in ('low','normal','high'):
            raise ValueError('Неизвестная частота вставок.')
        if not 1 <= s.zoom_max <= 1.4 or not 1 <= s.noise_reduction <= 20:
            raise ValueError('Некорректная настройка масштаба или очистки звука.')
        if s.rotate not in (0, 90, 180, 270):
            raise ValueError('Поворот должен быть 0, 90, 180 или 270 градусов.')
        if (s.width, s.height, s.fps) not in [(1280,720,30),(1920,1080,30)]:
            raise ValueError('Поддерживается 720p или 1080p при 30 кадрах/с.')
        if not math.isfinite(s.music_db) or not -60 <= s.music_db <= -15:
            raise ValueError('Громкость музыки должна быть от −60 до −15 дБ.')

    def save(self, filename):
        target = Path(filename).resolve()
        data = asdict(self)
        def relative(s):
            if not s: return ''
            try: return os.path.relpath(Path(s).resolve(), target.parent)
            except ValueError: return str(Path(s).resolve())
        for key in ('host','music'): data[key] = relative(data[key])
        data['team_logos'] = {name: relative(path) for name, path in self.team_logos.items()}
        for match in data['matches']: match['path'] = relative(match['path'])
        for block in data['blocks']:
            for c in block['clips']:
                c['path'] = relative(c['path'])
                c['origin_path'] = relative(c.get('origin_path',''))
            if block.get('edit_plan'):
                for c in block['edit_plan']['inserts']: c['path'] = relative(c['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix+'.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(target)

    @classmethod
    def load(cls, filename):
        p = Path(filename).resolve()
        data = json.loads(p.read_text(encoding='utf-8'))
        if data.get('version') not in (1, 2, 3, 4): raise ValueError('Версия проекта не поддерживается.')
        def resolve(s):
            if not s: return ''
            return str((p.parent / s).resolve())
        blocks = [Block(title=b['title'],script=b['script'],
                  clips=[Clip(**{**c,'path':resolve(c['path']),'origin_path':resolve(c.get('origin_path',''))}) for c in b.get('clips',[])],
                  card_overrides=b.get('card_overrides',{}), match_ids=b.get('match_ids', []),
                  edit_plan=b.get('edit_plan'), edit_key=b.get('edit_key',''),
                  events=[EventRequest(**{**e, 'selection': EventSelection(**e['selection']) if e.get('selection') else None}) for e in b.get('events', [])]) for b in data['blocks']]
        if not blocks: raise ValueError('В проекте нет разборов.')
        for block in blocks:
            if block.edit_plan:
                for c in block.edit_plan['inserts']: c['path'] = resolve(c['path'])
        settings = data.get('settings', {}).copy()
        if data.get('version', 1) < 3:
            settings.setdefault('auto_rotate', settings.get('rotate', 0) == 0)
            settings.setdefault('use_manual_clips', any(b.clips for b in blocks))
        return cls(host=resolve(data['host']),music=resolve(data.get('music','')),
                   blocks=blocks,settings=Settings(**settings),
                   matches=[MatchSource(**{**m, 'path': resolve(m['path'])}) for m in data.get('matches', [])],
                   team_logos={name: resolve(path) for name, path in data.get('team_logos', {}).items()})
