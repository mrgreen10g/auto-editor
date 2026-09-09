"""Guided native Windows workspace. Rendering stays on a worker thread."""
import copy
import json
import hashlib
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from .model import Project, Block, Clip
from .match_ui import MatchMixin
from .goals import unresolved
from .engine import Engine
from .media import Cancelled
from . import __version__
from . import ui

VIDEO = [('Видео', '*.mp4 *.mov *.mkv *.avi *.webm'), ('Все файлы', '*.*')]


def open_file(path):
    if os.name == 'nt':
        os.startfile(str(path))
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
    else:
        subprocess.Popen(['xdg-open', str(path)])


class App(MatchMixin):
    def __init__(self, root):
        self.root = root
        root.title(f'Hockey Auto Editor {__version__}')
        w, h = min(1220, root.winfo_screenwidth() - 60), min(860, root.winfo_screenheight() - 100)
        root.geometry(f'{w}x{h}')
        root.minsize(min(960, w), min(640, h))
        root.configure(bg=ui.BG)
        self.project = Project()
        self.project_path = None
        self.scans = {}
        self.legacy_project = False
        self.index = 0
        self.plan = self.result = None
        self.jobs = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.worker = None
        self.controls = []
        self.page = 'materials'
        self.refreshing = False
        self.poll_id = None
        self.stage = None
        self.host = tk.StringVar()
        self.music = tk.StringVar()
        self.title = tk.StringVar(value='Новый разбор')
        self.status = tk.StringVar(value='Добавьте запись ведущего и сценарий — таймкоды найдём автоматически.')
        self.project_label = tk.StringVar(value='Проект не сохранён')
        self.readiness = tk.StringVar()
        self.review_summary = tk.StringVar(value='Сначала определите тайминги на шаге «Материалы».')
        self.review_note = tk.StringVar(value='Здесь появятся фразы сценария и время их показа.')
        self.export_summary = tk.StringVar()
        self.output_label = tk.StringVar(value='Готовый ролик появится здесь после экспорта.')
        self.ui_style = ui.theme(root)
        self.build_shell()
        self.build_materials()
        self.build_review()
        self.build_export()
        self.build_settings()
        self.build_footer()
        self.refresh()
        for var in [self.host, self.music, self.title, self.rotate, self.noise,
                    self.level, self.resolution, *self.effect_vars.values()]:
            var.trace_add('write', self.changed)
        self.script.bind('<<Modified>>', self.script_changed)
        self.root.bind_all('<MouseWheel>', self.scroll_page, add='+')
        self.root.bind_all('<Button-4>', self.scroll_page, add='+')
        self.root.bind_all('<Button-5>', self.scroll_page, add='+')
        root.bind('<Control-s>', lambda _: self.save() if not self.busy else None)
        root.bind('<Control-o>', lambda _: self.load() if not self.busy else None)
        self.show_page('materials')
        self.poll_id = root.after(100, self.poll)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def build_shell(self):
        rail = tk.Frame(self.root, bg=ui.NAV, width=210)
        rail.pack(side='left', fill='y')
        rail.pack_propagate(False)
        brand = tk.Frame(rail, bg=ui.NAV)
        brand.pack(fill='x', padx=22, pady=(28, 22))
        logo = tk.Canvas(brand, width=36, height=36, bg=ui.NAV, highlightthickness=0)
        logo.pack(anchor='w', pady=(0, 14))
        logo.create_oval(1, 1, 35, 35, fill='#4CD8B1', outline='')
        logo.create_polygon(14, 9, 26, 18, 14, 27, fill=ui.NAV)
        tk.Label(brand, text='HOCKEY\nAUTO EDITOR', bg=ui.NAV, fg='white',
                 font=('Segoe UI', 15, 'bold'), justify='left').pack(anchor='w')
        tk.Label(brand, text=f'Версия {__version__}  /  Windows', bg=ui.NAV, fg=ui.NAV_MUTED,
                 font=('Segoe UI', 9)).pack(anchor='w', pady=(8, 0))
        tk.Label(rail, text='ВАШ РАЗБОР', bg=ui.NAV, fg=ui.NAV_MUTED,
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w', padx=22, pady=(6, 12))
        self.nav = {}
        for key, title in [('materials', '1   Материалы'), ('review', '2   Проверка'), ('export', '3   Экспорт')]:
            b = tk.Button(rail, text=title, command=lambda k=key: self.show_page(k),
                          bg=ui.NAV, fg=ui.NAV_MUTED, activebackground='#244452',
                          activeforeground='white', bd=0, relief='flat', anchor='w',
                          padx=16, pady=13, cursor='hand2', font=('Segoe UI', 11),
                          highlightthickness=0)
            b.pack(fill='x', padx=10, pady=3)
            self.nav[key] = b
        bottom = tk.Frame(rail, bg=ui.NAV)
        bottom.pack(side='bottom', fill='x', padx=20, pady=24)
        self.settings_nav = tk.Button(bottom, text='Оформление и звук', command=lambda: self.show_page('settings'),
                                      bg=ui.NAV, fg='white', activebackground='#244452', activeforeground='white',
                                      bd=0, anchor='w', pady=10, cursor='hand2', font=('Segoe UI', 10))
        self.settings_nav.pack(fill='x')
        tk.Frame(bottom, bg='#2C4350', height=1).pack(fill='x', pady=12)
        tk.Label(bottom, text='Всё на вашем компьютере', bg=ui.NAV, fg=ui.NAV_MUTED,
                 font=('Segoe UI', 8)).pack(anchor='w')
        tk.Label(bottom, textvariable=self.project_label, bg=ui.NAV, fg=ui.NAV_MUTED,
                 font=('Segoe UI', 8), wraplength=165, justify='left').pack(anchor='w', pady=(6, 0))
        main = ttk.Frame(self.root, padding=(26, 20, 20, 14))
        main.pack(side='left', fill='both', expand=True)
        bar = ttk.Frame(main)
        bar.pack(fill='x', pady=(0, 18))
        ttk.Label(bar, text='РАБОЧАЯ ОБЛАСТЬ', style='Muted.TLabel', font=('Segoe UI', 9, 'bold')).pack(side='left')
        for label, cmd in [('Сохранить проект', self.save), ('Открыть проект', self.load), ('Новый', self.new)]:
            self.button(bar, label, cmd).pack(side='right', padx=(8, 0))
        self.heading = ttk.Label(main, style='Heading.TLabel')
        self.heading.pack(anchor='w')
        self.subtitle = ttk.Label(main, style='Muted.TLabel', wraplength=800)
        self.subtitle.pack(fill='x', pady=(6, 18))
        self.subtitle.bind('<Configure>', lambda e: self.subtitle.configure(wraplength=max(200, e.width)))
        self.deck = ttk.Frame(main)
        self.deck.pack(fill='both', expand=True)
        self.deck.rowconfigure(0, weight=1)
        self.deck.columnconfigure(0, weight=1)
        self.pages = {}
        self.footer = ttk.Frame(main)
        self.footer.pack(fill='x', pady=(12, 0))

    def scrollable(self, key):
        page = ui.ScrollPage(self.deck)
        page.grid(row=0, column=0, sticky='nsew')
        self.pages[key] = page
        return page.content

    def build_materials(self):
        page = self.scrollable('materials')
        block = ttk.Frame(page)
        block.pack(fill='x', pady=(0, 14))
        ttk.Label(block, text='Разбор', style='Muted.TLabel').pack(side='left', padx=(0, 10))
        self.blockbox = ttk.Combobox(block, state='readonly', width=28)
        self.blockbox.pack(side='left', fill='x', expand=True)
        self.controls.append(self.blockbox)
        self.blockbox.bind('<<ComboboxSelected>>', self.switch_block)
        self.button(block, '+ Разбор', self.add_block).pack(side='left', padx=8)
        self.button(block, 'Удалить', self.delete_block).pack(side='left')
        presenter = ui.card(page, 'Запись ведущего', 'Можно весь выпуск до 15 минут. Нужны изображение и голос.', '01')
        self.pathrow(presenter, self.host, self.choose_host, 'Выбрать видео')
        self.host_hint = ttk.Label(presenter, style='CardMuted.TLabel', wraplength=650)
        self.host_hint.pack(anchor='w', pady=(8, 0))
        script = ui.card(page, 'Сценарий разбора', 'Вставьте текст так, как его произносит ведущий. Таймкоды не нужны.', '02')
        row = ttk.Frame(script, style='Card.TFrame')
        row.pack(fill='x', pady=(0, 10))
        ttk.Label(row, text='Название матча', style='CardMuted.TLabel').pack(side='left', padx=(0, 12))
        entry = ttk.Entry(row, textvariable=self.title)
        entry.pack(side='left', fill='x', expand=True)
        self.controls.append(entry)
        field = ttk.Frame(script, style='Card.TFrame')
        field.pack(fill='both', expand=True)
        self.script = tk.Text(field, height=7, wrap='word', font=('Segoe UI', 11), undo=True,
                              bg='#FAFCFD', fg=ui.INK, insertbackground=ui.TEAL,
                              relief='flat', highlightthickness=1, highlightbackground=ui.LINE,
                              highlightcolor=ui.TEAL, padx=12, pady=10, spacing1=3, spacing3=3)
        sb = ttk.Scrollbar(field, command=self.script.yview)
        self.script.configure(yscrollcommand=sb.set)
        self.script.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.controls.append(self.script)
        self.build_match_materials(page)
        clips = ui.card(page, 'Готовые вставки · необязательно', 'Уже вырезанные фрагменты можно добавить вручную. Их фразы не участвуют в поиске голов.', '04')
        self.clip_hint = ttk.Label(clips, style='CardMuted.TLabel')
        self.clip_hint.pack(anchor='w', pady=(0, 8))
        self.cliptable = ui.table(clips, [('file', 'Фрагмент', 280), ('phrase', 'Привязка к словам ведущего', 350)], 4)
        self.cliptable.bind('<Double-1>', lambda _: self.edit_clip() if not self.busy else None)
        actions = ttk.Frame(clips, style='Card.TFrame')
        actions.pack(fill='x', pady=(12, 0))
        self.button(actions, '+ Добавить вставки', self.add_clips).pack(side='left')
        for label, cmd in [('Привязка', self.edit_clip), ('Посмотреть', self.preview_clip), ('Убрать', self.remove_clip)]:
            self.button(actions, label, cmd).pack(side='left', padx=(8, 0))
        ttk.Label(page, text='Начните с одной записи. Затем можно добавить остальные встречи этого разбора.',
                  style='Muted.TLabel', wraplength=650).pack(anchor='w', pady=(0, 4))

    def build_review(self):
        page = ttk.Frame(self.deck, padding=(0, 0, 14, 0))
        page.grid(row=0, column=0, sticky='nsew')
        self.pages['review'] = page
        summary = ui.card(page, 'Результат анализа')
        ttk.Label(summary, textvariable=self.review_summary, style='CardTitle.TLabel').pack(anchor='w')
        self.warning_label = ttk.Label(summary, textvariable=self.review_note, style='CardMuted.TLabel', wraplength=720)
        self.warning_label.pack(fill='x', pady=(8, 0))
        self.warning_label.bind('<Configure>', lambda e: self.warning_label.configure(wraplength=max(200, e.width)))
        self.reviewtabs = ttk.Notebook(page)
        self.reviewtabs.pack(fill='both', expand=True)
        self.events_page = ttk.Frame(self.reviewtabs, padding=8)
        timing_page = ttk.Frame(self.reviewtabs, padding=8)
        self.reviewtabs.add(self.events_page, text='Игровые эпизоды')
        self.reviewtabs.add(timing_page, text='Речь и плашки')
        self.build_event_review(self.events_page)
        page = timing_page
        self.linetable = ui.table(page, [('time', 'Время', 125), ('text', 'Фраза сценария', 480), ('check', 'Проверка', 115)], 8)
        self.linetable.bind('<Double-1>', lambda _: self.edit_card() if not self.busy else None)
        row = ttk.Frame(page)
        row.pack(side='bottom', fill='x', pady=(12, 6), before=self.linetable.master)
        self.button(row, 'Изменить плашку', self.edit_card).pack(side='left')
        self.button(row, 'Повторить анализ', lambda: self.start(False)).pack(side='left', padx=8)
        self.button(row, 'Подробности', self.details).pack(side='right')
        ttk.Label(page, text='Дважды нажмите на фразу, чтобы изменить плашку. Пустой текст отключает её.',
                  style='Muted.TLabel', wraplength=700).pack(anchor='w')

    def build_export(self):
        page = self.scrollable('export')
        summary = ui.card(page, 'Ваш ролик')
        ttk.Label(summary, textvariable=self.export_summary, style='Card.TLabel', wraplength=680,
                  font=('Segoe UI', 12), justify='left').pack(anchor='w')
        self.button(summary, 'Настроить оформление и звук', lambda: self.show_page('settings')).pack(anchor='w', pady=(16, 0))
        result = ui.card(page, 'Готовый файл', 'Программа спросит, куда сохранить MP4. Исходники останутся на месте.')
        label = ttk.Label(result, textvariable=self.output_label, style='CardMuted.TLabel', wraplength=640)
        label.pack(fill='x')
        label.bind('<Configure>', lambda e: label.configure(wraplength=max(200, e.width)))
        row = ttk.Frame(result, style='Card.TFrame')
        row.pack(fill='x', pady=(16, 0))
        self.previewbutton = ttk.Button(row, text='Открыть результат', command=self.preview, state='disabled')
        self.previewbutton.pack(side='left')
        self.folderbutton = ttk.Button(row, text='Показать в папке', command=self.result_folder, state='disabled')
        self.folderbutton.pack(side='left', padx=8)
        ttk.Label(page, text='Экспортируется выбранный разбор. Остальные разборы сохраняются в проекте.',
                  style='Muted.TLabel', wraplength=700).pack(anchor='w')

    def build_settings(self):
        page = self.scrollable('settings')
        look = ui.card(page, 'Изображение и динамика', 'Проверенные настройки уже включены. Их можно менять для конкретного выпуска.')
        self.rotate = tk.StringVar(value='Без поворота')
        self.option(look, 'Поворот ведущего', self.rotate, ['Без поворота', '90°', '180°', '270°'])
        self.effect_vars = {}
        for key, label in [('zoom', 'Плавные наезды 100% → 120% с промежутками'),
                           ('transitions', 'Мягкие переходы к игре и обратно'),
                           ('animate_cards', 'Плавное появление и уход плашек'),
                           ('wobble', 'Лёгкое покачивание плашек'),
                           ('cut_pauses', 'Сокращать паузы, сохраняя окончания слов'),
                           ('color', 'Лёгкая цветокоррекция')]:
            var = tk.BooleanVar(value=True)
            self.effect_vars[key] = var
            widget = ttk.Checkbutton(look, text=label, variable=var)
            widget.pack(anchor='w', pady=2)
            self.controls.append(widget)
        sound = ui.card(page, 'Голос и музыка', 'Очистка уменьшает фоновый шум, музыка автоматически приглушается под речь.')
        self.noise = tk.StringVar(value='Обычно')
        self.level = tk.StringVar(value='Тихо')
        self.resolution = tk.StringVar(value='720p')
        self.option(sound, 'Очистка голоса', self.noise, ['Выключено', 'Мягко', 'Обычно', 'Сильнее'])
        ttk.Label(sound, text='Музыка · необязательно', style='CardMuted.TLabel').pack(anchor='w', pady=(12, 6))
        self.pathrow(sound, self.music, self.choose_music, 'Выбрать музыку')
        row = ttk.Frame(sound, style='Card.TFrame')
        row.pack(fill='x', pady=(6, 12))
        self.button(row, 'Убрать музыку', lambda: self.music.set('')).pack(side='right')
        self.option(sound, 'Громкость музыки', self.level, ['Очень тихо', 'Тихо', 'Заметнее'])
        quality = ui.card(page, 'Качество экспорта')
        self.option(quality, 'Размер видео', self.resolution, ['720p', '1080p'])
        ttk.Label(quality, text='MP4 · 30 кадров/с. Для быстрой первой проверки подойдёт 720p.',
                  style='CardMuted.TLabel').pack(anchor='w', pady=(6, 0))

    def build_footer(self):
        ttk.Separator(self.footer).pack(fill='x', pady=(0, 12))
        row = ttk.Frame(self.footer)
        row.pack(fill='x')
        row.columnconfigure(0, weight=1)
        self.ready_label = ttk.Label(row, textvariable=self.readiness, style='Muted.TLabel', wraplength=330, width=1)
        self.ready_label.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        self.ready_label.bind('<Configure>', lambda e: self.ready_label.configure(wraplength=max(100, e.width)))
        self.primary = self.button(row, 'Определить тайминги →', self.primary_action, 'Primary.TButton')
        self.primary.grid(row=0, column=2, sticky='e')
        self.cancelbutton = ttk.Button(row, text='Отменить', command=self.cancel.set, state='disabled')
        self.cancelbutton.grid(row=0, column=1, padx=(0, 10))
        self.progress = ttk.Progressbar(self.footer, mode='indeterminate')
        self.progress.pack(fill='x', pady=(12, 8))
        status = ttk.Frame(self.footer)
        status.pack(fill='x')
        label = ttk.Label(status, textvariable=self.status, style='Muted.TLabel', wraplength=650)
        label.pack(side='left', fill='x', expand=True)
        label.bind('<Configure>', lambda e: label.configure(wraplength=max(100, e.width)))
        ttk.Button(status, text='Журнал', command=self.details).pack(side='right', padx=(10, 0))
        self.log_lines = []

    def button(self, parent, label, command, style='TButton'):
        widget = ttk.Button(parent, text=label, command=command, style=style)
        self.controls.append(widget)
        return widget

    def pathrow(self, parent, var, choose, label):
        row = ttk.Frame(parent, style='Card.TFrame')
        row.pack(fill='x')
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.controls.append(entry)
        self.button(row, label, choose).pack(side='right')

    def option(self, parent, label, var, values):
        row = ttk.Frame(parent, style='Card.TFrame')
        row.pack(fill='x', pady=5)
        ttk.Label(row, text=label, style='Card.TLabel', width=25).pack(side='left')
        combo = ttk.Combobox(row, textvariable=var, values=values, state='readonly', width=22)
        combo.pack(side='left')
        self.controls.append(combo)

    def scroll_page(self, event):
        page = self.pages.get(self.page)
        if not isinstance(page, ui.ScrollPage):
            return
        # Text fields and tables retain their own wheel behaviour. Dialogs are independent.
        if event.widget.winfo_toplevel() != self.root or event.widget.winfo_class() in ('Text', 'Treeview', 'TCombobox'):
            return
        delta = -1 if getattr(event, 'num', 0) == 4 else 1 if getattr(event, 'num', 0) == 5 else (-1 if event.delta > 0 else 1)
        page.scroll(delta * 3)

    def show_page(self, key):
        self.page = key
        self.pages[key].tkraise()
        headings = {
            'materials': ('Подготовим разбор', 'Добавьте исходники. Дальше программа сопоставит сценарий с голосом.'),
            'review': ('Проверим совпадения', 'Посмотрите разметку и поправьте информационные плашки, если нужно.'),
            'export': ('Соберём готовый ролик', 'Выберите оформление и сохраните результат в MP4.'),
            'settings': ('Оформление и звук', 'Настройки применяются при следующей сборке видео.')}
        title, sub = headings[key]
        self.heading.configure(text=title)
        self.subtitle.configure(text=sub)
        for name, button in self.nav.items():
            button.configure(bg='#245160' if name == key else ui.NAV,
                             fg='white' if name == key else ui.NAV_MUTED,
                             font=('Segoe UI', 11, 'bold' if name == key else 'normal'))
        self.settings_nav.configure(fg='#65E4C0' if key == 'settings' else 'white')
        self.update_summary()

    def primary_action(self):
        if self.busy:
            return
        if self.page == 'settings':
            self.show_page('export' if self.plan else 'materials')
        elif self.project.blocks[self.index].match_ids and not self.project.blocks[self.index].events and not self.project.blocks[self.index].clips:
            self.search_matches()
        elif unresolved(self.project.blocks[self.index]):
            self.show_page('review')
            self.reviewtabs.select(self.events_page)
            block = self.project.blocks[self.index]
            self.eventtable.selection_set(str(block.events.index(unresolved(block)[0])))
            self.edit_event()
        elif self.page == 'review' and self.plan:
            self.show_page('export')
        else:
            self.start(self.page == 'export')

    def choose_host(self):
        path = filedialog.askopenfilename(title='Видео ведущего', filetypes=VIDEO)
        if path:
            self.host.set(path)

    def choose_music(self):
        path = filedialog.askopenfilename(title='Музыка', filetypes=[('Звук', '*.mp3 *.wav *.m4a *.aac *.flac'), ('Все файлы', '*.*')])
        if path:
            self.music.set(path)

    def script_changed(self, _=None):
        if self.script.edit_modified():
            self.script.edit_modified(False)
            if not self.refreshing and not self.busy:
                self.project.blocks[self.index].events = []
                self.refresh_events()
            self.changed()

    def changed(self, *_):
        if self.refreshing or self.busy:
            return
        self.invalidate()
        self.update_summary()

    def invalidate(self):
        had_plan = self.plan is not None
        self.plan = None
        self.linetable.delete(*self.linetable.get_children())
        self.review_summary.set('Материалы изменились — определите тайминги заново.' if had_plan else 'Сначала определите тайминги на шаге «Материалы».')
        self.review_note.set('Повторный анализ использует сохранённую разметку речи, если сценарий и запись не изменились.')
        self.result = None
        self.output_label.set('Готовый ролик появится здесь после экспорта.')
        self.previewbutton.configure(state='disabled')
        self.folderbutton.configure(state='disabled')

    def collect(self):
        p = self.project
        p.host = self.host.get().strip()
        p.music = self.music.get().strip()
        block = p.blocks[self.index]
        block.title = self.title.get().strip() or 'Разбор'
        block.script = self.script.get('1.0', 'end').strip()
        for key, var in self.effect_vars.items():
            setattr(p.settings, key, var.get())
        p.settings.rotate = {'Без поворота': 0, '90°': 90, '180°': 180, '270°': 270}[self.rotate.get()]
        p.settings.zoom_max = 1.20
        p.settings.denoise = self.noise.get() != 'Выключено'
        p.settings.noise_reduction = {'Выключено': 10, 'Мягко': 6, 'Обычно': 10, 'Сильнее': 14}[self.noise.get()]
        p.settings.music_db = {'Очень тихо': -32, 'Тихо': -28, 'Заметнее': -24}[self.level.get()]
        p.settings.width, p.settings.height = (1920, 1080) if self.resolution.get() == '1080p' else (1280, 720)

    def refresh(self):
        self.refreshing = True
        p = self.project
        block = p.blocks[self.index]
        self.host.set(p.host)
        self.music.set(p.music)
        self.title.set(block.title)
        self.blockbox['values'] = [x.title for x in p.blocks]
        self.blockbox.current(self.index)
        self.script.delete('1.0', 'end')
        self.script.insert('1.0', block.script)
        self.script.edit_modified(False)
        self.cliptable.delete(*self.cliptable.get_children())
        for i, clip in enumerate(block.clips):
            self.cliptable.insert('', 'end', iid=str(i), values=(Path(clip.path).name, clip.phrase), tags=('stripe',) if i % 2 else ())
        self.rotate.set({0: 'Без поворота', 90: '90°', 180: '180°', 270: '270°'}[p.settings.rotate])
        for key, var in self.effect_vars.items():
            var.set(getattr(p.settings, key))
        self.noise.set('Выключено' if not p.settings.denoise else 'Мягко' if p.settings.noise_reduction < 8 else 'Сильнее' if p.settings.noise_reduction > 12 else 'Обычно')
        self.level.set('Очень тихо' if p.settings.music_db <= -30 else 'Заметнее' if p.settings.music_db >= -26 else 'Тихо')
        self.resolution.set('1080p' if p.settings.width == 1920 else '720p')
        self.project_label.set(Path(self.project_path).name if self.project_path else 'Проект не сохранён')
        self.refresh_matches()
        self.refreshing = False
        self.update_summary()

    def update_summary(self):
        script = self.script.get('1.0', 'end').strip()
        host = self.host.get().strip()
        clips = self.project.blocks[self.index].clips
        self.host_hint.configure(text=Path(host).name if host and Path(host).is_file() else 'Выберите файл с компьютера.' if not host else 'Файл не найден. Выберите запись заново.')
        self.clip_hint.configure(text=f'Добавлено фрагментов: {len(clips)}. Двойной щелчок — изменить привязку.' if clips else 'Пока нет вставок. Без них в кадре останется ведущий.')
        missing = []
        if not host or not Path(host).is_file():
            missing.append('запись ведущего')
        if len(script) < 30:
            missing.append('сценарий')
        if any(not Path(c.path).is_file() for c in clips):
            missing.append('файлы вставок')
        if self.music.get().strip() and not Path(self.music.get().strip()).is_file():
            missing.append('файл музыки')
        self.readiness.set('Нужно добавить: ' + ', '.join(missing) if missing else 'Материалы готовы  ·  ' + str(len(clips)) + ' вставки')
        duration = ui.timecode(self.plan.duration) if self.plan else 'определится после анализа'
        effects = []
        if self.effect_vars['zoom'].get():
            effects.append('наезды до 120%')
        if self.noise.get() != 'Выключено':
            effects.append('очистка голоса')
        if self.effect_vars['transitions'].get():
            effects.append('переходы')
        self.export_summary.set(f'{self.title.get().strip() or "Новый разбор"}\n\nДлительность: {duration}\nMP4  ·  {self.resolution.get()}  ·  30 кадров/с\n\n' + ', '.join(effects).capitalize())
        labels = {'materials': 'Определить тайминги →', 'review': 'Перейти к экспорту →' if self.plan else 'Определить тайминги →',
                  'export': 'Собрать MP4', 'settings': 'Готово · вернуться'}
        block = self.project.blocks[self.index]
        if block.match_ids:
            self.readiness.set(f'Записей: {len(block.match_ids)} · Эпизодов для проверки: {len(unresolved(block))}' if not missing else self.readiness.get())
            if self.page != 'settings' and not block.events and not block.clips:
                labels[self.page] = 'Найти голы →'
            elif self.page != 'settings' and unresolved(block):
                labels[self.page] = 'Проверить эпизоды →'
        self.primary.configure(text='Идёт обработка…' if self.busy else labels[self.page])

    def switch_block(self, _=None):
        idx = self.blockbox.current()
        self.collect()
        self.index = idx
        self.invalidate()
        self.refresh()

    def add_block(self):
        self.collect()
        self.project.blocks.append(Block(title=f'Разбор {len(self.project.blocks) + 1}'))
        self.index = len(self.project.blocks) - 1
        self.invalidate()
        self.refresh()

    def delete_block(self):
        if len(self.project.blocks) == 1:
            return messagebox.showinfo('Разбор', 'В проекте должен остаться хотя бы один разбор.')
        if messagebox.askyesno('Удалить разбор', 'Убрать выбранный разбор из проекта? Видео на диске останется.'):
            del self.project.blocks[self.index]
            self.index = 0
            self.invalidate()
            self.refresh()

    def add_clips(self):
        self.collect()
        for path in filedialog.askopenfilenames(title='Готовые игровые вставки', filetypes=VIDEO):
            name = Path(path).stem
            nums = re.search(r'(\d+)[_:](\d+)(?:$|[^\d])', name)
            phrase = (nums[1] + ':' + nums[2]) if nums else simpledialog.askstring('Привязка к речи', f'{Path(path).name}\nКакие слова из сценария сопровождает вставка?')
            script = self.project.blocks[self.index].script
            if 'equaliz' in name.lower():
                phrase = next((line.strip() for line in script.splitlines() if 'сравн' in line.lower()), phrase)
            elif 'overtime' in name.lower():
                phrase = next((line.strip() for line in script.splitlines() if 'овертайм' in line.lower() and any(w in line.lower() for w in ('затем', 'решил', 'победный'))), phrase)
            if phrase:
                self.project.blocks[self.index].clips.append(Clip(path, phrase))
        self.invalidate()
        self.refresh()

    def selected_clip(self):
        sel = self.cliptable.selection()
        if not sel:
            self.status.set('Сначала выберите строку с игровой вставкой.')
            return None
        return self.project.blocks[self.index].clips[int(sel[0])]

    def edit_clip(self):
        if self.busy:
            return
        clip = self.selected_clip()
        if clip is None:
            return
        self.collect()
        value = simpledialog.askstring('Привязка к речи', 'Слова из сценария или счёт:', initialvalue=clip.phrase)
        if value:
            clip.phrase = value
            self.invalidate()
            self.refresh()

    def preview_clip(self):
        clip = self.selected_clip()
        if clip:
            try:
                open_file(clip.path)
            except Exception as e:
                messagebox.showerror('Просмотр', str(e))

    def remove_clip(self):
        sel = self.cliptable.selection()
        if sel:
            self.collect()
            for index in sorted((int(x) for x in sel), reverse=True):
                del self.project.blocks[self.index].clips[index]
            self.invalidate()
            self.refresh()
        else:
            self.status.set('Выберите вставку, которую нужно убрать.')

    def edit_card(self):
        if self.busy:
            return
        sel = self.linetable.selection()
        if not sel or self.plan is None:
            self.status.set('Выберите фразу в таблице после определения таймингов.')
            return
        i = int(sel[0])
        self.collect()
        block = self.project.blocks[self.index]
        default = next((c.text for c in self.plan.cards if c.line == i), '')
        text = block.card_overrides.get(str(i), default)
        value = simpledialog.askstring('Плашка', 'Текст плашки. Оставьте пустым, чтобы отключить:', initialvalue=text)
        if value is not None:
            block.card_overrides[str(i)] = value
            self.result = None
            self.previewbutton.configure(state='disabled')
            self.folderbutton.configure(state='disabled')
            self.output_label.set('Текст плашки изменён. Соберите MP4, чтобы увидеть обновление.')
            self.status.set('Плашка сохранена в проекте. Изменение применится при экспорте.')

    def new(self):
        if not messagebox.askyesno('Новый проект', 'Создать новый проект? Несохранённые изменения текущего проекта будут потеряны.'):
            return
        self.project = Project()
        self.index = 0
        self.project_path = None
        self.invalidate()
        self.refresh()
        self.show_page('materials')

    def load(self):
        path = filedialog.askopenfilename(filetypes=[('Проект монтажа', '*.hockeyproj')])
        if not path:
            return
        try:
            self.project = Project.load(path)
            self.legacy_project = json.loads(Path(path).read_text(encoding='utf-8')).get('version') == 1
            self.scans = {}
            self.index = 0
            self.project_path = path
            self.invalidate()
            self.refresh()
            self.show_page('materials')
            self.status.set('Проект открыт. Проверьте материалы и нажмите «Определить тайминги».')
        except Exception as e:
            messagebox.showerror('Не удалось открыть проект', str(e))

    def save(self):
        self.collect()
        path = filedialog.asksaveasfilename(defaultextension='.hockeyproj', initialfile=(Path(self.project_path).stem+'-0.2.hockeyproj' if self.legacy_project else Path(self.project_path).name) if self.project_path else 'Мой выпуск.hockeyproj', filetypes=[('Проект монтажа', '*.hockeyproj')])
        if path:
            try:
                self.project.save(path)
                self.project_path = path
                self.legacy_project = False
                self.project_label.set(Path(path).name)
                self.status.set('Проект сохранён: ' + str(path))
            except Exception as e:
                messagebox.showerror('Сохранение', str(e))

    def cache_path(self):
        seed = self.project.host + '\n' + self.project.blocks[self.index].title
        key = hashlib.sha256(seed.encode()).hexdigest()[:16]
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.cache'))) / 'HockeyAutoEditor' / 'Cache'
        return base / key

    def open_cache(self):
        try:
            self.collect()
            path = self.cache_path()
            path.mkdir(parents=True, exist_ok=True)
            open_file(path)
        except Exception as e:
            messagebox.showerror('Папка', str(e))

    def details(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('Подробности обработки')
        dialog.geometry('780x440')
        dialog.transient(self.root)
        box = tk.Text(dialog, wrap='word', font=('Consolas', 10), bg=ui.WHITE, fg=ui.INK, padx=16, pady=16)
        box.pack(fill='both', expand=True, padx=14, pady=14)
        messages = self.log_lines + (['\nПроверка разметки:'] + self.plan.warnings if self.plan and self.plan.warnings else [])
        box.insert('1.0', '\n'.join(messages) or 'Обработка ещё не запускалась.')
        box.configure(state='disabled')
        ttk.Button(dialog, text='Открыть папку разметки', command=self.open_cache).pack(side='left', padx=14, pady=(0, 14))
        ttk.Button(dialog, text='Закрыть', command=dialog.destroy).pack(side='right', padx=14, pady=(0, 14))

    def set_busy(self, state):
        if state == self.busy:
            return
        self.busy = state
        for widget in self.controls:
            if state:
                widget._oldstate = str(widget.cget('state'))
                widget.configure(state='disabled')
            else:
                widget.configure(state=getattr(widget, '_oldstate', 'normal'))
        self.cancelbutton.configure(state='normal' if state else 'disabled')
        if state:
            self.progress.configure(mode='indeterminate', value=0)
            self.progress.start(15)
        else:
            self.progress.stop()
            self.progress.configure(mode='determinate', value=100 if self.result else 0)
        self.update_summary()

    def start(self, render):
        if self.busy:
            return
        self.collect()
        try:
            self.project.validate(self.index)
        except Exception as e:
            self.show_page('materials')
            return messagebox.showerror('Проверьте материалы', str(e))
        target = None
        if render:
            target = filedialog.asksaveasfilename(title='Готовый ролик — новое имя файла', defaultextension='.mp4', initialfile='Мой разбор.mp4', filetypes=[('Видео MP4', '*.mp4')])
            if not target:
                return
            if Path(target).exists():
                return messagebox.showinfo('Выберите новое имя', 'Чтобы сохранить предыдущий результат, укажите новое имя MP4.')
        self.invalidate()
        self.log_lines = []
        self.cancel.clear()
        self.stage = 'render' if render else 'analyze'
        self.show_page('export' if render else 'review')
        self.review_summary.set('Ищем фразы в записи ведущего…')
        self.status.set('Начинаю обработку. Можно остановить её кнопкой «Отменить».')
        self.set_busy(True)
        # Snapshot prevents any navigation or future UI addition from mutating an active job.
        engine = Engine(copy.deepcopy(self.project), self.index, self.cache_path(), self.cancel,
                        lambda msg: self.jobs.put(('log', msg)))

        def work():
            try:
                plan = engine.analyze()
                self.jobs.put(('plan', plan))
                if render:
                    self.jobs.put(('result', engine.render(plan, target)))
            except Cancelled:
                self.jobs.put(('log', 'Отменено. Можно изменить настройки и повторить.'))
            except Exception as e:
                self.jobs.put(('error', str(e)))
            finally:
                self.jobs.put(('done', None))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def display_plan(self, plan):
        self.plan = plan
        self.reviewtabs.select(1)
        self.linetable.delete(*self.linetable.get_children())
        for i, line in enumerate(plan.lines):
            check = line.agreement > .8
            self.linetable.insert('', 'end', iid=str(i), values=(f'{ui.timecode(line.start)}–{ui.timecode(line.end)}', line.text, 'Проверить' if check else 'Совпало'),
                                  tags=('check',) if check else ('stripe',) if i % 2 else ())
        uncertain = sum(line.agreement > .8 for line in plan.lines)
        self.review_summary.set(f'{ui.timecode(plan.duration)}  ·  {len(plan.lines)} фраз  ·  {len(plan.inserts)} вставки')
        if plan.warnings:
            self.review_note.set('Обратите внимание: ' + plan.warnings[0] + (f' Ещё замечаний: {len(plan.warnings) - 1}. Откройте «Подробности».' if len(plan.warnings) > 1 else ''))
        elif uncertain:
            self.review_note.set(f'Фраз для проверки: {uncertain}. Они выделены цветом. Оцените совпадение речи и изображения в готовом ролике.')
        else:
            self.review_note.set('Неустойчивых совпадений не обнаружено. После экспорта проверьте речь и игровые моменты в ролике.')
        self.update_summary()

    def poll(self):
        try:
            while True:
                kind, value = self.jobs.get_nowait()
                if self.handle_match_job(kind, value):
                    continue
                if kind == 'log':
                    self.status.set(value)
                    self.log_lines.append(value)
                    progress = re.search(r'(?:Подготовка ведущего|Экспорт|Кадры|Поиск голов): (\d+)%', value)
                    if progress:
                        self.progress.stop()
                        self.progress.configure(mode='determinate', value=int(progress[1]))
                    elif self.busy:
                        self.progress.stop()
                        self.progress.configure(mode='indeterminate')
                        self.progress.start(15)
                elif kind == 'plan':
                    self.display_plan(value)
                elif kind == 'result':
                    self.result = Path(value)
                    self.output_label.set(str(value))
                    self.previewbutton.configure(state='normal')
                    self.folderbutton.configure(state='normal')
                    self.show_page('export')
                    self.status.set('Готово! Нажмите «Открыть результат», чтобы посмотреть ролик.')
                elif kind == 'error':
                    self.log_lines.append(value)
                    messagebox.showerror('Обработка не завершена', value + '\n\nКнопка «Журнал» открывает подробности.')
                    self.status.set('Обработка не завершена. Исходники сохранены.')
                elif kind == 'done':
                    self.set_busy(False)
                    if self.plan is None and self.stage in ('analyze', 'render'):
                        self.review_summary.set('Анализ не завершён. Проверьте журнал и повторите.')
                    elif self.stage == 'analyze':
                        self.show_page('review')
        except queue.Empty:
            pass
        self.poll_id = self.root.after(100, self.poll)

    def preview(self):
        if self.result and Path(self.result).exists():
            try:
                open_file(self.result)
            except Exception as e:
                messagebox.showerror('Просмотр', str(e))

    def result_folder(self):
        if self.result:
            try:
                open_file(Path(self.result).parent)
            except Exception as e:
                messagebox.showerror('Папка результата', str(e))

    def close(self):
        if self.busy:
            if messagebox.askyesno('Идёт обработка', 'Отменить обработку? После остановки можно закрыть окно.'):
                self.cancel.set()
            return
        if self.poll_id:
            self.root.after_cancel(self.poll_id)
        self.root.destroy()


def launch():
    root = tk.Tk()
    App(root)
    root.mainloop()
