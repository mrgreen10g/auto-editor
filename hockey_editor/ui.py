"""Native, dependency-free visual components for the desktop workspace."""
import tkinter as tk
from tkinter import ttk

BG = '#F2F5F8'
WHITE = '#FFFFFF'
INK = '#182C3A'
MUTED = '#596D7C'
LINE = '#DCE4EA'
TEAL = '#087F83'
PALE = '#E7F5F2'
NAV = '#122733'
NAV_MUTED = '#A8BDC8'


def theme(root):
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), background=BG, foreground=INK)
    style.configure('TFrame', background=BG)
    style.configure('Card.TFrame', background=WHITE)
    style.configure('TLabel', background=BG, foreground=INK)
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Heading.TLabel', font=('Segoe UI', 23, 'bold'))
    style.configure('Card.TLabel', background=WHITE)
    style.configure('CardTitle.TLabel', background=WHITE, font=('Segoe UI', 12, 'bold'))
    style.configure('CardMuted.TLabel', background=WHITE, foreground=MUTED, font=('Segoe UI', 9))
    style.configure('TButton', padding=(12, 8), background=WHITE, bordercolor=LINE,
                    lightcolor=WHITE, darkcolor=WHITE, focuscolor=TEAL)
    style.map('TButton', background=[('active', PALE)], foreground=[('disabled', '#9AA8B2')])
    style.configure('Primary.TButton', background=TEAL, foreground=WHITE,
                    bordercolor=TEAL, lightcolor=TEAL, darkcolor=TEAL, font=('Segoe UI', 10, 'bold'))
    style.map('Primary.TButton', background=[('disabled', '#C8D7DA'), ('active', '#09686D')],
              foreground=[('disabled', '#526973'), ('!disabled', WHITE)])
    style.configure('TEntry', padding=8, fieldbackground=WHITE, bordercolor=LINE,
                    lightcolor=LINE, darkcolor=LINE, insertcolor=INK)
    style.configure('TCombobox', padding=7, fieldbackground=WHITE, background=WHITE,
                    bordercolor=LINE, arrowcolor=MUTED)
    style.map('TCombobox', fieldbackground=[('readonly', WHITE), ('disabled', BG)],
              foreground=[('readonly', INK)])
    style.configure('TCheckbutton', background=WHITE, padding=(0, 5), indicatorcolor=WHITE)
    style.map('TCheckbutton', background=[('active', WHITE)],
              indicatorcolor=[('selected', TEAL), ('disabled', LINE)])
    style.configure('Treeview', background=WHITE, fieldbackground=WHITE, foreground=INK,
                    borderwidth=0, rowheight=36, font=('Segoe UI', 10))
    style.map('Treeview', background=[('selected', '#D7EEEA')], foreground=[('selected', INK)])
    style.configure('Treeview.Heading', background=BG, foreground=MUTED,
                    font=('Segoe UI', 9, 'bold'), padding=(10, 10), relief='flat')
    style.map('Treeview.Heading', background=[('active', '#E6EDF2')])
    style.configure('Horizontal.TProgressbar', background=TEAL, troughcolor=LINE,
                    borderwidth=0, lightcolor=TEAL, darkcolor=TEAL)
    style.configure('TScrollbar', background='#D0DBE3', troughcolor=BG,
                    borderwidth=0, arrowcolor=MUTED, arrowsize=12)
    return style


class ScrollPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.content = ttk.Frame(self.canvas, padding=(0, 0, 14, 12))
        self.window = self.canvas.create_window(0, 0, window=self.content, anchor='nw')
        self.content.bind('<Configure>', lambda _: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))

    def scroll(self, delta):
        if self.content.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(delta, 'units')


def card(parent, title, subtitle='', number=None):
    outer = tk.Frame(parent, bg=WHITE, highlightbackground=LINE, highlightthickness=1)
    outer.pack(fill='x', pady=(0, 14))
    inner = ttk.Frame(outer, style='Card.TFrame', padding=18)
    inner.pack(fill='both', expand=True)
    header = ttk.Frame(inner, style='Card.TFrame')
    header.pack(fill='x', pady=(0, 12))
    if number:
        tk.Label(header, text=number, bg=PALE, fg=TEAL, padx=8, pady=4,
                 font=('Segoe UI', 10, 'bold')).pack(side='left', padx=(0, 10))
    if subtitle:
        help_label=tk.Label(header,text='?',bg=PALE,fg=TEAL,font=('Segoe UI',10,'bold'),padx=6,cursor='hand2')
        help_label.pack(side='right',anchor='n',padx=(8,0))
        Tooltip(help_label,subtitle)
    captions = ttk.Frame(header, style='Card.TFrame')
    captions.pack(side='left', fill='x', expand=True)
    ttk.Label(captions, text=title, style='CardTitle.TLabel').pack(anchor='w')
    if subtitle:
        label = ttk.Label(captions, text=subtitle, style='CardMuted.TLabel', wraplength=620)
        label.pack(anchor='w', pady=(4, 0))
        captions.bind('<Configure>', lambda e: label.configure(wraplength=max(150, e.width)))
    return inner


def table(parent, columns, height=5):
    frame = ttk.Frame(parent, style='Card.TFrame')
    frame.pack(fill='both', expand=True)
    view = ttk.Treeview(frame, columns=[c[0] for c in columns], show='headings', height=height)
    for key, caption, width in columns:
        view.heading(key, text=caption)
        view.column(key, width=width, minwidth=70, stretch=key in ('text', 'file', 'phrase'))
    vbar = ttk.Scrollbar(frame, orient='vertical', command=view.yview)
    hbar = ttk.Scrollbar(frame, orient='horizontal', command=view.xview)
    view.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
    view.grid(row=0, column=0, sticky='nsew')
    vbar.grid(row=0, column=1, sticky='ns')
    hbar.grid(row=1, column=0, sticky='ew')
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    view.tag_configure('stripe', background='#F7F9FB')
    view.tag_configure('check', foreground='#965B0B', background='#FFF5E4')
    return view


def timecode(seconds):
    seconds = max(0, round(seconds))
    return f'{seconds // 60:02}:{seconds % 60:02}'


class Tooltip:
    def __init__(self, widget, text):
        self.widget=widget;self.text=text;self.pending=None;self.popup=None
        widget.bind('<Enter>',self.schedule,add='+')
        widget.bind('<Leave>',self.hide,add='+')
        widget.bind('<ButtonPress>',self.hide,add='+')
        widget.bind('<Destroy>',self.hide,add='+')
        widget._tooltip=self

    def schedule(self, _=None):
        self.hide();self.pending=self.widget.after(550,self.show)

    def show(self):
        self.pending=None
        if not self.widget.winfo_exists(): return
        self.popup=tk.Toplevel(self.widget);self.popup.overrideredirect(True)
        label=tk.Label(self.popup,text=self.text,bg='#173345',fg='white',font=('Segoe UI',10),
                       wraplength=340,justify='left',padx=12,pady=9)
        label.pack();self.popup.update_idletasks()
        x=min(self.widget.winfo_rootx(),self.widget.winfo_screenwidth()-self.popup.winfo_width()-12)
        y=min(self.widget.winfo_rooty()+self.widget.winfo_height()+6,self.widget.winfo_screenheight()-self.popup.winfo_height()-12)
        self.popup.geometry(f'+{max(0,x)}+{max(0,y)}')

    def hide(self, _=None):
        if self.pending:
            try: self.widget.after_cancel(self.pending)
            except tk.TclError: pass
            self.pending=None
        if self.popup:
            try: self.popup.destroy()
            except tk.TclError: pass
            self.popup=None


BUTTON_HELP={
    'search_matches':'Ищет голы и обычную игру. Если точный гол не найден, подбирает резервную игровую сцену.',
    'add_matches':'Добавьте одну или несколько записей. Названия команд обязательны, дата — нет.',
    'reuse_match':'Используйте запись из другого разбора без повторной загрузки.',
    'score_region':'Необязательная настройка: выделите две цифры счёта, если они не распознаются.',
    'edit_event':'Посмотрите выбранный фрагмент, замените запись или поправьте границы.',
    'skip_event':'Явно отключает вставку для этой фразы и оставляет ведущего.',
    'edit_card':'Изменяет краткий текст плашки. Пустой текст отключает плашку.',
    'save':'Сохраняет настройки, ссылки на исходники и выбранные эпизоды. Сами видео остаются на диске.',
    'primary_action':'Следующий шаг: подбор игры, тайминги речи или экспорт выбранного разбора.',
}
