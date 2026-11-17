import portable_paths as _portable
"""Validated archive transaction with a persistent recovery journal.

No process hooks, executable changes, or save changes are performed here.
"""
import hashlib,json,os,shutil
from pathlib import Path

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4194304),b''):digest.update(block)
    return digest.hexdigest()

def save(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.writing')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    os.replace(temporary,path)

def apply(rows,statefile,newstate,journalfile,closed,after_commit=None):
    """Rows contain target/candidate/previous/backup and their pinned hashes.

    Validate the whole transaction before staging. Preserve the old state until
    every archive has committed; the journal makes interrupted commits recoverable.
    """
    statefile=Path(statefile);journalfile=Path(journalfile)
    old=json.loads(statefile.read_text())
    if journalfile.exists():
        prior=json.loads(journalfile.read_text())
        if prior.get('status') not in ('complete','rolled-back'):
            raise RuntimeError('Unfinished installation journal requires recovery')
    closed();targets=set();prepared=[]
    for row in rows:
        paths={key:Path(row[key]).resolve() for key in ('target','candidate','previous','backup')}
        target=paths['target'];temporary=target.with_name(target.name+'.zoe2-mixed.tmp')
        if target in targets or target in (paths['candidate'],paths['previous'],paths['backup']):
            raise ValueError('Duplicate or overlapping transaction paths')
        targets.add(target)
        if temporary.exists():raise RuntimeError('Unexpected staging file: '+str(temporary))
        for key,digest in (('target','old_sha256'),('previous','old_sha256'),('backup','original_sha256'),('candidate','new_sha256')):
            if sha(paths[key])!=row[digest]:raise ValueError('Hash mismatch: '+key+' '+str(paths[key]))
        prepared.append(dict(row,**{k:str(v) for k,v in paths.items()},temporary=str(temporary)))
    if not prepared:raise ValueError('Empty transaction')
    if any(Path(row[key]) in targets for row in prepared for key in ('candidate','previous','backup')):
        raise ValueError('Recovery or candidate path overlaps a live target')
    for target in targets:
        needed=sum(Path(r['candidate']).stat().st_size for r in prepared if Path(r['target']).anchor==target.anchor)
        if shutil.disk_usage(target.parent).free<needed+268435456:raise RuntimeError('Insufficient staging space')
    journal=dict(status='staging',rows=prepared,previous_state=old,new_state=newstate,committed=[])
    save(journalfile,journal)
    try:
        for row in prepared:
            closed();shutil.copy2(row['candidate'],row['temporary'])
            if sha(row['temporary'])!=row['new_sha256']:raise ValueError('Staged archive mismatch')
        journal['status']='committing';save(journalfile,journal)
        for row in prepared:
            closed()
            if sha(row['target'])!=row['old_sha256']:raise ValueError('Live archive changed during staging')
            os.replace(row['temporary'],row['target'])
            journal['committed'].append(row['target']);save(journalfile,journal)
            if sha(row['target'])!=row['new_sha256']:raise ValueError('Committed archive mismatch')
            if after_commit:after_commit(len(journal['committed']))
        save(statefile,newstate)
        journal['status']='complete';save(journalfile,journal)
    except BaseException:
        recover(journalfile,statefile,closed)
        raise

def recover(journalfile,statefile,closed):
    journalfile=Path(journalfile);journal=json.loads(journalfile.read_text())
    if journal['status'] in ('complete','rolled-back'):return
    closed()
    # Validate all recovery inputs before changing any archive. Inspect hashes,
    # rather than only the commit list, to handle a crash after replace.
    for row in journal['rows']:
        target=Path(row['target']).resolve()
        if Path(row['temporary']).resolve()!=target.with_name(target.name+'.zoe2-mixed.tmp'):
            raise ValueError('Recovery has an unexpected staging path')
        if sha(row['previous'])!=row['old_sha256']:raise ValueError('Recovery source changed')
        if sha(row['target']) not in (row['old_sha256'],row['new_sha256']):
            raise ValueError('Recovery refuses an unknown live archive')
    journal['status']='rolling-back';save(journalfile,journal)
    for row in reversed(journal['rows']):
        closed();temporary=Path(row['temporary'])
        if sha(row['target'])==row['new_sha256']:
            shutil.copy2(row['previous'],temporary)
            if sha(temporary)!=row['old_sha256']:raise ValueError('Recovery staging mismatch')
            os.replace(temporary,row['target'])
        elif temporary.exists():temporary.unlink()
        if sha(row['target'])!=row['old_sha256']:raise ValueError('Recovery mismatch')
    save(statefile,journal['previous_state'])
    journal['status']='rolled-back';save(journalfile,journal)
