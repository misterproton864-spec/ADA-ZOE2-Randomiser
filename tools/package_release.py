"""Package the checked Local.24 source using the pinned Local.22 runtime."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_repository import audit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'ADA-Beta-Tester-Edition/'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def package(baseline_zip, output):
    result = audit()
    if not result['passed']:
        raise ValueError('Source audit failed: ' + repr(result['errors']))
    baseline_zip, output = Path(baseline_zip).resolve(), Path(output).resolve()
    if output.exists() or output == baseline_zip:
        raise FileExistsError('Choose a new output filename; existing packages are preserved')
    metadata = json.loads((ROOT / 'packaging/baseline-local22.json').read_text(encoding='utf-8'))
    if sha(baseline_zip.read_bytes()) != metadata['baseline_zip_sha256']:
        raise ValueError('Baseline ZIP SHA-256 does not match the sealed Local.22 input')
    rows = {}
    with zipfile.ZipFile(baseline_zip) as original:
        if original.testzip() is not None:
            raise ValueError('Baseline ZIP failed its CRC check')
        for info in original.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(PREFIX):
                raise ValueError('Unexpected baseline archive root')
            name = info.filename[len(PREFIX):]
            if name.startswith('runtime/') or name == 'ADA Randomiser.exe':
                rows[name] = original.read(info)
    for path in sorted((ROOT / 'app').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'):
            rows[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for target, source in {
        'README.md': 'docs/TESTER-GUIDE.md',
        'KNOWN-ISSUES.md': 'docs/KNOWN-ISSUES.md',
        'CHANGELOG.md': 'docs/CHANGELOG.md',
        'BUG-REPORT-TEMPLATE.md': 'docs/BUG-REPORT-TEMPLATE.md',
        'build-verification.json': 'docs/build-verification.json',
        'LICENSE': 'LICENSE',
        'THIRD-PARTY-NOTICES.txt': 'THIRD-PARTY-NOTICES.txt',
    }.items():
        rows[target] = (ROOT / source).read_bytes()
    rows['DISTRIBUTION-NOTE.txt'] = (
        'ADA 6.4.15-local.24 - experimental source candidate\n\n'
        'Application source matches the checked Local.24 snapshot.\n'
        'The launcher and Python runtime come from the pinned Local.22 baseline.\n'
        'Includes Local.23 boss candidates and Local.24 audio/diagnostics changes.\n'
        'No live gameplay or second-PC qualification is claimed by this repackaging.\n'
    ).encode('utf-8')
    # The manifest covers additions as well as the unchanged original binaries/runtime.
    hashes = {name: sha(data) for name, data in sorted(rows.items())}
    manifest = dict(format=1, edition='experimental-beta-public', version='6.4.15-local.24',
                    distribution_revision='github.1', game_assets_included=False, files=hashes)
    rows['package-manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    forbidden = {'.pac', '.wem', '.bnk', '.awb', '.mdz', '.scx', '.tex', '.wav', '.iso', '.dmp'}
    for name in rows:
        if Path(name).suffix.lower() in forbidden or Path(name).name.lower() in ('stage.dat', 'zoe2mars.exe'):
            raise ValueError('Refusing to distribute game/private asset: ' + name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as packaged:
        for name, data in sorted(rows.items()):
            packaged.writestr(PREFIX + name, data)
    with zipfile.ZipFile(output) as packaged:
        if packaged.testzip() is not None:
            raise ValueError('Output ZIP failed CRC')
        for name, expected in hashes.items():
            if sha(packaged.read(PREFIX + name)) != expected:
                raise ValueError('Output hash mismatch: ' + name)
    print(json.dumps(dict(passed=True, output=str(output), bytes=output.stat().st_size,
                         sha256=sha(output.read_bytes()), app_files=len(metadata['application_files']),
                         application_matches_local24_snapshot=True, gameplay_verified=False), indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-zip', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    package(args.baseline_zip, args.output)
