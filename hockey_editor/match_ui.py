"""Source cards, asynchronous scanning and explicit candidate review."""
import copy
import json
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from . import ui
from .model import MatchSource, EventRequest, EventSelection
from .event_rules import requests_for, suggested_names
from .goals import GoalScanner, Candidate, source_signature, scan_root, cut_candidate
from .media import run, probe, Cancelled


class SourceDialog(simpledialog.Dialog):
    def __init__(self, parent, source):
        self.source = source
        super().__init__(parent, 'Какая встреча в этой записи?')

    def body(self, parent):
        ttk.Label(parent, text=Path(self.source.path).name, wraplength=440).grid(row=0, column=0, columnspan=2, pady=10)
        ttk.Label(parent, text='Названия в порядке табло: слева → справа.', wraplength=440).grid(row=1, column=0, columnspan=2, pady=6)
        self.values = []
        for i, (label, value) in enumerate((('Команда слева', self.source.home), ('Команда справа', self.source.away), ('Дата встречи', self.source.date))):
            ttk.Label(parent, text=label).grid(row=i+2, column=0, sticky='w', padx=8, pady=6)
            entry = ttk.Entry(parent, width=30); entry.insert(0, value); entry.grid(row=i+2, column=1, padx=8, pady=6)
            self.values.append(entry)
        return self.values[0]

    def validate(self):
        if not all(e.get().strip() for e in self.values[:2]):
            messagebox.showinfo('Команды', 'Укажите названия обеих команд.', parent=self)
            return False
        return True

    def apply(self):
        self.result = [e.get().strip() for e in self.values]


class MatchMixin:
    def build_match_materials(self, page):
        box = ui.card(page, 'Исходные матчи', 'Добавьте одну или несколько записей, на которые ссылается ведущий. Таймкоды не нужны.', '03')
        self.matchtable = ui.table(box, [('title', 'Встреча', 300), ('file', 'Запись', 280)], 3)
        self.matchtable.bind('<Double-1>', lambda _: self.edit_match() if not self.busy else None)
        row = ttk.Frame(box, style='Card.TFrame'); row.pack(fill='x', pady=(10, 0))
        for label, command in [('+ Записи', self.add_matches), ('Из проекта', self.reuse_match), ('Изменить', self.edit_match), ('Убрать', self.remove_match)]:
            self.button(row, label, command).pack(side='left', padx=(0, 6))
        row = ttk.Frame(box, style='Card.TFrame'); row.pack(fill='x', pady=(8, 0))
        self.button(row, 'Найти голы', self.search_matches, 'Primary.TButton').pack(side='left')
        self.button(row, 'Область счёта', self.score_region).pack(side='left', padx=8)

    def build_event_review(self, parent):
        ttk.Label(parent, text='Проверьте спорные эпизоды. Двойной щелчок — посмотреть и выбрать.', style='Muted.TLabel', wraplength=660).pack(anchor='w', pady=8)
        self.eventtable = ui.table(parent, [('source', 'Матч', 160), ('phrase', 'Фраза ведущего', 250), ('goal', 'Эпизод', 90), ('state', 'Статус', 100)], 6)
        self.eventtable.bind('<Double-1>', lambda _: self.edit_event() if not self.busy else None)
        row = ttk.Frame(parent); row.pack(fill='x', pady=8)
        for label, command in [('Посмотреть / выбрать', self.edit_event), ('Оставить ведущего', self.skip_event), ('+ Фраза', self.add_event)]:
            self.button(row, label, command).pack(side='left', padx=(0, 8))

    def refresh_matches(self):
        block = self.project.blocks[self.index]
        self.matchtable.delete(*self.matchtable.get_children())
        for m in self.project.matches:
            if m.id in block.match_ids:
                self.matchtable.insert('', 'end', iid=m.id, values=(m.title, Path(m.path).name))
        self.refresh_events()

    def refresh_events(self):
        self.eventtable.delete(*self.eventtable.get_children())
        sources = {m.id: m for m in self.project.matches}
        for i, e in enumerate(self.project.blocks[self.index].events):
            state = 'Ведущий' if e.skipped else 'Готово' if e.selection and e.selection.accepted else 'Проверить' if e.selection else 'Не найден'
            goal = ':'.join(map(str, e.score)) if e.score else 'Овертайм' if e.kind == 'overtime' else 'Игра'
            self.eventtable.insert('', 'end', iid=str(i), values=(sources[e.source_id].title if e.source_id in sources else 'Нет записи', e.phrase, goal, state),
                                   tags=('check',) if state in ('Проверить', 'Не найден') else ('stripe',) if i%2 else ())

    def selected_match(self):
        sel = self.matchtable.selection()
        return next((m for m in self.project.matches if sel and m.id == sel[0]), None)

    def clear_source_events(self, source_id):
        for block in self.project.blocks:
            if source_id in block.match_ids:
                block.events = []
        self.scans.pop(source_id, None)

    def add_matches(self):
        from .gui import VIDEO
        self.collect()
        changed = False
        for path in filedialog.askopenfilenames(title='Полные записи исходных матчей', filetypes=VIDEO):
            existing = next((m for m in self.project.matches if Path(m.path).resolve() == Path(path).resolve()), None)
            if existing is None:
                names = suggested_names(Path(path).stem) + ['', '']
                source = MatchSource(path, names[0], names[1])
                dialog = SourceDialog(self.root, source)
                if not dialog.result: continue
                source.home, source.away, source.date = dialog.result
                self.project.matches.append(source)
            else: source = existing
            block = self.project.blocks[self.index]
            if source.id not in block.match_ids:
                block.match_ids.append(source.id); changed = True
        if changed:
            self.project.blocks[self.index].events = []
            self.invalidate(); self.refresh()

    def reuse_match(self):
        self.collect(); block = self.project.blocks[self.index]
        sources = [m for m in self.project.matches if m.id not in block.match_ids]
        if not sources:
            return messagebox.showinfo('Записи проекта', 'Других записей пока нет. Добавьте файл кнопкой «+ Записи».')
        dialog = tk.Toplevel(self.root); dialog.title('Запись из проекта'); dialog.transient(self.root); dialog.grab_set()
        combo = ttk.Combobox(dialog, state='readonly', width=55, values=[m.title+' · '+Path(m.path).name for m in sources]); combo.pack(padx=20, pady=20); combo.current(0)
        def use():
            block.match_ids.append(sources[combo.current()].id); block.events = []
            self.invalidate(); self.refresh(); dialog.destroy()
        ttk.Button(dialog, text='Добавить в разбор', command=use).pack(pady=(0, 20))

    def edit_match(self):
        source = self.selected_match()
        if not source: return
        self.collect(); dialog = SourceDialog(self.root, source)
        if dialog.result:
            source.home, source.away, source.date = dialog.result
            self.clear_source_events(source.id); self.invalidate(); self.refresh()

    def remove_match(self):
        source = self.selected_match()
        if not source: return
        self.collect(); block = self.project.blocks[self.index]
        block.match_ids.remove(source.id)
        block.events = []
        self.invalidate(); self.refresh()

    def match_job(self, stage, work):
        self.cancel.clear(); self.stage = stage; self.set_busy(True)
        def wrapped():
            try: work()
            except Cancelled: self.jobs.put(('log', 'Отменено. Исходные файлы сохранены.'))
            except Exception as e: self.jobs.put(('error', str(e)))
            finally: self.jobs.put(('done', None))
        self.worker = threading.Thread(target=wrapped, daemon=True); self.worker.start()

    def search_matches(self):
        if self.busy: return
        self.collect(); block = self.project.blocks[self.index]
        if not block.match_ids or len(block.script.strip()) < 30:
            return messagebox.showinfo('Материалы', 'Добавьте исходную запись матча и сценарий разбора.')
        if block.events and any(e.selection and e.selection.accepted for e in block.events):
            if not messagebox.askyesno('Повторить поиск', 'Заново подобрать эпизоды? Ваш выбор эпизодов будет заменён; сохранённое видео останется.'):
                return
        events = requests_for(block, self.project.matches)
        if not events:
            return messagebox.showinfo('Сценарий', 'Не найдены фразы о голах или игре. Проверьте сценарий. Уже привязанные готовые вставки повторно не ищутся.')
        sources = copy.deepcopy([m for m in self.project.matches if m.id in block.match_ids])
        self.invalidate(); self.show_page('review'); self.reviewtabs.select(self.events_page)
        self.review_summary.set('Ищем голы в исходных матчах…')
        def work():
            scans = {}; errors = []
            for source in sources:
                if self.cancel.is_set(): raise Cancelled()
                self.jobs.put(('log', 'Матч: '+source.title))
                try:
                    scans[source.id] = GoalScanner(cancel=self.cancel, log=lambda m: self.jobs.put(('log', m))).scan(source)
                except Cancelled: raise
                except Exception as e: errors.append(source.title+': '+str(e))
            self.jobs.put(('goals', (propose_events(events, scans), scans, errors)))
        self.match_job('goals', work)

    def handle_match_job(self, kind, value):
        if kind == 'goals':
            events, scans, errors = value
            self.project.blocks[self.index].events = events; self.scans.update(scans)
            self.refresh_events(); self.update_summary()
            count = sum(not e.skipped and (not e.selection or not e.selection.accepted) for e in events)
            self.review_summary.set(f'Найдено привязок: {sum(e.selection is not None for e in events)} · Для проверки: {count}')
            self.review_note.set(errors[0] if errors else 'Посмотрите выделенные строки, затем определите тайминги речи.')
            self.log_lines.extend(errors); self.status.set('Поиск завершён. Проверьте эпизоды в таблице.')
            return True
        if kind == 'roi':
            # Defer the modal until the queue has restored enabled controls.
            self.root.after(150, lambda: self.show_roi(*value)); return True
        if kind == 'clip_preview':
            from .gui import open_file
            open_file(value); return True
        return False

    def score_region(self):
        source = self.selected_match()
        if not source:
            return messagebox.showinfo('Область счёта', 'Выберите запись в таблице матчей.')
        snapshot = copy.deepcopy(source)
        def work():
            duration = probe(snapshot.path)['duration']
            folder = scan_root()/'previews'; folder.mkdir(parents=True, exist_ok=True)
            target = folder/(snapshot.id+'.jpg')
            run(['-y', '-ss', min(60, duration*.25), '-i', snapshot.path, '-frames:v', '1', '-vf', 'scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2', target], self.cancel)
            self.jobs.put(('roi', (source, target)))
        self.match_job('roi', work)

    def show_roi(self, source, path):
        from PIL import Image, ImageTk
        dialog = tk.Toplevel(self.root); dialog.title('Выделите только две цифры счёта'); dialog.transient(self.root); dialog.grab_set()
        ttk.Label(dialog, text='Обведите мышью счёт обеих команд, без игрового времени. Эта область используется только для данной записи.').pack(padx=12, pady=10)
        im = Image.open(path); photo = ImageTk.PhotoImage(im)
        canvas = tk.Canvas(dialog, width=960, height=540, highlightthickness=0); canvas.pack(); canvas.create_image(0, 0, image=photo, anchor='nw'); canvas.photo = photo
        state = {'start': None, 'box': source.score_box, 'rect': None}
        if source.score_box:
            state['rect'] = canvas.create_rectangle(*[v*(960 if i%2 == 0 else 540) for i, v in enumerate(source.score_box)], outline='#00e4bc', width=3)
        def down(e): state['start'] = (e.x, e.y)
        def drag(e):
            if state['start'] is None: return
            x, y = state['start']; bx, by = max(0, min(960, e.x)), max(0, min(540, e.y))
            if state['rect']: canvas.delete(state['rect'])
            coords = [min(x, bx), min(y, by), max(x, bx), max(y, by)]
            state['rect'] = canvas.create_rectangle(*coords, outline='#00e4bc', width=3)
            state['box'] = [v/(960 if i%2 == 0 else 540) for i, v in enumerate(coords)]
        canvas.bind('<Button-1>', down); canvas.bind('<B1-Motion>', drag)
        def save(auto=False):
            box = None if auto else state['box']
            if not auto and (not box or box[2]-box[0] < .01 or box[3]-box[1] < .01): return
            source.score_box = box; self.clear_source_events(source.id); self.invalidate(); self.refresh(); dialog.destroy()
        row = ttk.Frame(dialog); row.pack(pady=10)
        ttk.Button(row, text='Сохранить область', command=save).pack(side='left', padx=8)
        ttk.Button(row, text='Вернуть автоматический поиск', command=lambda: save(True)).pack(side='left')

    def selected_event(self):
        sel = self.eventtable.selection()
        return self.project.blocks[self.index].events[int(sel[0])] if sel else None

    def skip_event(self):
        event = self.selected_event()
        if event:
            event.skipped = True; self.invalidate(); self.refresh_events(); self.update_summary()

    def add_event(self):
        self.collect(); block = self.project.blocks[self.index]
        if not block.match_ids: return
        phrase = simpledialog.askstring('Фраза', 'Скопируйте сюда фразу из сценария, под которую нужна вставка:')
        if not phrase: return
        if phrase.strip() not in block.script:
            return messagebox.showinfo('Фраза', 'Эта фраза не найдена в сценарии. Скопируйте её без изменений.')
        block.events.append(EventRequest(block.match_ids[0], phrase.strip(), 'play'))
        self.invalidate(); self.refresh_events(); self.eventtable.selection_set(str(len(block.events)-1)); self.edit_event()

    def edit_event(self):
        if self.busy: return
        event = self.selected_event()
        if event is None: return
        sources = [m for m in self.project.matches if m.id in self.project.blocks[self.index].match_ids]
        if not sources: return
        dialog = tk.Toplevel(self.root); dialog.title('Выбор игрового эпизода'); dialog.geometry('760x580'); dialog.transient(self.root); dialog.grab_set()
        ttk.Label(dialog, text=event.phrase, wraplength=700).pack(anchor='w', padx=20, pady=(16, 8))
        combo = ttk.Combobox(dialog, values=[m.title+' · '+Path(m.path).name for m in sources], state='readonly'); combo.pack(fill='x', padx=20)
        combo.current(next((i for i, m in enumerate(sources) if m.id == event.source_id), 0))
        tree = ui.table(dialog, [('goal', 'Кандидат', 140), ('note', 'Проверка', 450)], 6)
        values = [tk.StringVar() for _ in range(3)]
        row = ttk.Frame(dialog); row.pack(fill='x', padx=20, pady=10)
        for label, var in zip(('Начало, с', 'Конец, с', 'Гол, с'), values):
            ttk.Label(row, text=label).pack(side='left', padx=(0, 4)); ttk.Entry(row, textvariable=var, width=9).pack(side='left', padx=(0, 12))
        note = ttk.Label(dialog, text=event.note or 'Выберите подходящий эпизод и посмотрите его. При необходимости поправьте границы.', wraplength=710); note.pack(fill='x', padx=20, pady=6)
        state = {'data': None, 'candidates': []}
        def load_candidates(_=None):
            source = sources[combo.current()]; signature = source_signature(source)
            data = self.scans.get(source.id)
            if not data or data.get('signature') != signature:
                file = scan_root()/signature[:24]/'goals.json'
                data = json.loads(file.read_text(encoding='utf-8')) if file.exists() else None
            state['data'] = data; state['candidates'] = [Candidate(**c) for c in data['candidates']] if data else []
            tree.delete(*tree.get_children())
            for i, c in enumerate(state['candidates']):
                tree.insert('', 'end', iid=str(i), values=(c.label, c.note or 'Смена счёта и игрового времени'))
            for var in values: var.set('')
            if event.selection and source.id == event.source_id and event.selection.source_signature == signature:
                for var, n in zip(values, (event.selection.source_start, event.selection.source_end, event.selection.event_time)): var.set(f'{n:.2f}')
                idx = next((i for i, c in enumerate(state['candidates']) if c.id == event.selection.candidate_id), None)
                if idx is not None: tree.selection_set(str(idx)); tree.see(str(idx))
            if not data: note.configure(text='Сначала выполните поиск в этой записи. Можно также задать границы вручную в секундах.')
        def selected(_=None):
            if not tree.selection(): return
            c = state['candidates'][int(tree.selection()[0])]
            for var, n in zip(values, (c.start, c.end, c.time)): var.set(f'{n:.2f}')
            note.configure(text=c.note or 'Посмотрите эпизод перед использованием.')
        def selection():
            source = sources[combo.current()]
            start, end, when = [float(v.get().replace(',', '.')) for v in values]
            if not 0 <= start <= when <= end or not .5 <= end-start <= 60 or end > probe(source.path)['duration']+.05:
                raise ValueError('Проверьте границы: начало ≤ гол ≤ конец; длина от 0,5 до 60 секунд.')
            ident = state['candidates'][int(tree.selection()[0])].id if tree.selection() else 'manual'
            return source, EventSelection(ident, start, end, when, source_signature(source), True)
        def use():
            try:
                source, chosen = selection()
                c = next((c for c in state['candidates'] if c.id == chosen.candidate_id), None)
                if event.score and c and c.score != event.score:
                    if not messagebox.askyesno('Другой счёт', 'Счёт выбранного эпизода отличается от сценария. Использовать его?', parent=dialog): return
                event.source_id = source.id; event.selection = chosen; event.skipped = False
                self.invalidate(); self.refresh_events(); self.update_summary(); dialog.destroy()
            except Exception as e: messagebox.showerror('Границы эпизода', str(e), parent=dialog)
        def preview():
            try: source, chosen = selection()
            except Exception as e: return messagebox.showerror('Границы эпизода', str(e), parent=dialog)
            dialog.destroy()
            def work():
                path = cut_candidate(copy.deepcopy(source), chosen, scan_root()/'previews', self.cancel)
                self.jobs.put(('clip_preview', path))
            self.match_job('preview', work)
        tree.bind('<<TreeviewSelect>>', selected); combo.bind('<<ComboboxSelected>>', load_candidates)
        buttons = ttk.Frame(dialog); buttons.pack(fill='x', padx=20, pady=12)
        ttk.Button(buttons, text='Посмотреть видео', command=preview).pack(side='left')
        ttk.Button(buttons, text='Использовать эпизод', command=use, style='Primary.TButton').pack(side='right')
        load_candidates()


def propose_events(events, scans):
    from .goals import propose
    return propose(events, scans)
