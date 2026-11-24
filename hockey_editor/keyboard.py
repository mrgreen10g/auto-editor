"""Layout-independent shortcuts run BEFORE Tk's native text class bindings."""
import sys
import tkinter as tk

EVENTS={65:'<<SelectAll>>',67:'<<Copy>>',86:'<<Paste>>',88:'<<Cut>>',90:'<<Undo>>',89:'<<Redo>>'}
TEXT_CLASSES=('Entry','TEntry','Text','Spinbox','TSpinbox','TCombobox')
TAG='AutoEditorTextKeys'
CYRILLIC={'Cyrillic_ef':65,'Cyrillic_es':67,'Cyrillic_em':86,'Cyrillic_che':88,'Cyrillic_ya':90,'Cyrillic_en':89}
CYRILLIC={k.lower():v for k,v in CYRILLIC.items()}

def _remember(widget):
    if widget.winfo_class()=='Text':return
    value=widget.get()
    history=getattr(widget,'_text_history',None)
    if history is None:widget._text_history=([value],0);return
    rows,index=history
    if rows[index]==value:return
    rows=rows[:index+1]+[value]
    # Bound memory in long script/path fields.
    while len(rows)>64 or len(rows)>1 and sum(map(len,rows))>2000000:rows.pop(0)
    widget._text_history=(rows,len(rows)-1)

def _undo_entry(widget,redo):
    _remember(widget)
    rows,index=widget._text_history
    target=index+(1 if redo else -1)
    if not 0<=target<len(rows):return
    widget.delete(0,'end');widget.insert(0,rows[target]);widget.icursor('end')
    widget._text_history=(rows,target)

def shortcut(event,windows=None):
    if windows is None:windows=sys.platform=='win32'
    if not windows or not event.state & 0x4 or event.state & (0x8|0x20000):return None
    code=CYRILLIC.get(str(event.keysym).lower(),event.keycode)
    virtual=EVENTS.get(code)
    if not virtual:return None
    if code==90 and event.state & 1:virtual='<<Redo>>'
    widget=event.widget
    try:
        kind=widget.winfo_class()
        if kind not in TEXT_CLASSES:return None
        readonly=str(widget.cget('state')) in ('disabled','readonly')
        if readonly and virtual not in ('<<Copy>>','<<SelectAll>>'):return 'break'
        if kind!='Text' and hasattr(widget,'get'):_remember(widget)
        if kind!='Text' and virtual in ('<<Undo>>','<<Redo>>') and hasattr(widget,'get'):
            _undo_entry(widget,virtual=='<<Redo>>')
        else:
            if kind=='Text' and virtual in ('<<Paste>>','<<Cut>>') and hasattr(widget,'edit_separator'):widget.edit_separator()
            widget.event_generate(virtual)
            if kind=='Text' and virtual in ('<<Paste>>','<<Cut>>') and hasattr(widget,'edit_separator'):widget.edit_separator()
        if kind!='Text' and hasattr(widget,'get'):_remember(widget)
        return 'break'  # Also consume Latin shortcuts: exactly one action.
    except tk.TclError:return 'break'

def attach(widget):
    try:
        kind=widget.winfo_class()
        if kind not in TEXT_CLASSES:return
        tags=widget.bindtags()
        if TAG not in tags:widget.bindtags((TAG,*tags))
        if kind=='Text':
            if not widget.cget('undo'):widget.configure(undo=True,maxundo=64)
        else:_remember(widget)
    except tk.TclError:pass

def install(root):
    if sys.platform!='win32':return
    def press(event):
        result=shortcut(event)
        if result=='break':return result
        # Capture ordinary typing too, including typing with Cyrillic layout.
        try:
            if event.widget.winfo_class()!='Text':
                _remember(event.widget)
                event.widget.after_idle(lambda:_safe_remember(event.widget))
        except tk.TclError:pass
    root.bind_class(TAG,'<KeyPress>',press)
    # Map handles every newly-created dialog. Focus handles widgets mapped earlier.
    root.bind_all('<Map>',lambda event:attach(event.widget),add='+')
    root.bind_all('<FocusIn>',lambda event:attach(event.widget),add='+')
    def visit(widget):
        attach(widget)
        for child in widget.winfo_children():visit(child)
    visit(root)

def _safe_remember(widget):
    try:_remember(widget)
    except tk.TclError:pass
