import portable_paths as _portable
"""The first native-boss profile changes existing pools, never imports actors."""
REGULAR_STAGES = frozenset(('ca00','cad1','ca01','ba01','ds00','ds02','wn00','cy01','ex01','tr01','ef03','fr01','ds00g','ds01g','fr01c'))
REGULAR_TYPES = frozenset((31,32,40,41,42,43))
HELPERS = frozenset(('MusicTrackAdapter.exe','MusicSectorAdapter.exe','SeededMetatronAdapter.exe'))
PROTECTED = ('All original boss fights and callbacks; Zakat; Vector Cannon; infected-Ardjet removal; '
             'native Spider/objective actors; Mosquito/swarm; BAHRAM ship, Vascilia Sky/rescue '
             'and reported final-kill regression stages. Singleton or unresolved regular pools remain native.')


def mode(value='native'):
    if value not in ('native','shuffle','shuffle_test'):
        raise ValueError('Unknown boss mode')
    return value
