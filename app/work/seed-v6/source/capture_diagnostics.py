import portable_paths as _portable
"""Build the read-only recorder with seed and pre-entry resource diagnostics."""
import json, subprocess
from pathlib import Path
from archive_tools import W

CSC = _portable.compiler()

def build(out, seed, archive_sha256):
    out = Path(out)
    source = (W/'progression-v4/source/CaptureEncounter.cs').read_text()
    marker = 'var snapshot=Obj("utc",'
    assert source.count(marker) == 1
    source = source.replace(marker, 'var snapshot=Obj("candidate_seed",'+json.dumps(str(seed))+',"archive_sha256",'+json.dumps(archive_sha256)+',"utc",')
    marker = '      "registry_count",'
    assert source.count(marker) == 1
    fields = '''      "loading_stage",Try(delegate{return System.Text.Encoding.ASCII.GetString(Read(VA(0x141542708),16)).Split((char)0)[0];}),
      "resource_phase",Try(delegate{return U32(Ptr(VA(0x1415441d8))+0x5c);}),
      "resource_part",Try(delegate{return U32(VA(0x1410f1d7c));}),
      "scripted_arena_clamp",Try(delegate{long clamp=Ptr(VA(0x141535930));return Obj("enabled_mask",U32(clamp+0x64),"inner_bounds_hex",BitConverter.ToString(Read(clamp,32)),"outer_bounds_hex",BitConverter.ToString(Read(clamp+0x20,32)));}),
      "sky_resource_filter_entry_hex",Try(delegate{return BitConverter.ToString(Read(VA(0x14008a9c0),7));}),
'''
    source = source.replace(marker, fields+marker)
    source = source.replace('string current=serializer.Serialize(snapshot["current_stage"]);',
                            'string current=serializer.Serialize(Obj("current_stage",snapshot["current_stage"],"loading_stage",snapshot["loading_stage"],"resource_phase",snapshot["resource_phase"],"resource_part",snapshot["resource_part"]));')
    from encounter_counters import augment
    source = augment(source)
    from viper_diagnostics import augment as augment_viper
    source = augment_viper(source)
    from viola_diagnostics import augment as augment_viola
    source = augment_viola(source,seed)
    from aumaan_diagnostics import augment as augment_aumaan
    source = augment_aumaan(source)
    from inhert_diagnostics import augment as augment_inhert
    source = augment_inhert(source)
    from native_pool_diagnostics import augment as augment_native_pool
    source = augment_native_pool(source)
    path = out/'CaptureEncounter.cs'
    path.write_text(source)
    subprocess.run([CSC,'/nologo','/platform:x64','/optimize+','/r:System.Web.Extensions.dll','/out:'+str(out/'CaptureEncounter.exe'),str(path)],check=True)
    subprocess.run([str(out/'CaptureEncounter.exe'),'--self-test'],check=True)
