"""Pristine input capture and an allowlisted diagnostic export; no game writes."""
import ctypes,hashlib,json,os,re,shutil,subprocess,zipfile
from ctypes import wintypes
from datetime import datetime,timezone
from pathlib import Path
import portable_paths as pp
from build_info import VERSION
STAGE='c5627420319bbaa28f887b0728e14277befd9cf33ced3f82d0e304b389d5e651'
EXE='b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92'
ATLASES={'atlas_pc_jp_Zlib_ps2.pac':'6935098b6f08fbd18abc41c6f945df9b6a2fc1555a3b9b1227ca00f0028b81f5','atlas_pc_Zlib.pac':'96a9e3049fa90679c2ce24aa709f8377a373b5409be090552c56f67f9486debe'}
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8');os.replace(temp,path)
def running():
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
        entry=Entry();entry.dwSize=ctypes.sizeof(entry)
        success=k.Process32FirstW(handle,ctypes.byref(entry))
        if not success:raise ctypes.WinError(ctypes.get_last_error())
        while success:
            if entry.szExeFile.lower()=='zoe2mars.exe':return True
            success=k.Process32NextW(handle,ctypes.byref(entry))
        if ctypes.get_last_error()!=18:raise ctypes.WinError(ctypes.get_last_error())
        return False
    finally:k.CloseHandle(handle)
def choose_game(path):
    game=Path(path).resolve()
    for rel in ['Zoe2Mars.exe','ZOE2/STAGE.DAT','sound/Windows/SoundbanksInfo.xml',*('atlas/'+n for n in ATLASES)]:
        if not (game/rel).is_file():raise ValueError('Select the game folder containing Zoe2Mars.exe. Missing '+rel)
    if sha(game/'Zoe2Mars.exe')!=EXE:raise ValueError('This game executable is unsupported. This beta requires the recorded Steam Windows ZOE2 MARS version.')
    previous=json.loads(pp.CONFIG.read_text()) if pp.CONFIG.exists() else {}
    if previous and Path(previous['game_root'])!=game:
        state=pp.STATE/'last-applied.json'
        if state.exists() and json.loads(state.read_text(encoding='utf-8-sig')).get('package'):
            raise ValueError('Restore every applied seed before changing game folders.')
    save(pp.CONFIG,dict(format=1,game_root=str(game),executable_sha256=EXE))
    return game
def prepare(log=print):
    if running():raise ValueError('Close ZOE2 completely before building a seed.')
    from vanilla_restore import load_catalog,CATALOG_SHA256
    catalog=load_catalog();game=pp.game();choose_game(game)
    required=dict(catalog['files']);required['Zoe2Mars.exe']=catalog['executable_sha256']
    index_path=pp.ORIGINALS/'input-index.json'
    index=json.loads(index_path.read_text()) if index_path.exists() else {}
    for number,(rel,expected) in enumerate(required.items(),1):
        source=game/rel;dest=pp.ORIGINALS/rel
        if dest.is_file():
            if sha(dest)!=expected:raise ValueError('A preserved original is not clean: '+rel+'. Use Restore game to vanilla to recover the game and original-file cache from verified backups.')
        else:
            if not source.is_file() or sha(source)!=expected:raise ValueError('A verified original is needed: '+rel+'. Use Restore game to vanilla, or choose a folder containing preserved original files. Reinstalling may not remove loose randomiser files.')
            dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_suffix(dest.suffix+'.partial')
            shutil.copyfile(source,temp)
            if sha(temp)!=expected:raise ValueError('Original snapshot copy failed: '+rel)
            os.replace(temp,dest)
        index[rel]=expected
        if number%25==0:log('Verified original inputs: '+str(number)+' / '+str(len(required)))
    save(index_path,{rel:index[rel] for rel in required})
    save(pp.ORIGINALS/'setup-complete.json',dict(passed=True,inputs=len(required),catalog_sha256=CATALOG_SHA256))
    log('Original game inputs verified. Building locally; game files remain unchanged until Apply.')
    return dict(passed=True,inputs=len(required),original_stage_sha256=STAGE)

def pristine_audio(rel):
    target=(pp.ORIGINALS/'sound/Windows'/rel).resolve()
    if not target.is_relative_to(pp.ORIGINALS.resolve()):raise ValueError('Invalid audio path')
    index=json.loads((pp.ORIGINALS/'input-index.json').read_text())
    if sha(target)!=index['sound/Windows/'+rel]:raise ValueError('Original audio input hash differs: '+rel)
    return target.read_bytes()
def export_report(destination,current=None):
    allowed=['viper-combat-contract.json','proximity-fix-contract.json','build-result.json','randomisation-settings.json','effective-settings.json','release-policy.json','boss-mapping.json','side-modes.json','enemy-mapping.json','subweapon-mapping.json','build-provenance.json','installation-plan.json','installation-journal.json','last-attachment.json','original-inputs.json','boss-spawn-check.json','finite-mosquito-tests.json','verification-boss-test.json','verification-side-modes.json','health-boss-targets.tsv']
    files=[]
    if pp.BUILD_ROOT.exists():
        recent=sorted(pp.BUILD_ROOT.glob('*.log'),key=lambda f:f.stat().st_mtime,reverse=True)[:10]
        files.extend((f,'recent-logs/'+f.name) for f in recent)
        profiles=sorted(pp.BUILD_ROOT.glob('*-settings.json'),key=lambda f:f.stat().st_mtime,reverse=True)[:3]
        files.extend((f,'requested-settings/'+f.name) for f in profiles)
    if current:
        p=Path(current).resolve()
        if not p.is_relative_to(pp.BUILD_ROOT.resolve()):raise ValueError('Selected build is outside this beta data folder')
        files.extend((p/n,'build/'+n) for n in allowed if (p/n).is_file())
        for directory in [p/'verification',p/'reports']:
            if directory.is_dir():files.extend((f,'build/'+f.relative_to(p).as_posix()) for f in directory.glob('*.json') if not f.is_symlink())
        files.extend((f,'logs/'+f.name) for f in p.glob('*.log'))
        files.extend((f,'logs/'+f.name) for f in pp.BUILD_ROOT.glob(p.parent.name+'*.log'))
    if current:
        for captures in [p/'captures',p/'runtime/captures']:
            if not captures.is_dir() or not captures.resolve().is_relative_to(p):continue
            for folder in sorted((f for f in captures.iterdir() if f.is_dir() and not f.is_symlink() and f.resolve().is_relative_to(p)),key=lambda f:f.stat().st_mtime,reverse=True)[:2]:
                selected=[f for f in folder.glob('recent-*.json') if not f.is_symlink() and f.resolve().is_relative_to(p)]
                selected += [folder/n for n in ['viola-deletion-events.jsonl','stage-observations.jsonl'] if (folder/n).is_file() and (folder/n).resolve().is_relative_to(p)]
                files.extend((f,'captures/'+folder.name+'/'+f.name) for f in selected)
    prefs=pp.STATE/'preferences.json'
    if prefs.exists():files.append((prefs,'preferences.json'))
    replacements=[(str(pp.HOME),'<BETA_DATA>'),(str(pp.game()),'<GAME>'),(str(pp.PACKAGE),'<APP>'),(str(Path.home()),'<USER>')]
    def redact(text):
        for raw,replacement in replacements:
            for value in [raw,raw.replace('\\','/'),raw.replace('\\','\\\\'),json.dumps(raw)[1:-1],json.dumps(raw.replace('\\','/'))[1:-1]]:text=text.replace(value,replacement)
        return text
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED) as z:
        z.writestr('report.json',json.dumps(dict(format=1,version=VERSION,created_utc=datetime.now(timezone.utc).isoformat(),game_assets_included=False,saves_included=False,dumps_included=False,paths_redacted=True),indent=2))
        for f,name in files:
            if not f.is_symlink() and f.stat().st_size<=8*1024*1024:z.writestr(name,redact(f.read_text(encoding='utf-8-sig',errors='replace')))
    return str(destination)
