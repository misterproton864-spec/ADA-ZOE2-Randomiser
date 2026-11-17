import portable_paths as _portable
"""Restore Anubis 2's original SCX class/resource registration before spawn."""
from boss_donor_initialisation import REGISTRATIONS
ANUBIS2_FACTORY=0xb7d9f1ad
ANUBIS2_REGISTRATION=0xcfab21f2
# fr04g dfd7b35d.scx: native call13618, type9, before spawn13683.
# Handler140521eb0 ->1478857b0 registers abs_stl/anubis motion and type9.
REGISTRATIONS[ANUBIS2_FACTORY]=ANUBIS2_REGISTRATION
