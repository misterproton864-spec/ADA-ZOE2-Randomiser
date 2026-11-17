"""Static release checks; no game access, imports from the app or output files."""
import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.pac', '.wem', '.bnk', '.awb', '.mdz', '.scx', '.tex', '.wav', '.iso', '.dmp'}
ALLOWED = {'.py', '.cs', '.ps1', '.cmd', '.json', '.xml', '.tbl', '.txt', '.exe', '.obj'}
SECRETS = [re.compile(r'gh[pousr]_[A-Za-z0-9_]{20,}'),
           re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
           re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
           re.compile(r'(?i)[A-Z]:[/\\]Users[/\\][^/\\\s"\']+')]

def audit(root=ROOT):
    errors = []
    modules = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '.git' in relative.parts or '__pycache__' in relative.parts or not path.is_file():
            continue
        name = relative.as_posix()
        if path.suffix.lower() in FORBIDDEN or path.name.lower() in ('stage.dat', 'zoe2mars.exe'):
            errors.append('Game/private asset: ' + name)
        if 'app' == relative.parts[0] and path.suffix.lower() not in ALLOWED:
            errors.append('Unexpected application file type: ' + name)
        if path.suffix.lower() in ('.exe', '.obj'):
            continue
        try:
            content = path.read_text(encoding='utf-8-sig')
            if path.suffix == '.py':
                ast.parse(content, filename=name)
                modules += 1
            if path.suffix == '.json':
                json.loads(content)
            if any(pattern.search(content) for pattern in SECRETS):
                errors.append('Private path or credential pattern: ' + name)
        except (SyntaxError, UnicodeError, json.JSONDecodeError) as error:
            errors.append(name + ': ' + str(error))
    baseline = json.loads((root / 'packaging/baseline-local22.json').read_text(encoding='utf-8'))
    changed = []
    for name, expected in baseline['application_files'].items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(name)
    # Later development may change the source; this initial snapshot is deliberately pinned.
    if changed:
        errors.append('Local.22 application differs from sealed baseline: ' + ', '.join(changed))
    for name in ('LICENSE', 'THIRD-PARTY-NOTICES.txt', 'app/legacy/research/THIRD_PARTY_LICENSE.txt'):
        if not (root / name).is_file():
            errors.append('Missing licence notice: ' + name)
    return dict(passed=not errors, python_modules_checked=modules,
                pinned_app_files_checked=len(baseline['application_files']),
                game_accessed=False, gameplay_verified=False, errors=errors)

if __name__ == '__main__':
    result = audit()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
