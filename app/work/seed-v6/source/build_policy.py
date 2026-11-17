import portable_paths as _portable
"""Current release constraints. Static validation cannot certify live arenas."""
from collections import Counter
from experimental_bosses import neith_selection,neith_readiness

def assess(manifest, story):
    blockers = list(manifest.get('effective_settings',{}).get('blocked',[]))
    from boss_qualification import blockers as live_blockers
    blockers.extend(live_blockers(story))
    settings=manifest.get('settings',{})
    if any(settings.get(key) for key in ('randomise_boss_sequence','randomise_survival','randomise_extra_missions')):
        mode_proof=manifest.get('side_mode_validation',{})
        if mode_proof.get('passed') is not True:
            blockers.append('Fresh Boss Sequence/Survival archive and resource validation required.')
        if settings.get('randomise_boss_sequence') and mode_proof.get('boss_sequence_encounters')!=8:
            blockers.append('Boss Sequence did not assign all eight qualified replacement fights.')
        if settings.get('randomise_survival') and mode_proof.get('survival_stages')!=6:
            blockers.append('Survival did not change all six numbered stages.')
        if settings.get('randomise_extra_missions') and mode_proof.get('extra_missions_stages')!=6:
            blockers.append('Six currently eligible Extra Mission enemy sections were not all changed.')
        if settings.get('randomise_extra_missions') and settings.get('boss_mode')=='shuffle_test' and mode_proof.get('extra_missions_boss_battles')!=1:
            blockers.append('Extra Mission boss battle did not receive a replacement.')
    from boss_qualification import exclusion_blockers
    # Recompute from the requested pool: effective settings may remove Inhert
    # from replacement eligibility while preserving its checked native fight.
    requested=manifest.get('effective_settings',{}).get('requested',settings)
    blockers.extend(exclusion_blockers(requested,story))
    from audio_options import helpers
    from mosquito_rules import helpers as swarm_helpers
    swarm_runtime=swarm_helpers(manifest)
    from health_runtime_support import HELPER as HEALTH_HELPER
    health_runtime={HEALTH_HELPER} if manifest.get('health_multiplier_runtime',{}).get('enabled') else set()
    if swarm_runtime and manifest.get('native_preservation',{}).get('finite_swarm_readback',{}).get('passed') is not True:
        blockers.append('Finite Mosquito replacement and runtime readback required.')
    repeats=[k for k,n in Counter(r.get('identity') for r in story).items() if n>1]
    if settings.get('repeat_rule','no_repeat')=='no_repeat' and repeats:
        blockers.append('No-repeat story policy cannot be met by this pool: '+', '.join(sorted(repeats))+'. No automatic repeat override was applied.')
    if manifest.get('settings',{}).get('boss_mode')=='shuffle_test':
        from boss_test_profile import stages,boss_helpers
        from native_seed_rules import HELPERS
        if settings.get('repeat_rule') not in ('no_repeat','compatible_exhaustion'):blockers.append('Explicit boss repeat rule required.')
        if [r.get('stage') for r in story]!=list(stages(settings)):blockers.append('Test arena list differs from the protected profile.')
        proof=manifest.get('native_preservation',{});boss=manifest.get('boss_test_validation',{})
        if proof.get('passed') is not True or proof.get('protected_boss_scripts_preserved') is not True:
            blockers.append('Protected native progression readback failed.')
        if boss.get('passed') is not True or boss.get('repeat_policy_checked') is not True:
            blockers.append('Fresh full boss-spawn validation required.')
        if {r['file'] for r in manifest.get('runtime_helpers',[])}!=helpers(settings)|boss_helpers(settings,story)|swarm_runtime|health_runtime:
            blockers.append('Unexpected or missing test runtime helpers.')
        if manifest.get('settings',{}).get('include_neith_experimental'):blockers.append(neith_readiness()['reason'])
        return dict(format=2,passed=not blockers,blockers=blockers,profile='experimental-boss-test',
                    repeat_rule=settings.get('repeat_rule'),randomised_bosses=len(story),gameplay_verified=False,
                    limitations=['Boss arena spawn/movement/death and a complete Normal run remain unverified.'])
    if manifest.get('settings',{}).get('boss_mode')=='native':
        from native_seed_rules import HELPERS
        proof=manifest.get('native_preservation',{})
        if story or manifest.get('boss_changes'):blockers.append('Boss replacements are forbidden in original-boss mode.')
        if proof.get('passed') is not True or proof.get('native_boss_scripts_preserved') is not True or proof.get('imported_resources')!=proof.get('opening_imported_resources',0)+proof.get('ship_imported_resources',0):
            blockers.append('Fresh native resource and progression preservation check required.')
        if {h['file'] for h in manifest.get('runtime_helpers',[])}!=helpers(settings)|swarm_runtime|health_runtime:
            blockers.append('Original-boss mode contains unexpected runtime helpers.')
        if manifest.get('settings',{}).get('include_neith_experimental') or manifest.get('settings',{}).get('include_viola_ai'):
            blockers.append('Experimental bosses cannot be enabled in original-boss mode.')
        return dict(format=2,passed=not blockers,blockers=blockers,profile='native-bosses',
                    randomised_bosses=0,native_bosses_preserved=True,gameplay_verified=False)
    try:
        if neith_selection(manifest.get('settings',{}).get('include_neith_experimental',False)):
            blockers.append(neith_readiness()['reason'])
    except ValueError as ex:
        blockers.append(str(ex))
    counts = Counter(row.get('identity') for row in story)
    repeated = sorted(str(k) for k, n in counts.items() if n > 1)
    if repeated:
        blockers.append('No-repeat story policy: repeated main identities: ' + ', '.join(repeated))
    available = set().union(*(set(row.get('compatible', [])) for row in story))
    if len(available) < len(story):
        blockers.append(f'Boss identity shortage: {len(story)} story slots, {len(available)} compatible main identities; Anubis forms count as one.')
    include_viola = manifest.get('settings', {}).get('include_viola_ai', False)
    if not include_viola and any(row.get('variant') == 'Viola AI (full rescue fight)' for row in story):
        blockers.append('Experimental Viola AI is disabled but appears in the boss mapping.')
    # No imported arena has an attributed live spawn/movement/death/continuation record yet.
    # Never promote the historical static compatibility list into gameplay evidence.
    if story:
        blockers.append('Live arena qualification pending: actor/HP bar, AI movement, bounds, damage/death and continuation must be recorded for each assignment.')
    if manifest.get('settings',{}).get('enemy_percentages'):
        blockers.append('Enemy percentages currently cover authored regular groups; the separate runtime Spider replacement stream still needs weighted selection validation.')
    return dict(format=1, passed=not blockers, blockers=blockers,
                story_slots=len(story), compatible_main_identities=len(available),
                repeated_main_identities=repeated, gameplay_verified=False)
