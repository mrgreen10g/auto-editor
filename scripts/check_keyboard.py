"""Exercise real Windows keyboard layouts through Tk event dispatch."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import ttk
from hockey_editor.keyboard import install

def check(root=None):
    owns_root=root is None
    if owns_root:root=tk.Tk();install(root)
    from hockey_editor.keyboard import TAG
    clipboard_window=tk.Toplevel(root)
    expected='Русский текст — 19 голов'
    import ctypes
    user32=ctypes.WinDLL('user32',use_last_error=True)
    user32.GetKeyboardLayout.restype=ctypes.c_void_p
    user32.LoadKeyboardLayoutW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint]
    user32.LoadKeyboardLayoutW.restype=ctypes.c_void_p
    user32.ActivateKeyboardLayout.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    user32.ActivateKeyboardLayout.restype=ctypes.c_void_p
    original_layout=user32.GetKeyboardLayout(0)
    russian_layout=user32.LoadKeyboardLayoutW('00000419',0)
    assert russian_layout,'Russian keyboard layout could not be loaded'
    keycodes={'Cyrillic_em':86,'Cyrillic_ef':65,'Cyrillic_es':67,'Cyrillic_che':88,'Cyrillic_ya':90,'Cyrillic_en':89}
    for widget in (tk.Entry(clipboard_window),ttk.Entry(clipboard_window),tk.Text(clipboard_window),
                   tk.Spinbox(clipboard_window),ttk.Spinbox(clipboard_window),ttk.Combobox(clipboard_window)):
        widget.pack();root.update();widget.focus_force();root.update()
        assert widget.bindtags()[0]==TAG
        def value():return widget.get('1.0','end-1c') if isinstance(widget,tk.Text) else widget.get()
        def key(symbol,shift=False):
            russian=symbol in keycodes
            user32.ActivateKeyboardLayout(russian_layout if russian else original_layout,0);root.update()
            if russian:assert user32.GetKeyboardLayout(0)&0xffff==0x419
            code=keycodes[symbol] if russian else ord(symbol.upper())
            widget.event_generate('<KeyPress>',keycode=code,state=4|(1 if shift else 0));root.update()
        if isinstance(widget,tk.Text):widget.delete('1.0','end');widget.edit_reset()
        else:widget.delete(0,'end')
        root.clipboard_clear();root.clipboard_append(expected)
        # Real Tk dispatch, including Cyrillic keysyms, not a direct handler call.
        key('Cyrillic_em');assert value()==expected,(widget.winfo_class(),value())
        key('Cyrillic_ef');key('Cyrillic_es');assert root.clipboard_get()==expected,(widget.winfo_class(),repr(root.clipboard_get()))
        key('Cyrillic_che');assert value()==''
        key('Cyrillic_em');assert value()==expected
        key('Cyrillic_ya');assert value()=='',(widget.winfo_class(),value())
        key('Cyrillic_en');assert value()==expected
        key('Cyrillic_ya');key('Cyrillic_ya',shift=True);assert value()==expected
        # Latin shortcuts must not paste twice.
        key('a');key('v');assert value()==expected
        widget.destroy()
    user32.ActivateKeyboardLayout(original_layout,0)
    clipboard_window.destroy()
    if owns_root:root.destroy()
    print('Russian and Latin clipboard, selection, undo and redo: OK')

if __name__=='__main__':check()
