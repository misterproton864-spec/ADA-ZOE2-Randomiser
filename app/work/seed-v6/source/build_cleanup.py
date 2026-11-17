import portable_paths as _portable
"""Local housekeeping after successful builds; never runs an AI or a scheduler."""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

BUILD_ROOT = Path(str(_portable.BUILD_ROOT))
STATE_ROOT = Path(__file__).resolve().parents[1]
KEEP_LATEST = 3
MIN_AGE_SECONDS = 48 * 60 * 60
AUTO_BUILD = re.compile(r'seed-\d{8}-\d{6}-[0-9a-f]{6}\Z')
STATE_FILES = ('last-applied.json', 'last-built.json', 'recommended-build.json',
               'installation-result.json')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & 0x400)


def checked_root(path):
    path = Path(os.path.abspath(path))
    if not path.is_dir() or any(linked(p) for p in (path, *path.parents)):
        raise ValueError('Cleanup root is missing or contains a link')
    if path.resolve(strict=True) != path:
        raise ValueError('Cleanup root changed location')
    return path


def snapshot(folder):
    """Inspect every entry without following links, including hidden entries."""
    rows = []
    for base, dirs, files in os.walk(folder, followlinks=False,
                                     onerror=lambda error: (_ for _ in ()).throw(error)):
        for path in [Path(base), *(Path(base) / n for n in files + dirs)]:
            if linked(path):
                raise ValueError('Build contains a link: ' + str(path))
            info = path.lstat()
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValueError('Build contains an unusual file: ' + str(path))
            rows.append((path.relative_to(folder).as_posix(), info.st_mode,
                         info.st_size if stat.S_ISREG(info.st_mode) else 0,
                         info.st_mtime_ns, info.st_ctime_ns, info.st_ino))
    return tuple(sorted(set(rows)))


def state_snapshot(root):
    signature, values = {}, []
    for name in STATE_FILES:
        path = root / name
        if path.exists():
            if linked(path):
                raise ValueError('Saved installation state contains a link')
            content = path.read_bytes()
            signature[name] = hashlib.sha256(content).hexdigest()
            values.append(json.loads(content.decode('utf-8-sig')))
        else:
            signature[name] = None
    return signature, values


def referenced_folders(values, root):
    """All nested restore states and backup paths count as live references."""
    found = set()
    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str) and Path(value).is_absolute():
            path = Path(os.path.abspath(value))
            if path.is_relative_to(root):
                parts = path.relative_to(root).parts
                if parts:
                    found.add(parts[0].casefold())
    visit(values)
    return found


def running_processes():
    # Inspect command lines as well as images: Python/PowerShell can be using a
    # package while their executable lives outside the build directory.
    command = ("$ErrorActionPreference='Stop'; "
               "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
               "@(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ExecutablePath,CommandLine) "
               "| ConvertTo-Json -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                             '-Command', command], capture_output=True, text=True,
                            encoding='utf-8-sig', timeout=15, check=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    rows = json.loads(result.stdout)
    if not isinstance(rows, list) or not rows:
        raise ValueError('Could not inspect running processes')
    ui_count = 0
    for row in rows:
        name = (row.get('Name') or '').casefold()
        line = (row.get('CommandLine') or '').casefold()
        if ('python' in name or name.endswith('adapter.exe')) and not line:
            raise ValueError('Could not inspect an active build/helper process')
        ui_count += 'seed_ui.py' in line
        if any(token in line for token in ('seed_builder.py', 'native_seed_builder',
                                           'install-preview.ps1', 'build-atlases.ps1')):
            # This check runs inside seed_builder.py after generation. Ignore
            # only our own completed builder, never a second build or installer.
            if row.get('ProcessId') != os.getpid():
                raise ValueError('Another build or installation is running')
    if ui_count > 1:
        raise ValueError('Another seed utility window may have an older selection')
    return rows


def complete_build(folder):
    package = folder / 'Ship-v5'
    result = read(package / 'build-result.json')
    provenance = read(package / 'build-provenance.json')
    if (result.get('installable') is not True or result.get('payloads_complete') is not True
            or Path(result['package']).resolve() != package
            or not str(result.get('build_id', '')).startswith('seed-v6.')
            or provenance.get('source_snapshot_stable') is not True
            or provenance.get('seed') != result.get('seed')
            or provenance.get('build_id') != result.get('build_id')):
        raise ValueError('Not a completed, sealed seed build')
    for name in ('manifest.json', 'build-result.json', 'installation-plan.json', 'Install-preview.ps1'):
        if provenance.get('package_hashes', {}).get(name) != digest(package / name):
            raise ValueError('Build metadata is incomplete or changed')
    return result


def write_report(path, report):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def cleanup(build_root, state_root, current, *, dry_run=True, now=None,
            process_reader=running_processes):
    """Delete only old automatic outputs, with independent safety rechecks."""
    report = dict(status='skipped', dry_run=dry_run, deleted=[], attempted=[], candidates=[],
                  kept=[], errors=[], removed_bytes=0, checked_utc=time.time())
    lock = None
    report_path = None
    try:
        root, state = checked_root(build_root), checked_root(state_root)
        report_path = state / 'build-cleanup-latest.json'
        if (state / 'disable-build-cleanup').exists():
            raise ValueError('Automatic cleanup is disabled')
        lock = state / 'build-cleanup.lock'
        try:
            with lock.open('x', encoding='utf-8') as handle:
                handle.write(str(os.getpid()))
        except FileExistsError:
            lock = None
            report_path = None
            raise ValueError('Another cleanup is running')
        current = Path(os.path.abspath(current))
        if current.name != 'Ship-v5' or current.parent.parent != root:
            raise ValueError('New build is outside the expected build folder')
        # Even the triggering build must be complete. Failed builds never prune.
        snapshot(current.parent)
        complete_build(current.parent)
        signature, saved = state_snapshot(state)
        protected = referenced_folders(saved + [str(current)], root)
        processes = process_reader()
        process_text = '\n'.join(str(row.get(k) or '') for row in processes
                                 for k in ('ExecutablePath', 'CommandLine')).replace('\\', '/').casefold()
        builds = []
        now = time.time() if now is None else now
        for folder in sorted(root.iterdir()):
            if not AUTO_BUILD.fullmatch(folder.name):
                continue  # Manually named tests, experiments and releases stay.
            reason = None
            try:
                if linked(folder) or not folder.is_dir() or folder.resolve() != folder:
                    raise ValueError('Linked or invalid folder')
                tree = snapshot(folder)
                complete_build(folder)
                builds.append(folder)
                names = [row[0] for row in tree]
                if folder.name.casefold() in protected:
                    reason = 'Current selection or restore history'
                elif any(Path(n).name in ('.keep', '.git', 'installation-journal.json')
                         or Path(n).name.startswith('installation-backups') for n in names):
                    reason = 'Pinned build or installation backups/history'
                elif folder.as_posix().casefold() in process_text:
                    reason = 'In use by a running process'
                elif now - max(row[3] for row in tree) / 1e9 < MIN_AGE_SECONDS:
                    reason = 'Less than 48 hours since its last change'
                if reason:
                    report['kept'].append(dict(path=str(folder), reason=reason))
                else:
                    report['candidates'].append(dict(path=str(folder),
                        bytes=sum(row[2] for row in tree), tree=tree))
            except (OSError, ValueError, KeyError, TypeError) as error:
                report['kept'].append(dict(path=str(folder), reason=str(error)))
        latest = set(sorted(builds, key=lambda p: p.name, reverse=True)[:KEEP_LATEST])
        candidates = []
        snapshots = {}
        for row in report['candidates']:
            folder = Path(row['path'])
            tree = row.pop('tree')
            if folder in latest:
                report['kept'].append(dict(path=str(folder), reason='One of the three newest builds'))
            else:
                candidates.append(row)
                snapshots[str(folder)] = tree
        report['candidates'] = candidates
        report['status'] = 'dry-run' if dry_run else 'completed'
        # Persist the exact intended scope before any deletion. Failure to write
        # the audit record stops cleanup without affecting the successful build.
        write_report(report_path, report)
        if dry_run or not candidates:
            return report
        processes = process_reader()  # Stop if a new builder/installer/window appeared.
        process_text = '\n'.join(str(row.get(k) or '') for row in processes
                                 for k in ('ExecutablePath', 'CommandLine')).replace('\\', '/').casefold()
        for row in candidates:
            folder = Path(row['path'])
            if folder.as_posix().casefold() in process_text:
                raise ValueError('A process started using an old build')
            if state_snapshot(state)[0] != signature:
                raise ValueError('Build selection or installation state changed during cleanup')
            if (state / 'disable-build-cleanup').exists():
                raise ValueError('Automatic cleanup was disabled')
            if (checked_root(root) != root or folder.parent != root or linked(folder)
                    or folder.resolve(strict=True) != folder
                    or snapshot(folder) != snapshots[str(folder)]):
                raise ValueError('Build changed during cleanup: ' + str(folder))
            # Only this verified immediate child of the explicitly scoped root
            # is removed. Root, sibling folders and junction targets are never removed.
            report['attempted'].append(str(folder))
            write_report(report_path, report)
            shutil.rmtree(folder)
            report['deleted'].append(row)
            report['removed_bytes'] += row['bytes']
            write_report(report_path, report)
    except Exception as error:
        report['status'] = 'partial' if report['attempted'] else 'skipped'
        report['errors'].append(str(error))
    finally:
        if lock is not None:
            try:
                lock.unlink(missing_ok=True)
            except OSError as error:
                report['errors'].append(str(error))
        if report_path is not None:
            try:
                write_report(report_path, report)
            except OSError:
                pass
    return report


def cleanup_after_build(package):
    """A cleanup failure must never turn a successful build into a failure."""
    report = cleanup(BUILD_ROOT, STATE_ROOT, package, dry_run=False)
    if report['deleted']:
        print('Old builds cleaned:', len(report['deleted']), 'folders,',
              round(report['removed_bytes'] / 1024**3, 2), 'GiB freed.', flush=True)
    elif report['errors']:
        print('Old builds retained; cleanup skipped:', '; '.join(report['errors']), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preview the automatic old-build cleanup policy; deletes nothing.')
    parser.add_argument('--current', required=True, help='Completed Ship-v5 package to preserve')
    args = parser.parse_args()
    print(json.dumps(cleanup(BUILD_ROOT, STATE_ROOT, Path(args.current)), indent=2))
