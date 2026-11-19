import portable_paths as _portable
"""Verify installation journals before changing GUI/attachment state."""
import json, os
from pathlib import Path
from file_hashes import sha

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');os.replace(temporary,path)

def confirm(package,restore=False):
    p=Path(package);journal=read(p/'installation-journal.json')
    expected='restored' if restore else 'installed'
    if journal.get('status')!=expected:raise ValueError('Journal does not confirm '+expected)
    root=Path(journal['game_root']).resolve()
    for row in journal['files']:
        target=(root/row['relative_path']).resolve()
        if not target.is_relative_to(root):raise ValueError('Journal target escapes game directory')
        actual=sha(target) if target.exists() else None
        if actual!=row['original_sha256' if restore else 'patched_sha256']:
            raise ValueError('Journal/game hash mismatch: '+row['relative_path'])
        backup=Path(row['backup'])
        backup_digest=sha(backup) if backup.exists() else None
        if not backup.exists() and Path(str(backup)+'.compact.json').is_file():
            from compact_payloads import virtual_sha
            backup_digest=virtual_sha(p,read(str(backup)+'.compact.json'))
        if backup_digest!=row['original_sha256']:
            raise ValueError('Restore backup hash mismatch: '+row['relative_path'])
    return journal

def commit(root,package,prior,restore=False):
    root=Path(root);p=Path(package);journal=confirm(p,restore)
    if restore:
        state=prior.get('previous_state') or ({'package':prior['previous_package']} if prior.get('previous_package') else {})
        if state:
            previous=Path(state['package'])
            if not (previous/'manifest.json').is_file() or not (previous/'installation-plan.json').is_file():state={}
            else:
                plan=read(previous/'installation-plan.json');game=Path(journal['game_root'])
                for row in plan['files']:
                    target=game/row['relative_path']
                    if not target.is_file() or sha(target)!=row['patched_sha256']:state={};break
    elif prior.get('package')==str(p):state=prior
    else:state=dict(package=str(p),previous_package=prior.get('package'),previous_state=prior)
    if state:
        save(root/'last-applied.json',state);save(root/'recommended-build.json',dict(package=state['package']))
    else:
        for name in ('last-applied.json','recommended-build.json'):(root/name).unlink(missing_ok=True)
    manifest=read(Path(state['package'])/'manifest.json') if state else {}
    save(root/'installation-result.json',dict(installed=bool(state),restored=restore,package=state.get('package'),
         seed=manifest.get('seed'),archive_sha256=manifest.get('patched_sha256'),
         runtime_helper_count=len(manifest.get('runtime_helpers',[])),payloads=len(journal['files']),gameplay_verified=False))
    return state

def recover(root,package,previous_package=None):
    """Adopt a manual installation only after full file + backup readback."""
    root=Path(root);p=Path(package);journal=confirm(p)
    prior=read(root/'last-applied.json') if (root/'last-applied.json').exists() else {}
    # Old pointers can name a seed already restored. Do not invent a restore chain.
    originals={r['relative_path']:r['original_sha256'] for r in journal['files']}
    previous={}
    candidate=Path(previous_package) if previous_package else Path(prior['package']) if prior.get('package') else None
    if candidate and candidate.is_dir():
        plan=read(candidate/'installation-plan.json')
        def baseline(relative):
            target=Path(journal['game_root'])/relative
            return originals[relative] if relative in originals else sha(target) if target.exists() else None
        if all(baseline(r['relative_path'])==r['patched_sha256'] for r in plan['files']) and all(baseline(r['relative_path'])==r['sha256'] for r in plan['dependencies']):
            previous=prior if prior.get('package')==str(candidate) else dict(package=str(candidate))
        elif previous_package:raise ValueError('Requested previous package does not match the verified pre-install baseline')
    state=commit(root,p,previous)
    save(p/'state-recovery.json',dict(verified=True,old_pointer=prior,new_pointer=state,payloads=len(journal['files']),
         baseline_pointer_unresolved=bool(prior and not previous),gameplay_verified=False))
    return state
