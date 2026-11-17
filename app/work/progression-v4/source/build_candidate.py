import portable_paths as _portable
"""Private progression-isolation candidate, from hash-pinned v3 and vanilla.

Whole-section fallbacks deliberately trade coverage for a testable regression
boundary. They are not a root-cause fix or evidence of playable progression.
"""
import copy, ctypes, hashlib, json, shutil, struct, subprocess, sys
from pathlib import Path
from boss_slot_policy import allocate, validate, canonical

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
BASE = WORK / 'full-preview-v3/Full-Preview-v3'
OUT = ROOT / 'Progression-v4'
LEGACY = Path(str(_portable.LEGACY))
VANILLA = WORK / '2026-10-18-preview/backups/vanilla.STAGE.DAT'
sys.path.insert(0, str(LEGACY / 'research'))
from zoe2_archive import Archive, xor_words

SEED = 'progression-isolation-2026-10-19-v4'
BASE_SHA = '0b67e9528083912c6f49f3de11966026665f2fb724ea8fa6dde41f58298e4145'
VANILLA_SHA = 'c5627420319bbaa28f887b0728e14277befd9cf33ced3f82d0e304b389d5e651'
FALLBACKS = {
 'ba01': 'BAHRAM phantom/dormant source isolation',
 'fc01': 'Rescue candidate; exact save/stage attribution still required',
 'vc02': 'Post-Inhert Vascilia Sky entry / rescue candidate isolation',
 'vc03': 'Vascilia Sky continuation candidate isolation',
 'mf01': 'Post-LEV final-kill/clear candidate; exact stage unconfirmed',
 'mf01c': 'Post-LEV continuation candidate; exact stage unconfirmed',
 'mf02': 'Post-LEV final-kill/clear candidate; exact stage unconfirmed',
 'am01f': 'Later combat candidate; exact final-kill stage unconfirmed',
 'vc01': 'Valley Viper zero-HP stall: restore native encounter pending death-state fix',
 'cy02': 'Remove repeated Vic Viper replacement',
 'ef01': 'Remove repeated Vic Viper replacement',
 'ba03': 'Remove repeated Ardjet replacement',
 'cs01': 'Remove repeated Ardjet; native compressed-space handoff for skip regression',
 'fa01': 'Remove repeated Ardjet replacement',
 'fr04g': 'Remove repeated Ardjet replacement',
}
CSC = _portable.compiler()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')

def section_bytes(a, stage):
    start = a.stages[stage]
    end = min((p for p in a.stages.values() if p > start), default=a.size)
    with a.path.open('rb') as f:
        f.seek(start)
        data = f.read(end-start)
    assert len(data) == end-start
    return data

def rebuild():
    assert sha(BASE/'STAGE.DAT') == BASE_SHA
    assert sha(VANILLA) == VANILLA_SHA
    assert not OUT.exists(), 'Refuse to overwrite any candidate'
    OUT.mkdir(parents=True)
    (ROOT/'reports').mkdir(exist_ok=True)
    # The 4 GB atlas stays in the preserved parent package. Explicit dependency
    # checks below cover every atlas/audio file without duplicating those assets.
    shutil.copytree(BASE/'runtime', OUT/'runtime')
    for name in ('CaptureEncounter.exe', 'Install-preview.ps1', 'Install preview.cmd',
                 'Restore previous build.cmd', 'Attach at main menu.cmd', 'Capture stuck encounter.cmd'):
        shutil.copy2(BASE/name, OUT/name)
    old = Archive(VANILLA); base = Archive(BASE/'STAGE.DAT')
    assert old.seed == base.seed and set(old.stages) == set(base.stages)
    stages = sorted(base.stages, key=base.stages.get); offsets = {}
    with base.path.open('rb') as src, (OUT/'STAGE.DAT').open('xb') as dst:
        dst.write(src.read(base.stages[stages[0]]))
        for stage in stages:
            offsets[stage] = dst.tell()
            donor = old if stage in FALLBACKS else base
            dst.write(section_bytes(donor, stage))
        src.seek(4)
        directory = bytearray(xor_words(src.read(12+20*len(stages)), base.seed, base.seed^0xf0f0))
        for i in range(len(stages)):
            p = 12+20*i
            stage = directory[p:p+16].split(b'\0')[0].decode()
            assert offsets[stage] % 2048 == 0
            struct.pack_into('<I', directory, p+16, offsets[stage]//2048)
        dst.seek(4); dst.write(xor_words(directory, base.seed, base.seed^0xf0f0))
    new = Archive(OUT/'STAGE.DAT'); checks = []; group_count = 0
    for stage in stages:
        donor = old if stage in FALLBACKS else base
        assert section_bytes(new, stage) == section_bytes(donor, stage), stage
        end = min((v for v in new.stages.values() if v > new.stages[stage]), default=new.size)
        for g in new.groups(stage):
            n = g['compressed_size'] if g['compressed_size'] is not None else g['decoded_size']
            assert new.stages[stage] <= g['location'] and g['location']+(n+3)//4*4 <= end
            new.decode(g); group_count += 1
        checks.append(dict(stage=stage, donor='vanilla' if stage in FALLBACKS else 'v3',
            section_sha256=hashlib.sha256(section_bytes(new, stage)).hexdigest(),
            reason=FALLBACKS.get(stage, 'Preserved byte-for-byte')))
    save(ROOT/'reports/archive-verification.json', dict(passed=True, sections=len(stages),
        groups_decoded=group_count, exact_section_checks=checks, gameplay_verified=False))
    m = json.loads((BASE/'manifest.json').read_text())
    m.update(release_name='Progression v4 — isolation test, NOT certified',
        candidate_seed=SEED, parent_sha256=BASE_SHA, patched_sha256=sha(OUT/'STAGE.DAT'),
        vanilla_sha256=VANILLA_SHA, installed=False, gameplay_verified=False,
        full_campaign_gameplay_verified=False, full_requirements_complete=False,
        boss_mapping_is_permutation=False, boss_mapping_policy='Per-slot strict validation; full scope blocked by pool shortage',
        fallback_sections=FALLBACKS, boss_seed=m['boss_seed'],
        mosquito_policy=dict(included=True, reason='Explicitly retained experimental parent setting; official default remains excluded'),
        historical_parent_manifest='../../full-preview-v3/Full-Preview-v3/manifest.json')
    for key in ('boss_identity_policy', 'linked_identity_mapping', 'linked_story_groups'):
        m.pop(key, None)
    m['boss_changes'] = [r for r in m['boss_changes'] if r['stage'] not in FALLBACKS]
    m['enemy_changes'] = [r for r in m['enemy_changes'] if r['stage'] not in FALLBACKS]
    m['modified_boss_sections'] = [s for s in m['modified_boss_sections'] if s not in FALLBACKS]
    rows = [dict(stage=r['stage'], identity=r['canonical_destination_identity'],
            destination_boss=r['destination_boss'], sites=r['sites'])
            for r in m['boss_changes'] if not r['stage'].startswith('vs_') and r['stage']!='am01g']
    validate(rows)
    source_encounters = json.loads((LEGACY/'campaign-boss-encounters.json').read_text())['encounters']
    eligible = {r['encounter']: ['Ardjet','Nephtis','Anubis','Vic Viper','Inhert']
        for r in source_encounters if r['randomise'] and r['encounter']!='am01g'}
    try:
        allocate(eligible, SEED)
    except ValueError as e:
        shortage = str(e)
    else:
        raise AssertionError('Expected source-catalog capacity shortage')
    allocation = dict(seed=SEED, full_scope_slots=sorted(eligible), full_scope_error=shortage,
        full_scope_uniqueness_satisfied=False, retained_subset_unique=True,
        retained_subset=rows, fallbacks=[dict(stage=s, mode='native', reason=why) for s,why in FALLBACKS.items()],
        native_fallback_identities_may_repeat=True, clones_exempt=['am01g'],
        optional_modes_scoped_separately=True, gameplay_verified=False)
    save(OUT/'encounter-boss-mapping.json', allocation)
    save(OUT/'manifest.json', m)
    return old, new, m

def bank_helpers(old, new, m):
    runtime = OUT/'runtime'; rows = []
    side=m.get('side_modes',{}).get('boss_sequence') or {}
    extra_battle=(m.get('side_modes',{}).get('extra_missions') or {}).get('boss_battle')
    expected_sound={row['stage']:row['sound_pack_import']['added']
                    for row in m.get('boss_changes',[])+side.get('encounters',[])+([extra_battle] if extra_battle else [])
                    if 'sound_pack_import' in row}
    for stage in old.stages:
        a = [g for g in old.groups(stage) if g['folder']=='sound']
        b = [g for g in new.groups(stage) if g['folder']=='sound']
        assert len(a) == len(b)
        for group_index,(og, ng) in enumerate(zip(a,b)):
            extra=expected_sound.get(stage,0) if group_index==0 else 0
            original_names=[f['name'] for f in og['files']]
            generated_names=[f['name'] for f in ng['files']]
            assert generated_names[:len(original_names)]==original_names
            assert len(generated_names)==len(original_names)+extra
            if extra:
                assert generated_names[len(original_names):]==[f'pk{i:06x}.sdx' for i in range(len(original_names),len(original_names)+extra)]
            for of,nf in zip(og['files'],ng['files']):
                rows.append(dict(stage=stage,original_sector=(og['location']+of['offset'])//2048,
                                 modified_sector=(ng['location']+nf['offset'])//2048))
    save(runtime/'music-bank-address-audit.json', dict(modified_stage_sha256=m['patched_sha256'], rows=rows))
    builder = 'import sys\nsys.path.insert(0,'+repr(str(LEGACY))+')\n'
    builder += (LEGACY/'build_load_fix_adapters.py').read_text()
    (runtime/'generate-bank-guards.py').write_text(builder)
    subprocess.run([sys.executable,str(runtime/'generate-bank-guards.py'),str(OUT/'STAGE.DAT')],cwd=runtime,check=True)
    for name in ('MusicSectorAdapter','NephtisDialogueAdapter'):
        subprocess.run([CSC,'/nologo','/platform:x64','/optimize+', '/out:'+str(runtime/(name+'.exe')),str(runtime/(name+'.cs'))],check=True)
        subprocess.run([str(runtime/(name+'.exe')),'--self-test',str(runtime/'Load-Fix-Verification')],check=True)
    subprocess.run([sys.executable,str(runtime/'verify_load_fix_native.py')],cwd=runtime,check=True)
    m['music_sector_source'] = dict(json.loads((runtime/'music-sector-source.json').read_text()), helper_sha256=sha(runtime/'MusicSectorAdapter.exe'))

def spider_gate(m):
    """Prepend exact-stage bypass; preserve the existing corrected tick verbatim."""
    original = WORK/'2026-10-18-preview/source/Full-Rerandomisation-v2/runtime/SpiderReplacementAdapter.cs'
    text = original.read_text(); runtime = OUT/'runtime'
    assert sha(WORK/'2026-10-18-preview/source/Full-Rerandomisation-v2/runtime/SpiderReplacementAdapter.exe') == next(h['sha256'] for h in m['runtime_helpers'] if h['file']=='SpiderReplacementAdapter.exe')
    a = text.index(' public static byte[] BuildCave('); b = text.index(' public static byte[] BuildRuntime(',a)
    method = ''' public static byte[] BuildCave(long image,long cave) {
 var g=new List<byte>(); var jumps=new List<int>();
 Add(g,0x9c,0x50,0x48,0xb8);g.AddRange(BitConverter.GetBytes(image+0x1535830));
 string[] stages={STAGES};
 foreach(string stage in stages) {
  var mismatches=new List<int>();byte[] name=System.Text.Encoding.ASCII.GetBytes(stage+"\\0");
  for(int i=0;i<name.Length;i++) {
   Add(g,0x80,0x78,(byte)i,name[i],0x0f,0x85);mismatches.Add(g.Count);g.AddRange(new byte[4]);
  }
  Add(g,0xe9);jumps.Add(g.Count);g.AddRange(new byte[4]);
  foreach(int p in mismatches){byte[] rel=BitConverter.GetBytes(g.Count-p-4);for(int j=0;j<4;j++)g[p+j]=rel[j];}
 }
 Add(g,0x58,0x9d);int prefix=g.Count;
 int bypass=prefix+Wrapper.Length;
 foreach(int p in jumps){byte[] rel=BitConverter.GetBytes(bypass-p-4);for(int j=0;j<4;j++)g[p+j]=rel[j];}
 byte[] w=(byte[])Wrapper.Clone();
 int configAt=CONFIGAT,tickAt=TICKAT;
 Buffer.BlockCopy(BitConverter.GetBytes(cave+0x4000),0,w,configAt,8);
 Buffer.BlockCopy(BitConverter.GetBytes(cave+0x1000),0,w,tickAt,8);
 Buffer.BlockCopy(Rel32(image+Factory-ImageBase+Stolen.Length,cave+prefix+w.Length),0,w,w.Length-4,4);
 g.AddRange(w);Add(g,0x58,0x9d);g.AddRange(Stolen);Add(g,0xe9);
 g.AddRange(Rel32(image+Factory-ImageBase+Stolen.Length,cave+g.Count+4));
 if(g.Count>=0x1000)throw new Exception("Stage gate overlaps compiled tick");
 byte[] code=new byte[0x1000+Tick.Length];g.CopyTo(code);Buffer.BlockCopy(Tick,0,code,0x1000,Tick.Length);return code;
 }
'''
    # Extract relocation offsets from the reviewed source, not magic offsets.
    import re
    body=text[a:b]
    offsets=re.findall(r'Buffer.BlockCopy\(BitConverter.GetBytes\(cave\+0x(?:4000|1000)\),0,b,(\d+),8\)',body)
    assert len(offsets)==2
    method=method.replace('STAGES',','.join(json.dumps(s) for s in sorted(FALLBACKS)))
    method=method.replace('CONFIGAT',offsets[0]).replace('TICKAT',offsets[1])
    text=text[:a]+method+text[b:]
    # Existing self-test computes the continuation at old wrapper end. Gate tests
    # below inspect and execute both paths instead.
    a=text.index(' static void SelfTest('); b=text.index(' static IntPtr AllocateNearby',a)
    text=text[:a]+''' static void SelfTest(string folder) {
 Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
 long cave=image+0x20000000;File.WriteAllBytes(Path.Combine(folder,"spider-"+image.ToString("x")+".bin"),BuildCave(image,cave));
 }Console.WriteLine("Generated stage-gated Spider code at three image bases; gameplay untested.");
 }
'''+text[b:]
    (runtime/'SpiderReplacementAdapter.cs').write_text(text)
    subprocess.run([CSC,'/nologo','/platform:x64','/optimize+', '/out:'+str(runtime/'SpiderReplacementAdapter.exe'),str(runtime/'SpiderReplacementAdapter.cs')],check=True)
    fixtures=ROOT/'reports/spider-gate-fixtures'
    subprocess.run([str(runtime/'SpiderReplacementAdapter.exe'),'--self-test',str(fixtures)],check=True)
    parent_fixtures=ROOT/'reports/spider-parent-fixtures'
    subprocess.run([str(original.with_suffix('.exe')),'--self-test',str(parent_fixtures)],check=True)
    for image in (0x140000000,0x180000000,0x7ff600000000):
        name=f'spider-{image:x}.bin'
        assert (fixtures/name).read_bytes()[0x1000:] == (parent_fixtures/name).read_bytes()[0x1000:]
    # Exercise real generated gate on controlled memory, with tick replaced by
    # a counting stub and original continuation replaced by an epilogue only.
    k=ctypes.WinDLL('kernel32');k.VirtualAlloc.restype=ctypes.c_void_p
    k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32]
    k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
    mem=k.VirtualAlloc(None,0x4000,0x3000,0x40);assert mem
    cases=0
    try:
        stage=ctypes.create_string_buffer(32); manager=ctypes.create_string_buffer(0x2000)
        count=ctypes.c_uint32(0)
        for image in (0x140000000,0x180000000,0x7ff600000000):
            raw=bytearray((fixtures/f'spider-{image:x}.bin').read_bytes())
            wrapper=raw.index(bytes.fromhex('9c50515241504151'),12)
            # Prefix absolute address, original tick and config absolute operands.
            struct.pack_into('<Q',raw,4,ctypes.addressof(stage))
            struct.pack_into('<Q',raw,wrapper+int(offsets[0]),mem+0x3000)
            struct.pack_into('<Q',raw,wrapper+int(offsets[1]),mem+0x1000)
            # Locate both jump-to-native continuations by their original target.
            targets=[]; cave=image+0x20000000; target=image+0xa5ea740+16
            for p in range(wrapper,len(raw[:0x1000])-4):
                if raw[p]==0xe9 and cave+p+5+struct.unpack_from('<i',raw,p+1)[0]==target:
                    targets.append(p)
            assert len(targets)==2
            for p in targets:struct.pack_into('<i',raw,p+1,0x2000-p-5)
            ctypes.memmove(mem,bytes(raw),len(raw))
            stub=b'\x48\xb8'+struct.pack('<Q',ctypes.addressof(count))+bytes.fromhex('ff00c3')
            ctypes.memmove(mem+0x1000,stub,len(stub))
            ctypes.memmove(mem+0x2000,bytes.fromhex('4883c4205bc3'),6)
            fn=ctypes.WINFUNCTYPE(None,ctypes.c_void_p)(mem)
            for name in (*FALLBACKS,'tr01','am01g','ds00','ba01evil','','BA01','vs_vc01'):
                ctypes.memset(stage,0,32);ctypes.memmove(stage,name.encode(),len(name))
                count.value=0;before=bytes(manager);fn(ctypes.addressof(manager))
                assert count.value==(0 if name in FALLBACKS else 1),name
                assert bytes(manager)==before
                cases+=1
    finally:k.VirtualFree(mem,0,0x8000)
    m['spider_bridge_helper']=dict(stage_bypass=sorted(FALLBACKS),native_gate_cases=cases,
        corrected_parent_tick_preserved=True,gameplay_verified=False)
    save(ROOT/'reports/spider-stage-gate.json',dict(passed=True,cases=cases,image_bases=3,
        exact_null_terminated_matching=True,synthetic_tick=True,gameplay_verified=False))
    print('PASS Spider stage bypass',cases,'native gate cases')

def finish(m):
    runtime=OUT/'runtime'
    for helper in m['runtime_helpers']:helper['sha256']=sha(runtime/helper['file'])
    save(OUT/'manifest.json',m)
    # Only the archive is installed by v4. The parent dependency preflight checks
    # both atlases and all audio files before a single write; attachment checks all.
    parent=json.loads((BASE/'installation-plan.json').read_text())
    atlas_files=[dict(relative_path='atlas/'+a['file'],package_path=a['file'],
        expected_before_sha256=next(r['patched_sha256'] for r in parent['files'] if r['relative_path']=='atlas/'+a['file']),
        patched_sha256=a['sha256']) for a in m['atlases'] if (OUT/a['file']).is_file()]
    writes={'ZOE2/STAGE.DAT'}|{a['relative_path'] for a in atlas_files}
    dependencies=[dict(relative_path=r['relative_path'],sha256=r['patched_sha256']) for r in parent['files'] if r['relative_path'] not in writes]
    plan=dict(format=1,baseline='Full Preview v3',dependencies=dependencies,files=[dict(
        relative_path='ZOE2/STAGE.DAT',package_path='STAGE.DAT',expected_before_sha256=BASE_SHA,patched_sha256=m['patched_sha256'])]+atlas_files)
    save(OUT/'installation-plan.json',plan)
    installer=(BASE/'Install-preview.ps1').read_text()
    anchor='$rows=@()'
    dependency_check='''foreach($dependency in $plan.dependencies){
 if((Get-Sha (Get-Target $dependency.relative_path)) -ne $dependency.sha256){throw ('Required v3 atlas/audio dependency differs: '+$dependency.relative_path+'. No files installed.')}
}
'''
    installer=installer.replace(anchor,dependency_check+anchor)
    installer=installer.replace('Full Preview v3 installed','Progression v4 isolation candidate installed')
    (OUT/'Install-preview.ps1').write_text(installer)
    attach=(BASE/'runtime/Attach-Full-Preview.ps1').read_text()
    anchor='foreach($helper in $manifest.runtime_helpers){'
    deps='''foreach($dependency in $plan.dependencies){
 if((Get-Sha (Join-Path $GamePath $dependency.relative_path)) -ne $dependency.sha256){throw ('Required v3 dependency differs: '+$dependency.relative_path)}
}
'''
    attach=attach.replace(anchor,deps+anchor,1)
    (runtime/'Attach-Full-Preview.ps1').write_text(attach)
    save(OUT/'checksums.json',dict(algorithm='SHA256',files=[dict(file=p.relative_to(OUT).as_posix(),sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='checksums.json']))
    print('BUILT',m['patched_sha256'],'NOT installed; NOT gameplay verified')

def atlas_fallbacks(m):
    # Native scripts/models must also resolve original stage texture bindings.
    # V3 can replace existing atlas names, not just add new donor aliases.
    game=Path(str(_portable.game()))
    def index(path):
        with path.open('rb') as f:
            header=f.read(12);assert header[:4]==b'PAC\0'
            big=header[4:9]==b'0.01a';assert big or header[4:9]==b'0.01b'
            endian='>' if big else '<';width=4 if big else 8
            n=struct.unpack(endian+'I',f.read(4))[0]
            names,table,data=struct.unpack(endian+('III' if big else 'QQQ'),f.read(3*width))
            entries={}
            for i in range(n):
                f.seek(names+32*i);name=f.read(32).split(b'\0')[0].decode()
                f.seek(table+width*2*i);pair=f.read(width*2)
                assert name not in entries;entries[name]=(i,pair)
            return table,width,data,entries
    proofs=[]
    for label,name in [('main','atlas_pc_Zlib.pac'),('small','atlas_pc_jp_Zlib_ps2.pac')]:
        original=game/'atlas'/(name+'.zoe2-ca01-loader-v1.bak')
        expected=next(r['source_sha256'] for r in json.loads((BASE/'atlas-validation.json').read_text(encoding='utf-8-sig'))['files'] if r['file']==name)
        assert sha(original)==expected
        _,ow,od,old=index(original);table,width,data,new=index(BASE/name);assert ow==width
        native={key:value for key,value in old.items() if any(key.startswith('@'+s+'_') for s in FALLBACKS)}
        changes={key:pair for key,(_,pair) in native.items() if new[key][1]!=pair}
        if changes:
            assert not (OUT/name).exists(), 'Refuse atlas overwrite'
            shutil.copy2(BASE/name,OUT/name)
            with (OUT/name).open('r+b') as f:
                for key,pair in changes.items():
                    f.seek(table+width*2*new[key][0]);f.write(pair)
            _,_,_,actual=index(OUT/name)
        else:actual=new
        for key,(_,pair) in native.items():
            assert actual[key][1]==pair
            m['atlas_aliases'][label].pop(key,None)
        path=OUT/name if changes else BASE/name
        next(a for a in m['atlases'] if a['file']==name)['sha256']=sha(path)
        proofs.append(dict(file=name,native_stage_bindings_verified=len(native),restored_bindings=len(changes),
            output_packaged=bool(changes),sha256=sha(path)))
        print('Native atlas bindings',name,len(native),'checked;',len(changes),'restored',flush=True)
    m['source_sha256']=BASE_SHA
    m['retained_v25_enemy_weapon_behaviour']=False
    m.pop('installed_at',None)
    save(ROOT/'reports/native-atlas-bindings.json',dict(passed=True,atlases=proofs,gameplay_verified=False))

def viper_guard(m):
    # Valley is a native fallback. BAHRAM's completed fighter-mode encounter
    # must keep that mode. Keep the parent's restriction only in Boss Battle.
    text=(WORK/'full-preview-v3/source/build_viper_guard.py').read_text()
    text=text.replace("ROOT/'Full-Preview-v3", "ROOT/'Progression-v4")
    text=text.replace("TIGHT=('ba02','vc01','vs_ba02','vs_vc01')", "TIGHT=('vs_ba02','vs_vc01')")
    text=text.replace("(*TIGHT,'wn01'", "(*TIGHT,'ba02','vc01','wn01'")
    script=ROOT/'source/build_viper_guard_v4.py';script.write_text(text)
    subprocess.run([sys.executable,str(script)],check=True)
    m['viper_arena_guard']=json.loads((ROOT/'reports/viper-guard-verification.json').read_text())

def capture_tool():
    text=(WORK/'full-preview-v3/source/CaptureEncounter.cs').read_text()
    # The new prefix saves flags/RAX, loads current-stage address and then
    # exact-matches names. Its config/tick locations remain unchanged.
    old='for(int i=0;i<8;i++)if(header[i]!=expected[i])throw new Exception("Unknown bridge redirect; private layout not read");'
    new='''bool known=true;for(int i=0;i<8;i++)if(header[i]!=expected[i])known=false;
  if(!known) {
   byte[] gate=Read(cave,12);
   if(gate[0]!=0x9c||gate[1]!=0x50||gate[2]!=0x48||gate[3]!=0xb8||BitConverter.ToInt64(gate,4)!=VA(0x141535830))
    throw new Exception("Unknown bridge redirect; private layout not read");
  }'''
    assert old in text;text=text.replace(old,new)
    text=text.replace('try {for(int i=0;i<10;i++) {', '''bool watch=args.Length>0&&args[0]=="--watch";
   Console.WriteLine("Read-only encounter recording: "+folder+(watch?" (up to six hours; close this window to stop)":" (ten samples)"));
   string lastStage="";int samples=watch?21600:10;
   try {for(int i=0;i<samples;i++) {
    game.Refresh();if(game.HasExited)break;''')
    text=text.replace('File.WriteAllText(Path.Combine(folder,i.ToString("00")+".json"),serializer.Serialize(snapshot));\n    if(i<9)Thread.Sleep(1000);', '''string json=serializer.Serialize(snapshot);
    File.WriteAllText(Path.Combine(folder,watch?"recent-"+(i%30).ToString("00")+".json":i.ToString("00")+".json"),json);
    string current=serializer.Serialize(snapshot["current_stage"]);
    if(watch&&current!=lastStage) {
     File.AppendAllText(Path.Combine(folder,"stage-observations.jsonl"),serializer.Serialize(Obj("utc",DateTime.UtcNow.ToString("o"),"from",lastStage,"to",current,"interpretation","Observed stage value only; does not prove a victory callback or stage-clear success."))+Environment.NewLine);
     File.WriteAllText(Path.Combine(folder,"stage-"+i.ToString("00000")+".json"),json);lastStage=current;
    }
    if(i<samples-1)Thread.Sleep(1000);''')
    text=text.replace('Saved 10 read-only encounter samples:', 'Saved read-only encounter samples:')
    path=ROOT/'source/CaptureEncounter.cs';path.write_text(text)
    subprocess.run([CSC,'/nologo','/platform:x64','/optimize+','/r:System.Web.Extensions.dll',
        '/out:'+str(OUT/'CaptureEncounter.exe'),str(path)],check=True)
    subprocess.run([str(OUT/'CaptureEncounter.exe'),'--self-test'],check=True)
    (OUT/'Record progression.cmd').write_text('@echo off\n"%~dp0CaptureEncounter.exe" --watch\necho Exit code: %errorlevel%\npause\n')

if __name__=='__main__':
    old,new,m=rebuild()
    bank_helpers(old,new,m)
    spider_gate(m)
    viper_guard(m)
    capture_tool()
    atlas_fallbacks(m)
    finish(m)
