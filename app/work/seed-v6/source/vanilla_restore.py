"""Recover randomiser-managed originals independently of any seed receipt.

All writes are confined to a pinned catalogue. Existing files are backed up
before changes; replacement bytes are verified and committed atomically.
"""
import argparse,hashlib,json,os,shutil,uuid
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath

CATALOG_SHA256='49cf0c1951a950e5b35c77a3dba9a1d854634f6091062eef769e8725f144e67b'

def sha(path):
 p=Path(path)
 if not p.exists():return None
 if not p.is_file():raise ValueError('Expected a file: '+str(p))
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 temp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temp.open('w',encoding='utf-8',newline='\n') as f:
   json.dump(obj,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(temp,p)
 finally:temp.unlink(missing_ok=True)

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def safe_relative(relative):
 if not isinstance(relative,str) or '\\' in relative or ':' in relative:raise ValueError('Invalid managed path')
 p=PurePosixPath(relative)
 if p.is_absolute() or not p.parts or any(x in ('.','..','') for x in relative.split('/')):raise ValueError('Invalid managed path')
 if relative not in ('ZOE2/STAGE.DAT','atlas/atlas_pc_Zlib.pac','atlas/atlas_pc_jp_Zlib_ps2.pac'):
  if not relative.startswith('sound/Windows/') or p.suffix.lower() not in ('.wem','.bnk','.xml'):raise ValueError('Path is not randomiser-managed: '+relative)
 return relative

def target(root,relative):
 root=Path(root).resolve();relative=safe_relative(relative);p=root.joinpath(*relative.split('/'))
 if not p.resolve().is_relative_to(root) or p.is_symlink():raise ValueError('Managed path escapes its directory: '+relative)
 current=root
 for part in relative.split('/'):
  current=current/part
  if current.is_symlink() or current.is_junction():raise ValueError('Managed paths cannot pass through links: '+relative)
 return p

def load_catalog():
 path=Path(__file__).with_name('vanilla-catalog.json')
 if sha(path)!=CATALOG_SHA256:raise ValueError('Vanilla recovery catalogue is missing or changed. Re-extract the utility.')
 c=read(path)
 if c.get('format')!=1:raise ValueError('Unsupported recovery catalogue')
 for rel,digest in c['files'].items():
  safe_relative(rel)
  if not isinstance(digest,str) or len(digest)!=64:raise ValueError('Invalid original checksum')
 for rel in c['managed_additions']:safe_relative(rel)
 if set(c['files'])&set(c['managed_additions']):raise ValueError('Original/addition catalogue overlap')
 return c

def check_game(game,catalog):
 game=Path(game).resolve()
 if not game.is_dir() or sha(game/'Zoe2Mars.exe')!=catalog['executable_sha256']:
  raise ValueError('The supported ZOE2 executable is missing or different. Select the correct game folder; Steam may be needed for the executable itself.')
 return game

def find_original(relative,digest,sources):
 for root in sources:
  root=Path(root).resolve()
  relatives=[relative]
  if relative.startswith('sound/Windows/'):relatives.append(relative.removeprefix('sound/Windows/'))
  for rel in relatives:
   for suffix in ('','.zoe2-ca01-loader-v1.bak'):
    p=root.joinpath(*rel.split('/')).with_name(PurePosixPath(rel).name+suffix)
    if p.resolve().is_relative_to(root) and not p.is_symlink() and p.is_file() and sha(p)==digest:return str(p.resolve())
 return None

def make_plan(game,sources,catalog,log=print):
 game=check_game(game,catalog);sources=[str(Path(p).resolve()) for p in sources]
 rows=[];missing=[];already=0
 for count,(relative,digest) in enumerate(catalog['files'].items(),1):
  p=target(game,relative);before=sha(p)
  if before==digest:already+=1;continue
  source=find_original(relative,digest,sources)
  rows.append(dict(relative_path=relative,action='restore_original',before_sha256=before,after_sha256=digest,source=source))
  if source is None:missing.append(relative)
  if count%50==0:log('Checked managed original files: '+str(count)+' / '+str(len(catalog['files'])))
 for relative in catalog['managed_additions']:
  before=sha(target(game,relative))
  if before is not None:rows.append(dict(relative_path=relative,action='quarantine_added_file',before_sha256=before,after_sha256=None,source=None))
 return dict(format=1,game_root=str(game),catalog_sha256=hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest(),
  sources=sources,ready=not missing,missing_originals=missing,already_original=already,
  restores=sum(r['action']=='restore_original' for r in rows),quarantines=sum(r['action']=='quarantine_added_file' for r in rows),
  changes=rows,scope=catalog.get('scope','Randomiser-managed files only'),game_files_changed=False)

def validate_plan(plan,catalog):
 if plan.get('format')!=1 or not plan.get('ready') or plan.get('missing_originals'):raise ValueError('Recovery plan is incomplete. Choose a folder containing the missing verified originals.')
 if plan.get('catalog_sha256')!=hashlib.sha256(json.dumps(catalog,sort_keys=True).encode()).hexdigest():raise ValueError('Recovery plan belongs to a different catalogue')
 game=check_game(plan['game_root'],catalog);seen=set()
 for row in plan['changes']:
  relative=row['relative_path'];target(game,relative)
  if relative in seen:raise ValueError('Duplicate recovery target')
  seen.add(relative)
  if relative in catalog['files']:
   if row['action']!='restore_original' or row['after_sha256']!=catalog['files'][relative]:raise ValueError('Recovery target checksum differs from catalogue')
  elif relative in catalog['managed_additions']:
   if row['action']!='quarantine_added_file' or row['after_sha256'] is not None:raise ValueError('Invalid added-file recovery action')
  else:raise ValueError('Recovery target is not in the catalogue')
 return game

def atomic_copy(source,dest,expected):
 dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
 temp=dest.with_name(dest.name+'.zoe2-recovery-'+uuid.uuid4().hex+'.tmp')
 try:
  shutil.copyfile(source,temp)
  if sha(temp)!=expected:raise ValueError('Staged recovery file checksum differs')
  with temp.open('r+b') as f:os.fsync(f.fileno())
  os.replace(temp,dest)
 finally:temp.unlink(missing_ok=True)

def verify_vanilla(game,catalog):
 game=check_game(game,catalog);errors=[]
 for rel,digest in catalog['files'].items():
  if sha(target(game,rel))!=digest:errors.append(rel)
 for rel in catalog['managed_additions']:
  if target(game,rel).exists():errors.append(rel)
 if errors:raise ValueError('Managed vanilla verification failed: '+', '.join(errors[:8]))
 return dict(passed=True,managed_originals=len(catalog['files']),managed_additions_absent=len(catalog['managed_additions']),saves_touched=False,scope=catalog.get('scope'))

def rollback(journal_path,catalog):
 path=Path(journal_path).resolve();j=read(path);game=validate_plan(j['plan'],catalog)
 if j['status'] in ('complete','rolled_back'):return j
 root=path.parent.resolve();written=set(j['written'])
 for row in j['plan']['changes']:
  if row['relative_path'] not in written:continue
  p=target(game,row['relative_path']);actual=sha(p)
  if actual not in (row['before_sha256'],row['after_sha256']):raise ValueError('External file change prevents automatic recovery: '+row['relative_path'])
  if row['before_sha256'] is not None:
   backup=target(root/'before',row['relative_path'])
   if sha(backup)!=row['before_sha256']:raise ValueError('Recovery backup is missing or changed: '+row['relative_path'])
 j['status']='rolling_back';save(path,j)
 for row in reversed(j['plan']['changes']):
  if row['relative_path'] not in written:continue
  p=target(game,row['relative_path'])
  if row['before_sha256'] is None:p.unlink(missing_ok=True)
  else:atomic_copy(target(root/'before',row['relative_path']),p,row['before_sha256'])
  if sha(p)!=row['before_sha256']:raise ValueError('Recovery rollback readback failed')
 j['status']='rolled_back';save(path,j);return j

def pending_recoveries(state):
 return [p for p in (Path(state)/'vanilla-recovery').glob('*/journal.json') if read(p).get('status') not in ('complete','rolled_back')]

def apply_plan(plan,state,catalog,log=print,after_write=None):
 game=validate_plan(plan,catalog);state=Path(state).resolve()
 if state.is_relative_to(game) or game.is_relative_to(state):raise ValueError('Recovery records must be outside the game directory')
 pending=pending_recoveries(state)
 if pending:raise ValueError('An interrupted recovery needs rollback first: '+str(pending[0]))
 # Validate every source and current target before creating the transaction.
 for row in plan['changes']:
  if sha(target(game,row['relative_path']))!=row['before_sha256']:raise ValueError('Game files changed after the preview. Run the check again.')
  if row['after_sha256'] is not None and sha(row['source'])!=row['after_sha256']:raise ValueError('Preserved original changed after the preview')
 ident=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
 root=state/'vanilla-recovery'/ident;root.mkdir(parents=True)
 journal=root/'journal.json';j=dict(format=1,status='backing_up',plan=plan,written=[],created_utc=datetime.now(timezone.utc).isoformat())
 save(journal,j)
 try:
  for row in plan['changes']:
   if row['before_sha256'] is not None:
    p=target(game,row['relative_path']);backup=target(root/'before',row['relative_path']);backup.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,backup)
    if sha(backup)!=row['before_sha256']:raise ValueError('Pre-recovery backup verification failed')
    with backup.open('r+b') as f:os.fsync(f.fileno())
  j['status']='prepared';save(journal,j)
  for count,row in enumerate(plan['changes'],1):
   p=target(game,row['relative_path'])
   if sha(p)!=row['before_sha256']:raise ValueError('Game file changed while preparing recovery')
   j['written'].append(row['relative_path']);j['status']='restoring';save(journal,j)
   if row['after_sha256'] is None:p.unlink(missing_ok=True)
   else:atomic_copy(row['source'],p,row['after_sha256'])
   if sha(p)!=row['after_sha256']:raise ValueError('Restored file readback failed')
   if after_write:after_write(count)
   if count%25==0:log('Restored managed files: '+str(count)+' / '+str(len(plan['changes'])))
  result=verify_vanilla(game,catalog)
  j['status']='complete';j['verification']=result;save(journal,j)
 except Exception:
  rollback(journal,catalog);raise
 return dict(passed=True,game_root=str(game),restored_files=plan['restores'],quarantined_files=plan['quarantines'],journal=str(journal),backup_folder=str(root/'before'),verification=result,saves_touched=False)

def invalidate_receipt(state,result):
 state=Path(state);saved={}
 for name in ('last-applied.json','recommended-build.json','installation-result.json'):
  p=state/name
  if p.is_file():saved[name]=read(p)
 journal=Path(result['journal']);save(journal.parent/'prior-utility-state.json',saved)
 for name in ('last-applied.json','recommended-build.json'):(state/name).unlink(missing_ok=True)
 save(state/'installation-result.json',dict(installed=False,vanilla=True,seed=None,recovery_journal=str(journal),game_root=result['game_root']))

def refresh_originals(originals,game,catalog,recovery_folder):
 originals=Path(originals).resolve();game=check_game(game,catalog);backups=Path(recovery_folder)/'prior-original-cache'
 if originals.is_relative_to(game) or game.is_relative_to(originals):raise ValueError('Original cache must be outside the game directory')
 files=dict(catalog['files']);files['Zoe2Mars.exe']=catalog['executable_sha256'];repaired=0
 def cache_path(root,rel):
  p=Path(root).joinpath(*rel.split('/'))
  if not p.resolve().is_relative_to(Path(root).resolve()) or p.is_symlink():raise ValueError('Original cache path escapes its folder')
  return p
 for rel,digest in files.items():
  src=cache_path(game,rel);dest=cache_path(originals,rel)
  if sha(src)!=digest:raise ValueError('Game changed before original-cache refresh: '+rel)
  if sha(dest)==digest:continue
  if dest.exists():
   backup=cache_path(backups,rel);backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dest,backup)
  atomic_copy(src,dest,digest);repaired+=1
 for name in ('input-index.json','setup-complete.json'):
  p=originals/name
  if p.is_file():
   dest=backups/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 save(originals/'input-index.json',files);save(originals/'setup-complete.json',dict(passed=True,inputs=len(files),catalog_sha256=CATALOG_SHA256))
 return dict(passed=True,repaired_files=repaired,verified_originals=len(files))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['plan','apply','recover']);ap.add_argument('--game');ap.add_argument('--state',required=True);ap.add_argument('--sources',nargs='*',default=[]);ap.add_argument('--plan');ap.add_argument('--output',required=True);ap.add_argument('--journal')
 ap.add_argument('--originals');args=ap.parse_args();catalog=load_catalog()
 from recovery_configuration import game_running
 if game_running():raise ValueError('Close ZOE2 completely before checking or restoring vanilla files.')
 if args.action=='plan':result=make_plan(args.game,args.sources,catalog)
 elif args.action=='apply':
  result=apply_plan(read(args.plan),args.state,catalog);invalidate_receipt(args.state,result)
  if args.originals:result['original_cache']=refresh_originals(args.originals,args.game or result['game_root'],catalog,Path(result['journal']).parent)
 else:result=rollback(args.journal,catalog)
 save(args.output,result)
 summary={k:result[k] for k in ('ready','passed','restores','quarantines','already_original','missing_originals','restored_files','quarantined_files','backup_folder','status') if k in result}
 summary['report']=str(Path(args.output).resolve());print(json.dumps(summary,indent=2))
 return 0 if result.get('ready',result.get('passed',True)) else 2

if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:print('Vanilla recovery stopped: '+str(e),flush=True);raise SystemExit(1)
