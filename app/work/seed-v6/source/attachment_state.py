import portable_paths as _portable
"""Read-only attachment eligibility. A saved GUI pointer is not install evidence."""
import argparse
import json
from pathlib import Path

from file_hashes import sha
from install_state import read


def _target(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Installation path escapes the game directory: ' + relative)
    return path


def inspect(root, selected=None):
    report = dict(ready=False, game_modified=False, helpers_started=False,
                  scope='Installation receipt, selected build and installed archive; runtime rechecks all files')
    errors = []
    try:
        if selected:
            selected = Path(selected).resolve()
            result = read(selected / 'build-result.json')
            report.update(selected_package=str(selected), selected_seed=result['seed'])
            if result.get('installable') is not True:
                errors.append('Selected seed ' + result['seed'] + ' is diagnostic only and was not approved for Apply. '
                              + '; '.join(result.get('blocked_reasons', ['Release checks have not passed.'])))
        state_path = Path(root) / 'last-applied.json'
        if not state_path.is_file():
            errors.append('No applied seed is recorded. Build and successfully Apply an installable seed before attaching.')
        else:
            package = Path(read(state_path)['package']).resolve()
            manifest = read(package / 'manifest.json')
            plan = read(package / 'installation-plan.json')
            applied = read(package / 'build-result.json')
            if applied['seed'] != manifest['seed']:
                raise ValueError('Recorded build seed and manifest disagree')
            if applied.get('installable') is not True and (not selected or selected != package):
                errors.append('The recorded build is diagnostic only; it is not eligible for attachment.')
            report.update(package=str(package), recorded_seed=manifest['seed'])
            if selected and selected != package:
                errors.append('The selected seed is not the applied seed. Attach will not fall back to an older seed.')
            journal_path = package / 'installation-journal.json'
            if not journal_path.is_file():
                errors.append('No successful Apply receipt exists for the recorded seed.')
            else:
                journal = read(journal_path)
                if journal.get('status') != 'installed':
                    errors.append('The recorded installation is ' + str(journal.get('status')) + '. Apply must finish successfully before attachment.')
                game = Path(journal['game_root']).resolve()
                rows = {r['relative_path'].replace('\\', '/').lower(): r for r in journal['files']}
                stage = next(r for r in plan['files'] if r['relative_path'].replace('\\', '/').lower() == 'zoe2/stage.dat')
                for row in plan['files']:
                    _target(game, row['relative_path'])
                    receipt = rows.get(row['relative_path'].replace('\\', '/').lower())
                    if receipt is None or receipt['patched_sha256'] != row['patched_sha256']:
                        raise ValueError('Apply receipt does not match this build: ' + row['relative_path'])
                if stage['patched_sha256'] != manifest['patched_sha256']:
                    raise ValueError('Build manifest and installation plan disagree on the archive')
                installed = _target(game, stage['relative_path'])
                actual = sha(installed) if installed.is_file() else None
                report.update(game_root=str(game), expected_stage_sha256=stage['patched_sha256'], actual_stage_sha256=actual)
                if actual != stage['patched_sha256']:
                    from original_inputs import STAGE_SHA
                    description = 'The game archive is vanilla' if actual == STAGE_SHA else 'The game archive is missing or belongs to another build'
                    errors.append(description + '; the saved Apply record is stale. Close the game and successfully Apply an installable seed before attaching.')
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as ex:
        errors.append('Attachment evidence could not be verified: ' + str(ex))
    report['errors'] = errors
    report['ready'] = not errors
    report['message'] = ('Ready to attach installed seed ' + report['recorded_seed']) if not errors else '\n\n'.join(errors)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--selected')
    args = parser.parse_args()
    report = inspect(args.state_root, args.selected)
    print(json.dumps(report, indent=2))
    return 0 if report['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
