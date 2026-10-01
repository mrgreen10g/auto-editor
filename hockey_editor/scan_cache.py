"""One decode feeds both analyses; completed chunks survive cancellation."""
from pathlib import Path
import shutil
from .media import run
from .processing_cache import read_json, write_json, stage

CHUNK_SECONDS = 120


def chunk_spans(duration):
    start = 0
    while start < duration:
        end = min(start + CHUNK_SECONDS, duration)
        # Fold a tiny tail into the preceding chunk, so no empty 0.5-fps
        # output is mistaken for a decoder failure.
        if duration - end < 2:
            end = duration
        yield start, end - start
        start = end


def hockey_frames(source, folder, duration, cancel, log):
    folder = Path(folder) / 'decode-v1'
    folder.mkdir(exist_ok=True)
    score_files, visual_files = [], []
    with stage(folder.parent, 'Подготовка кадров матча', log):
        for start, span in chunk_spans(duration):
            if span <= 0:
                break
            from .media import Cancelled
            if cancel.is_set():
                raise Cancelled('Отменено.')
            chunk = folder / f'{start:06d}'
            ready = read_json(chunk / 'ready.json', {})
            score = sorted((chunk / 'score').glob('*.jpg'))
            visual = sorted((chunk / 'visual').glob('*.jpg'))
            # A completed visual analysis no longer needs the small JPEGs.
            visual_state = read_json(folder.parent / 'gameplay-v1.json', {})
            visual_done = visual_state.get('duration') == duration and isinstance(visual_state.get('ranges'), list)
            complete = (ready.get('span') == span and ready.get('score') == len(score)
                        and len(score) > 0 and (visual_done or ready.get('visual') == len(visual) > 0))
            if not complete:
                shutil.rmtree(chunk, ignore_errors=True)
                (chunk / 'score').mkdir(parents=True)
                (chunk / 'visual').mkdir()
                graph = ('[0:v]split=2[s][v];'
                         '[s]fps=1/2,scale=1280:720:force_original_aspect_ratio=decrease,'
                         'pad=1280:720:(ow-iw)/2:(oh-ih)/2[score];'
                         '[v]fps=2,scale=320:180[visual]')
                # Input seeking and duration apply to BOTH outputs. The chunk
                # size is divisible by both sampling grids, preserving times.
                run(['-y', '-threads', '2', '-ss', start, '-t', span, '-i', source.path,
                     '-filter_complex_threads', '2', '-filter_complex', graph,
                     '-map', '[score]', '-an', '-q:v', '3', '-threads', '1', '-start_number', '0', chunk/'score'/'%06d.jpg',
                     '-map', '[visual]', '-an', '-q:v', '3', '-threads', '1', '-start_number', '0', chunk/'visual'/'%06d.jpg'], cancel)
                score = sorted((chunk / 'score').glob('*.jpg'))
                visual = sorted((chunk / 'visual').glob('*.jpg'))
                if not score or not visual:
                    raise ValueError('Не удалось прочитать кадры матча.')
                write_json(chunk / 'ready.json', {'span': span, 'score': len(score), 'visual': len(visual)})
            else:
                log(f'Использую готовые кадры: {start//60:02}:{start%60:02}–{(start+int(span))//60:02}:{(start+int(span))%60:02}')
            score_files.extend(score)
            visual_files.extend(visual)
            log(f'Кадры: {min(100, round((start+span)/duration*100))}%')
    return score_files, visual_files


def hockey_ranges(folder, files, duration, cancel, log):
    from .gameplay import gameplay_ranges
    path = Path(folder) / 'gameplay-v1.json'
    saved = read_json(path)
    if isinstance(saved, dict) and saved.get('duration') == duration:
        return saved['ranges']
    with stage(folder, 'Анализ игровых сцен', log):
        ranges = gameplay_ranges(files, duration, cancel, .5)
        write_json(path, {'duration': duration, 'ranges': ranges})
    for directory in (Path(folder)/'decode-v1').glob('*/visual'):
        shutil.rmtree(directory, ignore_errors=True)
    return ranges


def observations(reader, files, folder, cancel, log):
    from .goals import Observation
    from .goals import read_image
    from .media import Cancelled
    path = Path(folder) / 'observations-v1.json'
    # Coordinates are part of the checkpoint: never mix different locators.
    boxes = [getattr(reader, attr, None) for attr in ('box', 'clock_box', 'period_box')]
    saved = read_json(path, {})
    rows = saved.get('rows', []) if saved.get('boxes') == boxes and saved.get('count') == len(files) else []
    result = [Observation(**{**row, 'score': tuple(row['score']) if row['score'] is not None else None}) for row in rows]
    if rows and hasattr(reader, 'colors'):
        import numpy as np
        colors = saved.get('colors')
        reader.colors = [np.asarray(c) for c in colors] if colors is not None else None
    if result:
        log(f'Продолжаю проверку табло с {len(result)*2:.0f} с.')
    from dataclasses import asdict
    def save():
        colors = getattr(reader, 'colors', None)
        write_json(path, {'boxes': boxes, 'count': len(files), 'rows': [asdict(o) for o in result],
                          'colors': [list(map(float,c)) for c in colors] if colors is not None else None})
    with stage(folder, 'Распознавание табло', log):
        try:
            for i in range(len(result), len(files)):
                if cancel.is_set():
                    raise Cancelled('Отменено.')
                result.append(reader.read(read_image(files[i]), i*2.))
                if (i+1) % 10 == 0:
                    save()
                    log(f'Поиск голов: {int((i+1)/len(files)*100)}%')
        finally:
            save()
    return result


def single_frames(source, folder, duration, fps, size, cancel, log):
    """Resumable extraction for football and combat without changing sampling."""
    from .media import Cancelled
    root = Path(folder)
    files = []
    with stage(root.parent, 'Подготовка кадров '+source.sport, log):
        for start, span in chunk_spans(duration):
            if cancel.is_set():
                raise Cancelled('Отменено.')
            chunk = root/f'{start:06d}'
            ready = read_json(chunk/'ready.json', {})
            frames = sorted(chunk.glob('*.jpg'))
            if not (ready.get('span') == span and ready.get('fps') == fps
                    and ready.get('size') == size and ready.get('count') == len(frames) > 0):
                shutil.rmtree(chunk, ignore_errors=True)
                chunk.mkdir(parents=True)
                run(['-y','-threads','2','-ss',start,'-t',span,'-i',source.path,'-an',
                     '-vf',f'fps={fps},scale={size}','-q:v','3','-threads','1','-start_number','0',chunk/'%06d.jpg'],cancel)
                frames = sorted(chunk.glob('*.jpg'))
                if not frames:
                    raise ValueError('Не удалось прочитать кадры записи.')
                write_json(chunk/'ready.json', {'span':span,'fps':fps,'size':size,'count':len(frames)})
            files.extend(frames)
            log(f'Кадры: {min(100,round((start+span)/duration*100))}%')
    return files
