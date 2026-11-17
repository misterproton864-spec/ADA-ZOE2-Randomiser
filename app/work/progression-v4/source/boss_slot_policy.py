import portable_paths as _portable
"""Canonical, per-encounter allocation. Never treat recurring fights as one slot."""
import hashlib
from collections import Counter

ALIASES = {'Bahram Anubis': 'Anubis', 'Compressed-space Anubis': 'Anubis',
           'Fake Anubis': 'Anubis', 'Aumaan Anubis': 'Anubis',
           'Anubis (fr04g)': 'Anubis'}


def canonical(name):
    return ALIASES.get(name, name)


def validate(rows):
    slots = [r['stage'] for r in rows]
    if len(slots) != len(set(slots)):
        raise ValueError('One row per distinct encounter; combine phases first')
    counts = Counter(canonical(r['identity']) for r in rows)
    repeats = sorted(k for k, n in counts.items() if n > 1)
    if repeats:
        raise ValueError('Repeated canonical boss identities: ' + ', '.join(repeats))
    return True


def allocate(eligible, seed):
    """Deterministic matching, including arena restrictions; fail on shortage."""
    if not seed:
        raise ValueError('A seed is required')
    choices = {s: sorted({canonical(x) for x in pool}) for s, pool in eligible.items()}
    identities = sorted({x for pool in choices.values() for x in pool})
    if len(identities) < len(choices):
        raise ValueError(f'Insufficient canonical identities: {len(choices)} slots, '
                         f'{len(identities)} identities; no repeated fallback permitted')
    assignment = {}; owner = {}

    def visit(slot, seen):
        ranked = sorted(choices[slot], key=lambda x: hashlib.sha256(
            (seed + '\0' + slot + '\0' + x).encode()).digest())
        for identity in ranked:
            if identity in seen:
                continue
            seen.add(identity)
            if identity not in owner or visit(owner[identity], seen):
                owner[identity] = slot; assignment[slot] = identity
                return True
        return False

    for slot in sorted(choices, key=lambda s: (len(choices[s]), s)):
        if not visit(slot, set()):
            raise ValueError('Arena compatibility prevents a unique assignment')
    rows = [dict(stage=s, identity=assignment[s]) for s in sorted(assignment)]
    validate(rows)
    return rows
