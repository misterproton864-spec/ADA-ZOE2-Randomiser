import portable_paths as _portable
"""Windows seed utility. Process completion and installation evidence are separate."""
import json, os, secrets, subprocess, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from boss_install_guard import console_python
from install_state import read, commit, save
from build_info import BUILD_ID, VERSION
from settings_contract import normalise,effective,save_profile,load_profile
from attachment_state import inspect as inspect_attachment
from randomizer_settings import ENEMIES,DEFAULT_WEIGHTS,LOCKED_ENEMIES,BOSSES,DEFAULT_BOSSES,WEAPONS,enemy_weights,boss_selection,weapon_selection
from experimental_bosses import NEITH_LABEL,neith_selection,neith_status,neith_readiness,require_neith_available
ROOT=_portable.STATE
BUILD_ROOT=Path(str(_portable.BUILD_ROOT))
ATTACH_LOG_ROOT=Path(str(_portable.HOME / 'diagnostics'))

def main():
 app=tk.Tk();app.title(f'ZOE2 Randomiser — v{VERSION} Beta Tester Edition');app.geometry('1180x920');app.minsize(1000,800)
 seed=tk.StringVar(value='zoe2-'+secrets.token_hex(8));status=tk.StringVar(value='Portable beta: choose settings, Build, then Apply. New changes need gameplay testing.')
 preview_mode=(ROOT/'tester-preview.json').is_file()
 if preview_mode:status.set('Tester controls preview • Game builds, installation and helpers are unavailable. Neith original-AI port is in progress.')
 viola=tk.BooleanVar(value=False)
 neith=tk.BooleanVar(value=False)
 levels=tk.BooleanVar(value=False)
 native_bosses=tk.BooleanVar(value=False)
 music=tk.BooleanVar(value=True);ada=tk.BooleanVar(value=True);chance=tk.IntVar(value=20)
 inhert=tk.BooleanVar(value=False);spider=tk.BooleanVar(value=False);mosquito=tk.BooleanVar(value=False)
 valley=tk.BooleanVar(value=False);ensure_mosquito=tk.BooleanVar(value=False)
 repeats=tk.BooleanVar(value=False)
 sequence=tk.BooleanVar(value=False);survival=tk.BooleanVar(value=False);extra=tk.BooleanVar(value=False)
 enemy_health=tk.IntVar(value=1);boss_health=tk.IntVar(value=1)
 weights={name:tk.IntVar(value=value) for name,value in DEFAULT_WEIGHTS.items()}
 bosses={name:tk.BooleanVar(value=name in DEFAULT_BOSSES) for name in BOSSES if name!='Viola AI (full rescue fight)'}
 weapons={ident:tk.BooleanVar(value=True) for ident in WEAPONS}
 current=None;process=None;logfiles=[];handles=[]
 for recommended in (ROOT/'last-built.json',ROOT/'recommended-build.json'):
  if not recommended.exists():continue
  try:
   candidate=Path(read(recommended)['package'])
   if (candidate/'build-result.json').exists():current=candidate;seed.set(read(current/'build-result.json')['seed']);break
  except (OSError,ValueError,KeyError):pass
 def set_settings(settings):
  settings=normalise(settings)
  for name,value in weights.items():value.set(settings['enemy_percentages'][name])
  for name,value in bosses.items():value.set(name in settings['enabled_bosses'])
  for ident,value in weapons.items():value.set(ident in settings['enabled_subweapons'])
  viola.set(settings.get('include_viola_ai',False));levels.set(settings.get('randomise_enemy_levels',False))
  native_bosses.set(settings.get('boss_mode','shuffle_test')=='native')
  neith.set(settings['include_neith_experimental']);music.set(settings['randomise_music']);ada.set(settings['randomise_ada'])
  chance.set(settings['metatron_subweapon_chance_percent']);inhert.set(settings['include_inhert_experimental'])
  spider.set(settings['include_spider_experimental']);mosquito.set(settings['include_mosquito_experimental'])
  repeats.set(settings['repeat_rule']=='compatible_exhaustion')
  sequence.set(settings['randomise_boss_sequence']);survival.set(settings['randomise_survival']);extra.set(settings['randomise_extra_missions'])
  enemy_health.set(settings['enemy_health_multiplier']);boss_health.set(settings['boss_health_multiplier'])
  valley.set(settings['valley_viper_test'])
  ensure_mosquito.set(settings['ensure_mosquito_replacements'])
 try:
  if (ROOT/'preferences.json').is_file():set_settings(load_profile(ROOT/'preferences.json'))
  elif current and (current/'randomisation-settings.json').is_file():
   legacy=read(current/'randomisation-settings.json');legacy['repeat_rule']='no_repeat';set_settings(legacy)
 except (OSError,ValueError,KeyError) as ex:status.set('Saved settings could not be loaded: '+str(ex))
 ttk.Label(app,text='ZOE2 Randomiser',font=('Segoe UI',19)).pack(pady=(15,6))
 ttk.Label(app,text='Boss shuffle available: registration/proximity fixes; Inhert and Viola AI experimental. Live testing required.').pack()
 if preview_mode:ttk.Label(app,text='CONTROLS PREVIEW — no playable Neith fight or game installation is included').pack()
 line=ttk.Frame(app);line.pack(fill='x',padx=20,pady=14)
 ttk.Label(line,text='Seed:').pack(side='left');ttk.Entry(line,textvariable=seed,width=64).pack(side='left',padx=10)
 ttk.Checkbutton(app,text='Optional: keep every boss original instead of boss shuffle',variable=native_bosses).pack()
 tabs=ttk.Notebook(app);tabs.pack(fill='x',padx=20,pady=6)
 enemy_tab=ttk.Frame(tabs);boss_tab=ttk.Frame(tabs);weapon_tab=ttk.Frame(tabs);audio_tab=ttk.Frame(tabs)
 tabs.add(enemy_tab,text='Enemy percentages');tabs.add(boss_tab,text='Bosses ON / OFF');tabs.add(weapon_tab,text='Subweapons ON / OFF')
 tabs.add(audio_tab,text='Music / ADA / Metatron')
 ttk.Checkbutton(audio_tab,text='Randomise music (compatible gameplay banks)',variable=music).grid(row=0,column=0,sticky='w',padx=12,pady=5)
 ttk.Checkbutton(audio_tab,text='Randomise compatible ADA gameplay voice lines',variable=ada).grid(row=1,column=0,sticky='w',padx=12,pady=5)
 ttk.Label(audio_tab,text='Metatron → random subweapon chance, 0–100%:').grid(row=2,column=0,sticky='w',padx=12,pady=5)
 ttk.Spinbox(audio_tab,from_=0,to=100,textvariable=chance,width=6).grid(row=2,column=1,padx=8)
 ttk.Label(audio_tab,text='OFF restores original audio payloads on Apply. Empty subweapon pool applies 0%; native healing stays available.').grid(row=3,column=0,columnspan=2,padx=12,pady=5)
 ttk.Label(enemy_tab,text='Share of authored regular-enemy replacements • total 100% • eligible stage pools are renormalised.').grid(row=0,column=0,columnspan=8,pady=5)
 total=tk.StringVar()
 def update_total(*_):
  try:total.set('Total: '+str(sum(v.get() for v in weights.values()))+'% (must be 100%)')
  except tk.TclError:total.set('Enter whole percentages from 0 to 100.')
 def adjust(name,amount):weights[name].set(max(0,min(100,weights[name].get()+amount)))
 for index,name in enumerate(ENEMIES):
  row=index//2+1;col=(index%2)*4
  ttk.Label(enemy_tab,text=name).grid(row=row,column=col,padx=(10,4),pady=3,sticky='w')
  minus=ttk.Button(enemy_tab,text='−5%',width=5,command=lambda n=name:adjust(n,-5));minus.grid(row=row,column=col+1)
  spin=ttk.Spinbox(enemy_tab,from_=0,to=100,textvariable=weights[name],width=5);spin.grid(row=row,column=col+2,padx=3)
  plus=ttk.Button(enemy_tab,text='+5%',width=5,command=lambda n=name:adjust(n,5));plus.grid(row=row,column=col+3)
  if name in LOCKED_ENEMIES:
   for widget in (minus,spin,plus):widget.configure(state='disabled')
  weights[name].trace_add('write',update_total)
 ttk.Label(enemy_tab,textvariable=total).grid(row=5,column=0,columnspan=4,pady=5);update_total()
 ttk.Button(enemy_tab,text='Reset equal shares',command=lambda:[weights[n].set(v) for n,v in DEFAULT_WEIGHTS.items()]).grid(row=5,column=4,columnspan=4)
 ttk.Checkbutton(enemy_tab,text='Remember Spider request (0%; objectives protected)',variable=spider).grid(row=6,column=0,columnspan=4,pady=5,sticky='w',padx=10)
 ttk.Checkbutton(enemy_tab,text='Finite Mosquito swarms (experimental; eligible groups)',variable=mosquito).grid(row=6,column=4,columnspan=4,pady=5,sticky='w',padx=10)
 ttk.Checkbutton(enemy_tab,text='Randomise enemy levels (observed range 0–7; OFF preserves original levels)',variable=levels).grid(row=7,column=0,columnspan=8,pady=5,sticky='w',padx=10)
 ttk.Checkbutton(enemy_tab,text='Ensure at least one eligible Mosquito replacement when enabled above 0%',variable=ensure_mosquito).grid(row=8,column=0,columnspan=8,pady=5,sticky='w',padx=10)
 ttk.Label(enemy_tab,text='Finite swarms: 6 × authored count; at most 36 particles per group, 72 added per stage. Native swarm capacity and scripted objectives are retained.').grid(row=9,column=0,columnspan=8,pady=4,padx=10,sticky='w')
 ttk.Checkbutton(enemy_tab,text='Randomise Survival stages 1–6 (experimental; gameplay test required)',variable=survival).grid(row=10,column=0,columnspan=8,pady=5,sticky='w',padx=10)
 ttk.Checkbutton(enemy_tab,text='Extra Missions: 6 enemy sections + boss battle with boss shuffle (experimental; selector repair needs playtest)',variable=extra).grid(row=11,column=0,columnspan=8,pady=5,sticky='w',padx=10)
 ttk.Label(enemy_tab,text='Enemy health:').grid(row=12,column=0,padx=10,pady=5,sticky='w')
 for column,value,label in ((1,1,'Normal'),(2,2,'Double'),(3,3,'Triple')):
  ttk.Radiobutton(enemy_tab,text=label,variable=enemy_health,value=value).grid(row=12,column=column,pady=5,sticky='w')
 ttk.Label(enemy_tab,text='Health choices take effect after Attach at the game main menu.').grid(row=13,column=0,columnspan=8,padx=10,pady=3,sticky='w')
 for index,(name,value) in enumerate(bosses.items()):ttk.Checkbutton(boss_tab,text='Inhert (requires experimental opt-in)' if name=='Inhert' else name,variable=value).grid(row=index//3,column=index%3,sticky='w',padx=12,pady=4)
 ttk.Checkbutton(boss_tab,text='Include Viola AI (experimental: deletion sequence needs retest)',variable=viola).grid(row=3,column=0,columnspan=3,sticky='w',padx=12,pady=4)
 ttk.Checkbutton(boss_tab,text='Include Inhert as opponent (experimental: arena testing needed)',variable=inhert).grid(row=7,column=0,columnspan=3,sticky='w',padx=12,pady=4)
 ttk.Checkbutton(boss_tab,text='Allow repeated identities after compatible pool exhaustion (explicit override)',variable=repeats).grid(row=8,column=0,columnspan=3,sticky='w',padx=12,pady=4)
 ttk.Label(boss_tab,text='Vic Viper movement, reachability and clone-death fixes apply automatically.').grid(row=9,column=0,columnspan=3,sticky='w',padx=12,pady=4)
 ttk.Checkbutton(boss_tab,text='Randomise Boss Sequence (experimental; Inhert and compatible-exhaustion repeats required)',variable=sequence).grid(row=10,column=0,columnspan=3,sticky='w',padx=12,pady=4)
 ttk.Label(boss_tab,text='Boss health:').grid(row=11,column=0,padx=12,pady=4,sticky='w')
 for column,value,label in ((0,1,'Normal'),(1,2,'Double'),(2,3,'Triple')):
  ttk.Radiobutton(boss_tab,text=label,variable=boss_health,value=value).grid(row=12,column=column,padx=12,pady=4,sticky='w')
 ttk.Checkbutton(boss_tab,text=NEITH_LABEL,variable=neith).grid(row=4,column=0,columnspan=3,sticky='w',padx=12,pady=4)
 neith_info=tk.StringVar(value=neith_status())
 neith.trace_add('write',lambda *_:neith_info.set(neith_status(neith.get())))
 ttk.Label(boss_tab,textvariable=neith_info,wraplength=1000).grid(row=5,column=0,columnspan=3,padx=12,pady=4,sticky='w')
 ttk.Label(boss_tab,text='OFF excludes that combat boss, including its original fight. Only Zakat is protected.',wraplength=1000).grid(row=6,column=0,columnspan=3,pady=5)
 def update_boss_controls(*_):
  for widget in boss_tab.winfo_children():
   if isinstance(widget,ttk.Checkbutton):widget.configure(state='disabled' if native_bosses.get() else 'normal')
 native_bosses.trace_add('write',update_boss_controls);update_boss_controls()
 for index,(ident,name) in enumerate(WEAPONS.items()):ttk.Checkbutton(weapon_tab,text=name,variable=weapons[ident]).grid(row=index//4,column=index%4,sticky='w',padx=12,pady=4)
 cannon=ttk.Checkbutton(weapon_tab,text='Vector Cannon — protected vanilla',state='disabled');cannon.grid(row=3,column=0,columnspan=4,sticky='w',padx=12,pady=4)
 ttk.Label(weapon_tab,text='ON: included in story reward shuffle and Metatron rewards. OFF: original story reward; excluded from random Metatron rewards.').grid(row=4,column=0,columnspan=4,pady=5)
 ttk.Label(app,text='Zakat, Vector Cannon, infected Ardjet removal and objective actors stay protected.').pack()
 ttk.Label(app,text='No repeated main identities by default. Insufficient compatible identities block Apply; no silent fallback.').pack()
 ttk.Label(app,text='All fourteen arenas can shuffle. No Vic Viper arena exclusions; Zakat remains original. Imported bosses still need live testing.').pack()
 ttk.Label(app,text='Candidates retain enemy, boss, music and subweapon / Metatron mappings for diagnostics.').pack()
 buttons=ttk.Frame(app);buttons.pack(pady=12)
 footer=ttk.Frame(app);footer.pack(side='bottom',fill='x')
 ttk.Label(footer,textvariable=status,wraplength=960).pack(side='bottom',padx=20,pady=8)
 output=tk.Text(app,height=19,wrap='word');output.pack(fill='both',expand=True,padx=20,pady=6)
 controls=[]
 def launch(args,path,completion):
  nonlocal process,logfiles,handles
  if process and process.poll() is None:return
  path.parent.mkdir(parents=True,exist_ok=True)
  stamp=time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)
  logfiles=[path.with_name(path.stem+'-'+stamp+'-stdout.log'),path.with_name(path.stem+'-'+stamp+'-stderr.log')]
  handles=[p.open('w',encoding='utf-8') for p in logfiles]
  save(path.with_name(path.stem+'-'+stamp+'-invocation.json'),dict(args=args,cwd=str(path.parent),logs=[str(p) for p in logfiles],started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
  try:process=subprocess.Popen(args,cwd=path.parent,stdout=handles[0],stderr=handles[1],creationflags=0x08000000)
  except OSError as ex:
   for handle in handles:handle.close()
   status.set('Could not start process: '+str(ex));return
  for button in controls:button.configure(state='disabled')
  def poll():
   text='\n'.join(str(p)+'\n'+p.read_text(encoding='utf-8',errors='replace') for p in logfiles)
   output.delete('1.0','end');output.insert('1.0',text);output.see('end')
   if process.poll() is None:app.after(700,poll);return
   code=process.returncode
   for handle in handles:handle.close()
   for button in controls:button.configure(state='normal')
   try:completion(code)
   except Exception as ex:status.set('Completion evidence could not be verified: '+str(ex))
  poll()
 def build(reroll=False,apply_after=False):
  nonlocal current
  if preview_mode:messagebox.showinfo('Controls preview','This archive tests the controls only. A gameplay build is not included.');return
  if reroll:seed.set('zoe2-'+secrets.token_hex(8))
  value=seed.get()
  if not value.strip():messagebox.showerror('Seed required','Enter a seed.');return
  try:
   settings=current_settings()
   blocked=effective(settings)['blocked']
   if blocked:raise ValueError('\n'.join(blocked))
  except (ValueError,tk.TclError) as ex:messagebox.showerror('Check randomisation settings',str(ex));return
  BUILD_ROOT.mkdir(parents=True,exist_ok=True)
  folder=BUILD_ROOT/('seed-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
  settings_path=BUILD_ROOT/(folder.name+'-settings.json');save(settings_path,settings)
  save_profile(ROOT/'preferences.json',settings)
  current=None;status.set('Building seed '+value+'. Full checks run before completion.')
  args=[str(console_python()),'-u',str(Path(__file__).with_name('seed_builder.py')),'--seed',value,'--output',str(folder),'--settings',str(settings_path)]
  if viola.get():args.append('--include-viola-ai')
  def done(code):
   nonlocal current
   if code:status.set('Build failed; no installation attempted. See captured stdout and stderr.');return
   current=folder/'Ship-v5';result=read(current/'build-result.json')
   save(ROOT/'last-built.json',dict(package=str(current),seed=result['seed']))
   if not result.get('installable'):
    status.set('Diagnostic candidate built; installation BLOCKED. '+'; '.join(result.get('blocked_reasons',[])));return
   status.set('Built '+result['seed']+' • STAGE '+result['archive_sha256'][:16])
   if apply_after:install()
  launch(args,BUILD_ROOT/(folder.name+'.log'),done)
 def install(restore=False):
  nonlocal current
  if preview_mode:messagebox.showinfo('Controls preview','Game installation and restore are unavailable in this controls preview.');return
  state_path=ROOT/'last-applied.json';prior=read(state_path) if state_path.exists() else {}
  target=Path(prior['package']) if restore and prior.get('package') else current
  if target is None:messagebox.showinfo('Build required','Build a seed first.');return
  if not restore:
   try:require_neith_available(effective(current_settings())['applied']['include_neith_experimental'])
   except ValueError as ex:messagebox.showerror('Neith port not ready',str(ex));return
   result=read(target/'build-result.json')
   if result.get('build_id')!=BUILD_ID:
    messagebox.showerror('Rebuild required','This package was generated by an older revision. Build the seed again to include the current fixes.');return
   if result['seed']!=seed.get():messagebox.showerror('Build selected seed','The seed changed. Build it first.');return
   if not result.get('installable',False):
    reason='\n'.join(result.get('blocked_reasons') or ['This build has not passed its installation checks.'])
    guidance='\n\nChoose your intended settings and use Build selected seed again. This existing package will stay unchanged.'
    if any('No-repeat story policy' in item for item in result.get('blocked_reasons',[])):
     guidance='\n\nFor boss shuffling across all fourteen campaign arenas, enable “Allow repeated identities after compatible pool exhaustion”, then use Build selected seed again. Anubis forms count as one identity.'
    status.set('Apply blocked before validation. '+reason)
    output.delete('1.0','end');output.insert('1.0',reason+guidance)
    messagebox.showerror('Build cannot be applied',reason+guidance);return
   if (target/'randomisation-settings.json').is_file():
    try:
     desired=current_settings()
     require_neith_available(effective(desired)['applied']['include_neith_experimental'])
    except (ValueError,tk.TclError) as ex:messagebox.showerror('Check randomisation settings',str(ex));return
    if normalise(read(target/'randomisation-settings.json'))!=desired:messagebox.showerror('Rebuild required','The randomisation settings changed. Build this seed again before applying.');return
   if result.get('build_id')!=BUILD_ID or not (target/'build-provenance.json').is_file():
    messagebox.showerror('Rebuild required','This legacy build has no current generation provenance. Build again; editing metadata cannot upgrade it.');return
   # Do not rewrite any generated script on Apply.
   # Known blocked builds stop above. Eligible builds still receive a fresh
   # installer preflight before backup or game-file writes.
  current=target
  status.set('Restoring and verifying previous files…' if restore else 'Fresh full-build preflight, then backup and installation…')
  args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(target/'Install-preview.ps1'),'-GamePath',str(_portable.game())]
  if restore:args.append('-Restore')
  def done(code):
   nonlocal current
   if code:
    result=read(target/'build-result.json') if not restore else {}
    reasons=result.get('blocked_reasons',[]) if not result.get('installable',True) else []
    status.set('Apply did not install this seed. '+('; '.join(reasons) if reasons else 'Installer stopped (exit '+str(code)+'). See stdout/stderr and the journal.'))
    return
   commit(ROOT,target,prior,restore)
   if restore:
    restored=read(state_path) if state_path.is_file() else {}
    current=Path(restored['package']) if restored.get('package') else None
    if current:
     restored_build=read(current/'build-result.json');seed.set(restored_build['seed'])
     save(ROOT/'last-built.json',dict(package=str(current),seed=restored_build['seed']))
   status.set('Previous files restored; game and backup hashes verified.' if restore else 'Installed and verified. Launch Steam, stop at main menu, then click Attach at main menu.')
  launch(args,target/('restore.log' if restore else 'apply.log'),done)
 def attach():
  if preview_mode:messagebox.showinfo('Controls preview','No game build or runtime helpers are included in this controls preview.');return
  report=inspect_attachment(ROOT,current)
  ATTACH_LOG_ROOT.mkdir(parents=True,exist_ok=True)
  save(ATTACH_LOG_ROOT/('preflight-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.json'),report)
  if not report['ready']:
   status.set('Nothing attached. '+report['message'])
   output.delete('1.0','end');output.insert('1.0',json.dumps(report,indent=2))
   messagebox.showerror('Seed is not installed',report['message']);return
  target=Path(report['package'])
  # The helper verifies its own supported executable and main-menu requirements.
  args=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(target/'runtime/Attach-Full-Preview.ps1'),'-AtMainMenu','-GamePath',report['game_root']]
  launch(args,ATTACH_LOG_ROOT/'attach-ui.log',lambda code:status.set('Attachment finished for '+report['recorded_seed']+'; inspect every helper result above.' if code==0 else 'Attachment failed. Keep the log and remain at the main menu.'))
 def openfolder():os.startfile(str(ROOT if preview_mode else current or BUILD_ROOT))
 def current_settings():
  native=native_bosses.get()
  selected=boss_selection([n for n,v in bosses.items() if v.get()],viola.get())
  eligible={'Ardjet','Nephtis','Anubis','Vic Viper'}|({'Inhert'} if inhert.get() else set())
  if not native and not any(BOSSES[n] in eligible for n in selected):raise ValueError('Enable an eligible replacement boss. Inhert requires its experimental checkbox.')
  return normalise(dict(boss_mode='native' if native else 'shuffle_test',repeat_rule='compatible_exhaustion' if repeats.get() else 'no_repeat',enemy_percentages=enemy_weights({n:v.get() for n,v in weights.items()}),enabled_bosses=selected,enabled_subweapons=weapon_selection([i for i,v in weapons.items() if v.get()]),include_viola_ai=viola.get(),randomise_enemy_levels=levels.get(),include_neith_experimental=neith_selection(neith.get()),randomise_music=music.get(),randomise_ada=ada.get(),metatron_subweapon_chance_percent=chance.get(),include_inhert_experimental=inhert.get(),include_spider_experimental=spider.get(),include_mosquito_experimental=mosquito.get(),valley_viper_test=valley.get(),ensure_mosquito_replacements=ensure_mosquito.get(),randomise_boss_sequence=sequence.get(),randomise_survival=survival.get(),randomise_extra_missions=extra.get(),enemy_health_multiplier=enemy_health.get(),boss_health_multiplier=boss_health.get()))
 def export_settings():
  try:
   settings=current_settings()
  except (ValueError,tk.TclError) as ex:messagebox.showerror('Check randomisation settings',str(ex));return
  chosen=filedialog.asksaveasfilename(parent=app,title='Save seed settings for tester report',initialdir=str(ROOT),defaultextension='.json',filetypes=[('Seed settings','*.json')])
  if chosen:
   save(chosen,dict(format=1,build_id=BUILD_ID,seed=seed.get(),settings=settings,neith=neith_readiness(),controls_preview=preview_mode,gameplay_verified=False))
   status.set('Seed settings saved: '+chosen)
 def restore_vanilla():
  from vanilla_restore_ui import start
  start(app,launch,ROOT,status,preview_mode)
 actions=[('Build selected seed',build),('REROLL + Build',lambda:build(True)),('REROLL + Build + Apply',lambda:build(True,True)),('Apply build',install),('Restore previous',lambda:install(True)),('Restore game to vanilla',restore_vanilla),('Open build folder',openfolder)]
 for label,action in actions:
  button=ttk.Button(buttons,text=label,command=action);button.pack(side='left',padx=3);controls.append(button)
  if preview_mode and label!='Open build folder':button.configure(state='disabled')
 utilities=ttk.Frame(footer);utilities.pack(pady=5)
 button=ttk.Button(utilities,text='Attach at main menu',command=attach);button.pack(side='left',padx=5);controls.append(button)
 if preview_mode:button.configure(state='disabled')
 ttk.Button(utilities,text='Export seed settings',command=export_settings).pack(side='left',padx=5)
 def bug_report():
  chosen=filedialog.asksaveasfilename(parent=app,title='Export bug report (no game files or saves)',defaultextension='.zip',filetypes=[('Bug report ZIP','*.zip')])
  if chosen:
   try:
    from beta_support import export_report
    export_report(chosen,current);status.set('Bug report saved: '+chosen)
   except Exception as ex:messagebox.showerror('Report could not be saved',str(ex))
 ttk.Button(utilities,text='Export bug report',command=bug_report).pack(side='left',padx=5)
 def change_game():
  if process and process.poll() is None:return
  chosen=filedialog.askdirectory(parent=app,title='Choose ZOE2 MARS game folder')
  if chosen:
   try:
    from beta_support import choose_game
    choose_game(chosen);messagebox.showinfo('Game folder selected','Reopen the app to use this game folder.');app.destroy()
   except Exception as ex:messagebox.showerror('Game folder could not be changed',str(ex))
 ttk.Button(utilities,text='Game folder',command=change_game).pack(side='left',padx=5)
 def import_settings():
  chosen=filedialog.askopenfilename(parent=app,title='Load settings profile',initialdir=str(ROOT),filetypes=[('Seed settings','*.json')])
  if not chosen:return
  try:set_settings(load_profile(chosen));save_profile(ROOT/'preferences.json',current_settings())
  except (OSError,ValueError,KeyError) as ex:messagebox.showerror('Profile not loaded',str(ex));return
  status.set('Profile loaded. Build a seed to apply these selections.')
 def settings_preview():
  try:report=effective(current_settings())
  except (ValueError,tk.TclError) as ex:messagebox.showerror('Check settings',str(ex));return
  if current and (current/'effective-settings.json').is_file():report['selected_build']=dict(package=str(current),effective=read(current/'effective-settings.json'))
  if current and (current/'manifest.json').is_file():
   swarm=read(current/'manifest.json').get('mosquito_replacements',{})
   report['selected_build_mosquitoes']=dict(selected_slots=len(swarm.get('selected',[])),minimum_applied=swarm.get('minimum_applied',False),eligible_slots=sum(len(r['eligible']) for r in swarm.get('stages',[])),gameplay_verified=False)
  report['coverage']='Fourteen campaign boss arenas; only Zakat is protected. Cinematic actors are separate from combat assignments.'
  output.delete('1.0','end');output.insert('1.0',json.dumps(report,indent=2))
 ttk.Button(utilities,text='Load profile',command=import_settings).pack(side='left',padx=5)
 ttk.Button(utilities,text='Applied / ignored preview',command=settings_preview).pack(side='left',padx=5)
 def persist(*_):
  try:save_profile(ROOT/'preferences.json',current_settings())
  except (OSError,ValueError,tk.TclError):pass
 for variable in [*weights.values(),*bosses.values(),*weapons.values(),viola,neith,levels,native_bosses,music,ada,chance,inhert,spider,mosquito,repeats,valley,ensure_mosquito,sequence,survival,extra,enemy_health,boss_health]:variable.trace_add('write',persist)
 def close():
  if process and process.poll() is None:status.set('An operation is still running. Wait for its result before closing the utility.');return
  persist()
  app.destroy()
 app.protocol('WM_DELETE_WINDOW',close)
 def initial_installation_status():
  if preview_mode or not (ROOT/'last-applied.json').exists():return
  report=inspect_attachment(ROOT,current)
  if not report['ready']:
   status.set('Nothing attached. Installation needs attention; see the details above.')
   output.insert('1.0',report['message']+'\n')
 app.after(100,initial_installation_status)
 app.mainloop()
if __name__=='__main__':main()

