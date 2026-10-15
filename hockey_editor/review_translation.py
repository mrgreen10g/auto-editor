"""Opt-in local Uzbek to Russian translation, never part of render data."""
import hashlib
import json
import os
import queue
import threading
import urllib.request
from pathlib import Path

REPO = 'lifeai-dev/madlad400-3b-mt-ct2-int8'
REV = '2f034f44fd4b8ef4b79a8bc7697fd71dff36c150'
DIGESTS = {
    'config.json': '90fb54962455a4e0a0bc7235c0f063d7e46d9c1a1ae003af8059809abd6aeece',
    'shared_vocabulary.json': 'c327551ce3ca6efc7b437e11a267f79979893332dda8a1d146e2c950815193f8',
    'tokenizer.json': 'a2799ccc696b752ba00c34f58726bfe253a04921ceb6cfc620400f560474790b',
    'model.bin': '77b9fd9ab97c1259d07089b5f854393dad81bc5fb5647d3f9a5d101c94f40daa',
}
LOCK = threading.Lock()


def model_folder():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.cache')))/'HockeyAutoEditor'/'Models'/'review-ru-madlad'


def installed(folder):
    try:
        return all((folder/n).is_file() and (folder/(n+'.sha256')).read_text() == h for n,h in DIGESTS.items())
    except OSError:
        return False


def ensure_model(folder, cancel, log):
    folder.mkdir(parents=True, exist_ok=True)
    for name, digest in DIGESTS.items():
        target = folder/name
        if target.exists() and (folder/(name+'.sha256')).exists() and (folder/(name+'.sha256')).read_text() == digest:
            continue
        partial = folder/(name+'.part')
        h = hashlib.sha256(); size = 0; last = 0
        try:
            with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REV}/{name}', timeout=30) as response, partial.open('wb') as stream:
                while True:
                    if cancel.is_set(): raise InterruptedError('Перевод отменён.')
                    data = response.read(1024*1024)
                    if not data: break
                    stream.write(data); h.update(data); size += len(data)
                    if size-last >= 25*1024*1024:
                        log(f'Загрузка модели перевода: {name}, {size//1024//1024} МБ'); last=size
            if h.hexdigest() != digest: raise ValueError('Не пройдена проверка файла модели перевода: '+name)
            partial.replace(target)
            (folder/(name+'.sha256')).write_text(digest)
        finally:
            partial.unlink(missing_ok=True)


def cache_key(text):
    return hashlib.sha256(json.dumps([REV, 'ru-sports-v2', text], ensure_ascii=False).encode()).hexdigest()


def translate(texts, cache, cancel, log):
    """Process exact snapshots; caller cannot mutate source/card through this API."""
    cache = Path(cache)/'translations'; cache.mkdir(parents=True, exist_ok=True)
    results = []
    with LOCK:
        model = None; tokenizer = None
        try:
            for text in texts:
                if cancel.is_set(): raise InterruptedError('Перевод отменён.')
                if not text.strip(): results.append('Нет текста для перевода.'); continue
                from .uz_review_terms import exact_translation,sensitive
                exact=exact_translation(text)
                if exact is not None:results.append(exact);continue
                saved = cache/(cache_key(text)+'.json')
                if saved.exists():
                    try:
                        entry = json.loads(saved.read_text(encoding='utf-8'))
                        if entry.get('source') == text and isinstance(entry.get('translation'), str):
                            results.append(entry['translation']); continue
                    except (OSError, ValueError): pass
                if model is None:
                    folder = model_folder(); ensure_model(folder, cancel, log)
                    log('Перевожу на русский локально. На процессоре это может занять время…')
                    import ctranslate2
                    from tokenizers import Tokenizer
                    tokenizer = Tokenizer.from_file(str(folder/'tokenizer.json'))
                    model = ctranslate2.Translator(str(folder), device='cpu', compute_type='int8', inter_threads=1, intra_threads=min(4, max(1, (os.cpu_count() or 2)-1)))
                tokens = tokenizer.encode(text, add_special_tokens=False).tokens
                parts = []
                # Explicit chunks prevent silently truncating long script excerpts.
                prefix = tokenizer.encode('<2ru> ', add_special_tokens=False).tokens
                for offset in range(0, len(tokens), 320):
                    if cancel.is_set(): raise InterruptedError('Перевод отменён.')
                    source = prefix+tokens[offset:offset+320]+['</s>']
                    out = model.translate_batch([source], beam_size=2, max_decoding_length=512)[0].hypotheses[0]
                    if len(out) >= 512:
                        raise ValueError('Перевод достиг ограничения длины. Полный перевод не подтверждён.')
                    ids = [tokenizer.token_to_id(t) for t in out]
                    if any(i is None for i in ids): raise ValueError('Неизвестные токены модели перевода.')
                    parts.append(tokenizer.decode(ids, skip_special_tokens=True))
                value = ' '.join(parts).strip()
                if not value: raise ValueError('Модель вернула пустой перевод.')
                if sensitive(text):
                    value='⚠ Непроверенный перевод спортивной формулировки: модель может ошибиться в отрицании или направлении ставки.\n\n'+value
                temp = saved.with_suffix('.tmp')
                temp.write_text(json.dumps({'source':text, 'translation':value}, ensure_ascii=False), encoding='utf-8')
                temp.replace(saved); results.append(value)
        finally:
            if model is not None: model.unload_model()
    return results


def show(parent, texts, cache):
    import tkinter as tk
    from tkinter import ttk, messagebox
    if not installed(model_folder()) and not messagebox.askyesno('Локальный перевод УЗ → РУ',
        'Для перевода нужна отдельная модель (~3 ГБ на диске и несколько ГБ свободной памяти). Скачать её?\n\nТексты и аудио никуда не отправляются. Перевод справочный: ошибки распознавания он не исправляет.', parent=parent):
        return
    w = tk.Toplevel(parent); w.title('УЗ → русский · перевод выбранной плашки')
    w.geometry('1000x650'); w.transient(parent)
    status = tk.StringVar(value='Подготовка локального перевода…')
    ttk.Label(w, textvariable=status, wraplength=930).pack(fill='x', padx=12, pady=8)
    ttk.Label(w, text='Машинный перевод для проверки. Оригиналы и текст в готовом видео не изменяются.').pack(fill='x', padx=12)
    grid = ttk.Frame(w); grid.pack(fill='both', expand=True, padx=12, pady=10)
    grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)
    boxes = []
    for i, (label, source) in enumerate(zip(('Сценарий', 'Распознанная речь', 'Текст плашки'), texts)):
        ttk.Label(grid, text=label+' · оригинал').grid(row=i*2, column=0, sticky='w')
        ttk.Label(grid, text=label+' · перевод').grid(row=i*2, column=1, sticky='w')
        grid.rowconfigure(i*2+1, weight=1)
        for col, value in ((0, source), (1, 'Перевод ожидается…')):
            frame = ttk.Frame(grid); frame.grid(row=i*2+1,column=col,sticky='nsew',padx=4,pady=4)
            box = tk.Text(frame, height=6, wrap='word'); scroll=ttk.Scrollbar(frame,command=box.yview)
            box.configure(yscrollcommand=scroll.set); scroll.pack(side='right',fill='y'); box.pack(fill='both',expand=True)
            box.insert('1.0',value); box.configure(state='disabled')
            if col: boxes.append(box)
    cancel = threading.Event(); events = queue.Queue(); closed = False
    def work():
        try: events.put(('result', translate(tuple(texts), cache, cancel, lambda s:events.put(('status', s)))))
        except Exception as e: events.put(('error', str(e)))
    def poll():
        if closed: return
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == 'result':
                    for box, translated in zip(boxes, value):
                        box.configure(state='normal'); box.delete('1.0','end'); box.insert('1.0',translated); box.configure(state='disabled')
                    status.set('Перевод готов. Это вспомогательный текст, не подтверждение правильности ставки или распознавания.')
                else: status.set(('Перевод недоступен: ' if kind=='error' else '')+value)
        except queue.Empty: pass
        w.after(100, poll)
    def close():
        nonlocal closed
        closed=True; cancel.set(); w.destroy()
    w.protocol('WM_DELETE_WINDOW', close)
    w.bind('<Destroy>', lambda e:cancel.set() if e.widget is w else None)
    threading.Thread(target=work, daemon=True).start(); poll()
