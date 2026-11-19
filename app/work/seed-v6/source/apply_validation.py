from pathlib import Path
import sys
APP=Path(__file__).resolve().parents[3]
for path in (APP,APP/'work/seed-v6/source',APP/'legacy',APP/'legacy/research',APP/'work/progression-v4/source'):
    sys.path.insert(0,str(path))
import portable_paths as _portable
"""Fresh independent preflight. No game writes; diagnostic reports stay separate."""
import argparse, json, sys, traceback, uuid
from datetime import datetime, timezone
from pathlib import Path
from archive_tools import sha

from build_info import BUILD_ID
def validate(package, require_policy=True):
    from validate_boss_spawns import validate as bosses
    from verify_builds import verify as archive
    from verify_features import verify as features
    from build_policy import assess
    p = Path(package).resolve()
    read = lambda name: json.loads((p/name).read_text(encoding='utf-8-sig'))
    result, manifest, plan = (read(n) for n in ('build-result.json','manifest.json','installation-plan.json'))
    if result['seed'] != manifest['seed'] or result['archive_sha256'] != sha(p/'STAGE.DAT'):
        raise ValueError('Build seed/archive provenance mismatch')
    provenance = p/'build-provenance.json'
    if provenance.exists():
        prov = read('build-provenance.json')
        if result['build_id'] != prov['build_id'] or prov['build_id'] != BUILD_ID:
            raise ValueError('Build identity disagrees with generation provenance')
        if require_policy and not prov.get('source_snapshot_stable'):
            raise ValueError('Build has no stable generation-source snapshot; rebuild with the current utility')
        for relative, digest in prov['package_hashes'].items():
            if sha(p/relative) != digest: raise ValueError('Generation provenance hash mismatch: '+relative)
    elif require_policy:
        raise ValueError('Legacy build has no generation provenance; rebuild with the current utility. Metadata edits cannot upgrade a build.')
    for row in plan['files']:
        source = (p/row['package_path']).resolve()
        if not source.is_relative_to(p): raise ValueError('Package payload escapes package directory')
        if not source.is_file() and (p/'compact-payloads.json').is_file():
            from compact_payloads import virtual_sha
            recipes=read('compact-payloads.json')['files']
            matches=[r for r in recipes if r['file']==row['package_path']]
            if len(matches)!=1 or virtual_sha(p,matches[0])!=row['patched_sha256']:raise ValueError('Compact payload checksum mismatch')
        elif sha(source) != row['patched_sha256']: raise ValueError('Package hash mismatch: '+row['package_path'])
    for row in manifest['runtime_helpers']:
        if sha(p/'runtime'/row['file']) != row['sha256']: raise ValueError('Runtime helper hash mismatch: '+row['file'])
    if manifest.get('settings',{}).get('boss_mode') in ('native','shuffle_test'):
        from validate_native_seed import verify as native
        checks=dict(native=native(p))
        manifest=dict(manifest,native_preservation=checks['native'])
        if manifest['settings']['boss_mode']=='shuffle_test':
            checks['bosses']=bosses(p)
            manifest['boss_test_validation']=checks['bosses']
        if any(manifest['settings'].get(key) for key in ('randomise_boss_sequence','randomise_survival','randomise_extra_missions')):
            from validate_side_modes import verify as side_modes
            checks['side_modes']=side_modes(p)
            manifest['side_mode_validation']=checks['side_modes']
    else:
        checks = dict(archive=archive(p), features=features(p,write_report=False), bosses=bosses(p))
    policy = assess(manifest, read('boss-mapping.json'))
    if require_policy and (not policy['passed'] or not result.get('installable')):
        raise ValueError('Build is diagnostic only: '+'; '.join(policy['blockers']))
    return dict(passed=True, seed=result['seed'], build_id=result['build_id'],
                archive_sha256=result['archive_sha256'], payloads_checked=len(plan['files']),
                checks=checks, release_policy=policy, gameplay_verified=False)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--diagnostic-only',action='store_true')
    args=parser.parse_args();started=datetime.now(timezone.utc).isoformat();code=1
    try:
        report=validate(args.package,not args.diagnostic_only);code=0
    except Exception as ex:
        report=dict(passed=False,error=str(ex),gameplay_verified=False)
        traceback.print_exc()
    report.update(attempt_id=uuid.uuid4().hex,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),
                  package=str(Path(args.package).resolve()),python=sys.executable,diagnostic_only=args.diagnostic_only)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(('PASS fresh build preflight' if code==0 else 'FAIL fresh build preflight: '+report['error']),flush=True)
    return code
if __name__=='__main__':sys.exit(main())
