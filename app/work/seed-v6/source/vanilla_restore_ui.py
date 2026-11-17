"""Preview and explicit confirmation for restoring managed vanilla files."""
import json,secrets,time
from pathlib import Path
from tkinter import filedialog,messagebox
from boss_install_guard import console_python
from install_state import save,read
from recovery_configuration import configuration
from vanilla_restore import pending_recoveries

def start(app,launch,state,status,preview_mode=False):
 if preview_mode:messagebox.showinfo('Controls preview','Vanilla recovery is unavailable in this controls preview.');return
 config=configuration(state);state=Path(state);out=state/'vanilla-preview.json';result=state/'vanilla-result.json'
 script=Path(__file__).with_name('vanilla_restore.py')
 def command(action):return [str(console_python()),'-u',str(script),action,'--state',str(state),'--output',str(out if action=='plan' else result)]
 pending=pending_recoveries(state)
 if pending:
  if not messagebox.askyesno('Interrupted recovery','An earlier vanilla recovery was interrupted. Roll back its recorded changes from verified backups before trying again?',parent=app):return
  status.set('Recovering the interrupted vanilla operation…')
  def recovered(code):
   if code:status.set('Interrupted recovery could not be rolled back. Keep its journal and backups.');return
   status.set('Interrupted recovery rolled back. Click Restore game to vanilla to check again.')
  launch(command('recover')+['--journal',str(pending[0])],state/'vanilla-interrupted.log',recovered);return
 def checked(code):
  if code not in (0,2) or not out.is_file():status.set('Vanilla check stopped. See the log; game files were not changed.');return
  plan=read(out)
  if not plan['ready']:
   missing=plan['missing_originals']
   if messagebox.askyesno('Preserved originals needed',str(len(missing))+' original files are missing from the available backups.\n\nFirst missing: '+missing[0]+'\n\nChoose another folder containing preserved original game files? No game files have been changed.',parent=app):
    folder=filedialog.askdirectory(parent=app,title='Choose preserved original game files')
    if folder:
     config['sources'].append(Path(folder));save(state/'vanilla-sources.json',dict(folders=[str(p) for p in config['sources']]));check()
   else:status.set('Vanilla recovery needs preserved originals. No game files were changed.')
   return
  text='Restore '+str(plan['restores'])+' managed files to verified original bytes and move '+str(plan['quarantines'])+' randomiser-added audio files into recovery backups?\n\nCurrent files will be backed up first. Saves, seed history and preferences are kept. The original-file cache will also be refreshed from verified vanilla files. This works even if Steam verification changed parts of a seed.\n\nRecovery records: '+str(state/'vanilla-recovery')
  if not messagebox.askyesno('Restore game to vanilla',text,parent=app):status.set('Vanilla recovery cancelled; no game files changed.');return
  status.set('Backing up current files, then restoring verified vanilla files…')
  args=command('apply')+['--plan',str(out),'--game',str(config['game'])]
  if config['originals']:args+=['--originals',str(config['originals'])]
  def finished(rc):
   if rc:status.set('Vanilla recovery stopped. Inspect the log and retained recovery backups.');return
   info=read(result)
   if not info.get('passed'):raise ValueError('Vanilla recovery did not verify completion')
   status.set('Managed vanilla files restored and verified. Saves and seed history kept. Make a new build before attaching helpers.')
   messagebox.showinfo('Vanilla restoration complete','The randomiser-managed game files are back to verified originals. Your saves, settings and existing builds were kept.\n\nBackups: '+info['backup_folder'],parent=app)
  launch(args,state/'vanilla-restore.log',finished)
 def check():
  status.set('Checking managed game files and preserved originals; no game writes…')
  launch(command('plan')+['--game',str(config['game']),'--sources',*[str(p) for p in config['sources']]],state/'vanilla-check.log',checked)
 check()
