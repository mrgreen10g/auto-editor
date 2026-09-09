"""Portable, versioned projects. Media stays on the user's computer."""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json, math, os

@dataclass
class Clip:
    path: str
    phrase: str
    goal_time: float | None = None

@dataclass
class Settings:
    rotate: int = 0
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

@dataclass
class Project:
    version: int = 1
    host: str = ''
    music: str = ''
    blocks: list[Block] = field(default_factory=lambda: [Block()])
    settings: Settings = field(default_factory=Settings)

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
        for c in block.clips:
            if not Path(c.path).is_file():
                raise ValueError(f'Не найден игровой фрагмент: {c.path}')
            if not c.phrase.strip():
                raise ValueError('Для каждой вставки укажите слова из сценария, например 3:2.')
            if c.goal_time is not None and (not math.isfinite(c.goal_time) or c.goal_time < 0):
                raise ValueError('Некорректное положение события внутри вставки.')
        s = self.settings
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
        for block in data['blocks']:
            for c in block['clips']: c['path'] = relative(c['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix+'.tmp')
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(target)

    @classmethod
    def load(cls, filename):
        p = Path(filename).resolve()
        data = json.loads(p.read_text(encoding='utf-8'))
        if data.get('version') != 1: raise ValueError('Версия проекта не поддерживается.')
        def resolve(s):
            if not s: return ''
            return str((p.parent / s).resolve())
        blocks = [Block(title=b['title'],script=b['script'],
                  clips=[Clip(path=resolve(c['path']),phrase=c['phrase'],goal_time=c.get('goal_time')) for c in b.get('clips',[])],
                  card_overrides=b.get('card_overrides',{})) for b in data['blocks']]
        if not blocks: raise ValueError('В проекте нет разборов.')
        return cls(host=resolve(data['host']),music=resolve(data.get('music','')),
                   blocks=blocks,settings=Settings(**data.get('settings',{})))
