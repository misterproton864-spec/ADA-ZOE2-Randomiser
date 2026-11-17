import json,os,sys,traceback
from pathlib import Path
APP=Path(__file__).resolve().parent
for p in [APP,APP/'work/seed-v6/source',APP/'legacy',APP/'legacy/research',APP/'work/progression-v4/source']:sys.path.insert(0,str(p))
os.environ['PYTHONPATH']=os.pathsep.join(map(str,[APP,APP/'work/seed-v6/source',APP/'legacy',APP/'legacy/research',APP/'work/progression-v4/source']))
import portable_paths as pp
def main():
    import tkinter as tk
    from tkinter import filedialog,messagebox,ttk
    import beta_support as beta
    if '--self-test' in sys.argv:
        root=tk.Tk();root.withdraw();root.update();root.destroy()
        import seed_ui,native_seed_builder,apply_validation,boss_test_profile,settings_contract
        from build_info import VERSION
        print(json.dumps(dict(passed=True,tk=True,version=VERSION,portable=True,game_writes=False)))
        return
    if '--export-report' in sys.argv:
        print(beta.export_report(sys.argv[sys.argv.index('--export-report')+1]));return
    # Only one interactive app may update the shared settings/installation state.
    import msvcrt
    lock=(pp.HOME/'app.lock').open('a+b')
    if lock.tell()==0:lock.write(b'0');lock.flush()
    lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:
        lock.close();messagebox.showinfo('ZOE2 Randomiser is already open','Use the existing randomiser window.');return
    if '--select-game' in sys.argv or not pp.CONFIG.exists():
        root=tk.Tk();root.title('ZOE2 Randomiser — Choose game folder');root.geometry('580x230')
        ttk.Label(root,text='ADA — ZOE2 Randomiser local.22',font=('Segoe UI',16)).pack(pady=18)
        ttk.Label(root,text='Choose your own Steam ZOE2 MARS installation.\nSelect the folder containing Zoe2Mars.exe.',justify='center').pack(pady=8)
        accepted=[]
        def select():
            chosen=filedialog.askdirectory(parent=root,title='Select your ZOE2 MARS folder containing Zoe2Mars.exe')
            if not chosen:return
            try:beta.choose_game(chosen)
            except Exception as ex:messagebox.showerror('Game folder could not be selected',str(ex),parent=root);return
            accepted.append(True);root.destroy()
        ttk.Button(root,text='Choose game folder',command=select).pack(pady=12)
        root.mainloop()
        if not accepted:return
    import seed_ui
    seed_ui.main()
    lock.close()
if __name__=='__main__':
    try:main()
    except Exception:
        error=traceback.format_exc();(pp.HOME/'startup-error.log').write_text(error,encoding='utf-8')
        try:
            import tkinter.messagebox as mb
            mb.showerror('ZOE2 Randomiser could not start',error+'\nLog: '+str(pp.HOME/'startup-error.log'))
        except Exception:pass
        raise
