"""Seed-scoped HP monitor payload. No game executable or archive HP edits."""
import shutil
from pathlib import Path

from archive_tools import sha

HELPER='HealthMultiplierAdapter.exe'
SOURCE=Path(__file__).resolve().parent
PROTOTYPE=SOURCE/'HealthMultiplierAdapter.cs'
PINNED_EXE='b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92'


def targets(rows):
    result=set()
    for row in rows:
        stage=row['stage']
        for site in row['sites']:
            for phase in site['phases']:
                ident=phase['actor_id']
                if type(ident) is not int or not 0<=ident<=0xffffffff:
                    raise ValueError('Invalid boss HP actor identity: '+stage)
                result.add((stage,ident))
    return sorted(result)


def install(out,options,bosses,side_bosses,expected_game_exe_sha):
    enemy=options['enemy_health_multiplier'];boss=options['boss_health_multiplier']
    enabled=enemy>1 or boss>1
    report=dict(enabled=enabled,enemy_multiplier=enemy,boss_multiplier=boss,
                attached_at_main_menu=enabled,gameplay_verified=False)
    if not enabled:return report
    if expected_game_exe_sha!=PINNED_EXE:
        raise ValueError('Health monitor supports only the pinned ZOE2 executable')
    rows=targets(bosses+side_bosses)
    if boss>1 and not rows:
        raise ValueError('Boss health multiplier has no shuffled boss targets in this build')
    path=Path(out)/'health-boss-targets.tsv'
    path.write_text(''.join('{}\t{}\n'.format(stage,ident) for stage,ident in rows),encoding='utf-8')
    runtime=Path(out)/'runtime'
    source=PROTOTYPE
    if not source.is_file():raise ValueError('Health monitor source is missing')
    shutil.copy2(source,runtime/source.name)
    # The packaged helper is compiled and self-tested during candidate preparation.
    helper=SOURCE/HELPER
    if not helper.is_file():raise ValueError('Health monitor executable is missing')
    shutil.copy2(helper,runtime/HELPER)
    report.update(helper=HELPER,helper_sha256=sha(runtime/HELPER),
                  source_sha256=sha(runtime/source.name),target_file=path.name,
                  target_sha256=sha(path),target_count=len(rows),
                  stages=sorted({stage for stage,_ in rows}),
                  native_boss_mode_supported=False,
                  runtime_log='health-multiplier.log')
    return report
