import portable_paths as _portable
"""Locate recovery inputs without changing game or utility state."""
import ctypes,json,os
from ctypes import wintypes
from pathlib import Path

def game_running():
 class Entry(ctypes.Structure):
  _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateToolhelp32Snapshot.argtypes=[wintypes.DWORD,wintypes.DWORD];k.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
 k.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];k.Process32FirstW.restype=wintypes.BOOL
 k.Process32NextW.argtypes=k.Process32FirstW.argtypes;k.Process32NextW.restype=wintypes.BOOL
 k.CloseHandle.argtypes=[wintypes.HANDLE];k.CloseHandle.restype=wintypes.BOOL
 handle=k.CreateToolhelp32Snapshot(2,0)
 if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
 try:
  entry=Entry();entry.dwSize=ctypes.sizeof(entry);success=k.Process32FirstW(handle,ctypes.byref(entry))
  if not success:raise ctypes.WinError(ctypes.get_last_error())
  while success:
   if entry.szExeFile.lower()=='zoe2mars.exe':return True
   success=k.Process32NextW(handle,ctypes.byref(entry))
  if ctypes.get_last_error()!=18:raise ctypes.WinError(ctypes.get_last_error())
  return False
 finally:k.CloseHandle(handle)

def configuration(state):
 state=Path(state).resolve();sources=[];originals=None
 try:
  import portable_paths as pp
  game=pp.game();originals=pp.ORIGINALS;sources.extend([pp.HOME/'vanilla-recovery-originals',originals])
 except ImportError:
  from archive_tools import W,L
  game=Path(str(_portable.game()))
  sources.extend([Path(str(_portable.ORIGINALS)),W/'2026-10-18-preview/backups',W/'seed-v6/audio-clean-originals',W/'full-preview-v3/Full-Preview-v3/audio/clean-originals',L/'Audio-Shuffle-v1/originals'])
 base=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))
 for name in ['ZOE2 Randomiser Local 5','ZOE2 Randomiser Beta','ZOE2 Randomiser Emergency Beta','ZOE2 Randomiser Diagnostic Beta 4','ZOE2 Randomiser Diagnostic Beta 5']:
  sources.append(base/name/'originals')
 config=state/'vanilla-sources.json'
 if config.is_file():sources.extend(Path(p) for p in json.loads(config.read_text())['folders'])
 unique=[]
 for p in sources:
  p=Path(p).resolve()
  if p.is_dir() and p not in unique:unique.append(p)
 return dict(game=Path(game).resolve(),state=state,sources=unique,originals=originals)
