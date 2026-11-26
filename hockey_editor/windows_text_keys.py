"""Translate this GUI thread's physical shortcuts without re-entering Tcl.

The Windows hook must never call Tk: GetMessage may run while Tcl has released
its interpreter lock. It only queues keys; a normal Tk timer applies the edit.
"""
import ctypes as c
from ctypes import wintypes as w
from collections import deque
import tkinter as tk


def install(root):
 from .keyboard import TEXT_CLASSES,EVENTS,shortcut,attach
 from types import SimpleNamespace
 user=c.WinDLL('user32',use_last_error=True);kernel=c.WinDLL('kernel32',use_last_error=True)
 LRESULT=c.c_ssize_t
 CALLBACK=c.WINFUNCTYPE(LRESULT,c.c_int,w.WPARAM,w.LPARAM)
 class MSG(c.Structure):
  _fields_=[('hwnd',w.HWND),('message',w.UINT),('wParam',w.WPARAM),('lParam',w.LPARAM),('time',w.DWORD),('pt',w.POINT),('lPrivate',w.DWORD)]
 user.SetWindowsHookExW.argtypes=[c.c_int,CALLBACK,w.HINSTANCE,w.DWORD];user.SetWindowsHookExW.restype=w.HHOOK
 user.CallNextHookEx.argtypes=[w.HHOOK,c.c_int,w.WPARAM,w.LPARAM];user.CallNextHookEx.restype=LRESULT
 user.UnhookWindowsHookEx.argtypes=[w.HHOOK];user.UnhookWindowsHookEx.restype=w.BOOL
 user.GetKeyState.argtypes=[c.c_int];user.GetKeyState.restype=c.c_short
 user.GetFocus.restype=w.HWND
 user.MapVirtualKeyW.argtypes=[w.UINT,w.UINT];user.MapVirtualKeyW.restype=w.UINT
 kernel.GetCurrentThreadId.restype=w.DWORD
 handle=None;pending=deque();focused=[None,None];timer=[None]
 def focus(event):
  try:
   field=event.widget
   if field.winfo_class() in TEXT_CLASSES:
    attach(field);focused[:]=[field,user.GetFocus()]
   else:focused[:]=[None,None]
  except tk.TclError:focused[:]=[None,None]
 def drain():
  while pending:
   field,key,state=pending.popleft()
   try:
    if field.winfo_exists():shortcut(SimpleNamespace(widget=field,state=state,keycode=key,keysym=''),windows=True)
   except tk.TclError:pass
  if getattr(root,'_native_text_keys',None):timer[0]=root.after(5,drain)
 def dispatch(code,wp,lp):
  # No Tcl/Tk calls here, including focus_get(), after() or event_generate().
  if code>=0 and wp==1 and focused[0] is not None:
   msg=c.cast(lp,c.POINTER(MSG)).contents
   if msg.message==0x100 and msg.hwnd==focused[1] and user.GetFocus()==focused[1] and user.GetKeyState(0x11)<0 and user.GetKeyState(0x12)>=0:
    scan=(msg.lParam>>16)&0xff
    key=user.MapVirtualKeyW(scan,3) if scan else int(msg.wParam)
    if key in EVENTS:
     pending.append((focused[0],key,4|(1 if user.GetKeyState(0x10)<0 else 0)))
     msg.message=0;msg.wParam=0;msg.lParam=0
  return user.CallNextHookEx(handle,code,wp,lp)
 callback=CALLBACK(dispatch)
 handle=user.SetWindowsHookExW(3,callback,None,kernel.GetCurrentThreadId())
 if not handle:return False
 root._native_text_keys=(handle,callback)
 root.bind_all('<FocusIn>',focus,add='+')
 timer[0]=root.after(5,drain)
 def close(event):
  if event.widget is root and getattr(root,'_native_text_keys',None):
   user.UnhookWindowsHookEx(root._native_text_keys[0]);root._native_text_keys=None
   pending.clear();focused[:]=[None,None]
   if timer[0]:root.after_cancel(timer[0])
 root.bind('<Destroy>',close,add='+')
 return True
