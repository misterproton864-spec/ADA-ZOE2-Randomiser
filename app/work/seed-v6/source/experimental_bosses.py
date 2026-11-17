import portable_paths as _portable
"""Experimental options must not stand in for an implemented actor or controller."""
NEITH_LABEL = 'Neith — 2nd fight, phases 1 + 2 (Experimental)'
NEITH_ENCOUNTER = 'ZOE1 Neith second fight'
NEITH_PHASES = (1, 2)
NEITH_BLOCKER = ('Neith is selected, but her original ZOE1 second-fight port is not playable yet. '
                 'Both phases, model/animation conversion, original combat AI, the phase transition, '
                 'damage/death and arena completion are still required. '
                 'Turn Neith off to build the other options.')

class ExperimentalBossUnavailable(ValueError):
    pass

def neith_selection(enabled=False):
    if type(enabled) is not bool:
        raise ValueError('Neith experimental toggle must be true or false')
    return enabled

def neith_readiness():
    # There is no PC factory/controller integration yet. A research JSON file,
    # imported model, or static validator pass cannot change this fact.
    return dict(name='Neith', experimental=True, default_enabled=False,
                behaviour='original ZOE1 AI only', playable=False, installable=False,
                encounter=NEITH_ENCOUNTER, required_phases=list(NEITH_PHASES),
                source_phase_mapping_verified=False, phase_transition_verified=False,
                phases=[dict(phase=n, original_ai_integrated=False,
                             combat_lifecycle_verified=False, gameplay_verified=False)
                        for n in NEITH_PHASES],
                model_conversion_verified=False, original_ai_integrated=False,
                combat_lifecycle_verified=False, arena_completion_verified=False,
                reason=NEITH_BLOCKER)

def require_neith_available(enabled=False):
    if neith_selection(enabled):
        raise ExperimentalBossUnavailable(NEITH_BLOCKER)

def neith_status(enabled=False):
    return ('Neith selected — port not ready; Build and Apply remain blocked for this option.'
            if neith_selection(enabled) else
            'Neith OFF • 2nd fight, phases 1 + 2; original ZOE1 AI port is not playable yet.')
