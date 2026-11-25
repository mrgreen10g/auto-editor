"""Intercept Windows thread keyboard messages before Tk layout translation.

Only this GUI thread and focused editable Tk fields are affected. No global hook.
"""
import ctypes as c
from ctypes import wintypes as w
import tkinter as tk


def install(root):
 from .keyboard import TEXT_CLASSES,EVENTS,shortcut,attach
 user=c.WinDLL('user32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
 LRESULT=c.c_ssize_t
 CALLBACK=c.WINFUNCTYPE(LRESULT,c.c_int,w.WPARAM,w.LPARAM)
 class MSG(c.Structure):
  _fields_=[('hwnd',w.HWND),('message',w.UINT),('wParam',w.WPARAM),('lParam',w.LPARAM),('time',w.DWORD),('pt',w.POINT),('lPrivate',w.DWORD)]
 user.SetWindowsHookExW.argtypes=[c.c_int,CALLBACK,w.HINSTANCE,w.DWORD];user.SetWindowsHookExW.restype=w.HHOOK
 user.CallNextHookEx.argtypes=[w.HHOOK,c.c_int,w.WPARAM,w.LPARAM];user.CallNextHookEx.restype=LRESULT
 user.UnhookWindowsHookEx.argtypes=[w.HHOOK];user.UnhookWindowsHookEx.restype=w.BOOL
 user.GetKeyState.argtypes=[c.c_int];user.GetKeyState.restype=c.c_short
 user.MapVirtualKeyW.argtypes=[w.UINT,w.UINT];user.MapVirtualKeyW.restype=w.UINT
 kernel.GetCurrentThreadId.restype=w.DWORD
 from types import SimpleNamespace
 handle=None
 def dispatch(code,wp,lp):
  try:
   if code>=0 and wp==1: # PM_REMOVE: never act on a PeekMessage probe.
    msg=c.cast(lp,c.POINTER(MSG)).contents
    if msg.message==0x100 and user.GetKeyState(0x11)<0 and user.GetKeyState(0x12)>=0:
     # Hardware scan code remains stable under RU, EN and remote desktop layouts.
     scan=(msg.lParam>>16)&0xff
     key=user.MapVirtualKeyW(scan,3) if scan else int(msg.wParam)
     if key in EVENTS:
      field=root.focus_get()
      if field is not None and field.winfo_class() in TEXT_CLASSES:
       attach(field)
       event=SimpleNamespace(widget=field,state=4|(1 if user.GetKeyState(0x10)<0 else 0),keycode=key,keysym='')
       if shortcut(event,windows=True)=='break':
        msg.message=0 # Do not let TranslateMessage/Tk perform a second action.
        msg.wParam=0;msg.lParam=0
  except (tk.TclError,AttributeError,ValueError):pass
  return user.CallNextHookEx(handle,code,wp,lp)
 callback=CALLBACK(dispatch)
 handle=user.SetWindowsHookExW(3,callback,None,kernel.GetCurrentThreadId()) # WH_GETMESSAGE
 if not handle:return False
 root._native_text_keys=(handle,callback)
 def close(event):
  if event.widget is root and getattr(root,'_native_text_keys',None):
   user.UnhookWindowsHookEx(root._native_text_keys[0]);root._native_text_keys=None
 root.bind('<Destroy>',close,add='+')
 return True
