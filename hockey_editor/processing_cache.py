"""Atomic, local stage checkpoints and wall-clock diagnostics."""
from contextlib import contextmanager
from pathlib import Path
import json
import time


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


@contextmanager
def stage(folder, name, log):
    start = time.perf_counter()
    status = 'interrupted'
    try:
        yield
        status = 'complete'
    finally:
        elapsed = round(time.perf_counter() - start, 3)
        # Diagnostics must never turn a successfully processed video into a failure.
        try:
            path = Path(folder) / 'performance.json'
            data = read_json(path, {})
            data[name] = {'seconds': elapsed, 'status': status}
            write_json(path, data)
        except OSError:
            pass
        log(f'{name}: {elapsed:.1f} с' + ('' if status == 'complete' else ' · прервано'))
