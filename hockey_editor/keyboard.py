"""Clipboard shortcuts on Windows regardless of the active keyboard layout."""
import sys
import tkinter as tk

EVENTS={65:'<<SelectAll>>',67:'<<Copy>>',86:'<<Paste>>',88:'<<Cut>>'}

def shortcut(event,windows=None):
    if windows is None:windows=sys.platform=='win32'
    if not windows or not event.state & 0x4 or event.state & (0x8|0x20000):return None
    virtual=EVENTS.get(event.keycode)
    if not virtual:return None
    # The native class binding has already handled Latin Ctrl+V/C/X/A.
    if str(event.keysym).lower()==chr(event.keycode).lower():return None
    widget=event.widget
    try:
        if widget.winfo_class() not in ('Entry','TEntry','Text','Spinbox','TSpinbox','TCombobox'):return None
        if str(widget.cget('state')) in ('disabled','readonly') and virtual in ('<<Paste>>','<<Cut>>'):return 'break'
        widget.event_generate(virtual)
        return 'break'
    except tk.TclError:return None

def install(root):
    if sys.platform=='win32':root.bind_all('<Control-KeyPress>',shortcut,add='+')
