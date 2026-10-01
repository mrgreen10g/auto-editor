"""Reuse PCM and checkpoint complete Whisper decoder windows, not partial phrases."""
from pathlib import Path
import hashlib
import json
import os
import wave
from .media import run, Cancelled
from .processing_cache import read_json, write_json, stage


def cpu_threads():
    # Leave two logical CPUs for Windows, FFmpeg and the interface on an 8-vCPU VPS.
    count = os.cpu_count() or 2
    return max(1, min(6, count - 2 if count > 4 else count - 1))


def prepared_audio(project, folder, cancel, log):
    from .host_media import analysis_source, identity
    folder = Path(folder)
    key = hashlib.sha256(json.dumps([identity(p) for p in project.host_paths()]).encode()).hexdigest()
    target = folder/'voice.wav'
    marker = folder/'voice-ready.json'
    ready = read_json(marker, {})
    valid = False
    if ready.get('key') == key:
        try:
            with wave.open(str(target), 'rb') as wav:
                valid = (wav.getframerate() == 16000 and wav.getnchannels() == 1
                         and wav.getsampwidth() == 2 and wav.getnframes() == ready.get('frames')
                         and target.stat().st_size >= wav.getnframes()*2+44)
        except (OSError, EOFError, wave.Error):
            pass
    if valid:
        log('Использую подготовленный звук ведущего.')
        return target
    with stage(folder, 'Извлечение речи', log):
        source, _, _ = analysis_source(project, folder, cancel, log)
        partial = folder/'voice.partial.wav'
        try:
            run(['-y','-i',source,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',partial],cancel)
            with wave.open(str(partial), 'rb') as wav:
                frames = wav.getnframes()
            partial.replace(target)
            write_json(marker, {'key': key, 'frames': frames})
        finally:
            partial.unlink(missing_ok=True)
    return target


def recognize(model, audio, checkpoint, language, prompt, cancel, log):
    """Retain only windows closed by a subsequent seek; resume at that seek.

    faster-whisper 1.1.1 exposes Segment.seek in 10 ms frames. With
    condition_on_previous_text=False, a completed decoder window does not need
    the preceding text. On resume initial_prompt is omitted as on later windows
    in an uninterrupted pass. Word timestamps remain in original audio time.
    """
    if cancel.is_set():
        raise Cancelled('Отменено.')
    checkpoint = Path(checkpoint)
    saved = read_json(checkpoint, {})
    if saved.get('version') != 1:
        saved = {}
    rows = saved.get('rows', [])
    if saved.get('complete'):
        log('Использую сохранённое первичное распознавание речи.')
        return rows
    seek = saved.get('seek', 0)
    if seek:
        log(f'Продолжаю распознавание речи с {seek/100:.1f} с.')
    options = dict(language=language, word_timestamps=True, beam_size=5,
                   vad_filter=False, condition_on_previous_text=False,
                   initial_prompt=prompt if not seek else None)
    if seek:
        options['clip_timestamps'] = str(seek/100)
    pending = []
    current_seek = seek
    with stage(checkpoint.parent, 'Первичное распознавание речи', log):
        segments, _ = model.transcribe(str(audio), **options)
        for segment in segments:
            if cancel.is_set():
                raise Cancelled('Отменено.')
            window = int(segment.seek)
            if window != current_seek:
                rows.extend(pending)
                pending = []
                current_seek = window
                write_json(checkpoint, {'version':1, 'seek':window, 'rows':rows, 'complete':False})
            words = [dict(word=w.word, start=w.start, end=w.end, probability=w.probability)
                     for w in segment.words or [] if w.end > w.start]
            if words:
                pending.append(dict(text=segment.text, start=words[0]['start'], end=words[-1]['end'], words=words))
            log(f'Речь: {int(segment.end)//60:02}:{int(segment.end)%60:02}')
        if cancel.is_set():
            raise Cancelled('Отменено.')
        rows.extend(pending)
        write_json(checkpoint, {'version':1, 'seek':current_seek, 'rows':rows, 'complete':True})
    return rows


def preferred_device():
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            types = ctranslate2.get_supported_compute_types('cuda')
            if 'int8_float16' in types:
                return 'cuda', 'int8_float16'
            if 'float16' in types:
                return 'cuda', 'float16'
    except (ImportError, RuntimeError, ValueError, OSError):
        pass
    return 'cpu', 'int8'


def with_model(model_dir, work, log):
    """One model at a time; CUDA is optional and failure resumes on CPU."""
    import gc
    from faster_whisper import WhisperModel
    device, compute = preferred_device()
    while True:
        model = None
        retry = False
        try:
            log(f'Распознавание: {device.upper()}, CPU-потоков: {cpu_threads()}.')
            model = WhisperModel(str(model_dir), device=device, compute_type=compute,
                                 cpu_threads=cpu_threads(), local_files_only=True)
            return work(model)
        except (RuntimeError, OSError) as error:
            if device != 'cuda':
                raise
            log('Ускорение GPU недоступно; продолжаю на CPU с сохранённого этапа. '+str(error)[:180])
            retry = True
        finally:
            del model
            gc.collect()
        if retry:
            device, compute = 'cpu', 'int8'
