"""Seeded side-mode enemy changes using authored native manager pools."""
import hashlib
import json
import struct

from archive_tools import L
from mixed_boss_catalog import payloads
from scx_bytecode import native_calls
from scx_manager_chain_adapter import MANAGER_TYPES
from native_seed_rules import REGULAR_TYPES
from enemy_pool_mapping import mapping as distinct_mapping
from randomizer_settings import DEFAULT_WEIGHTS,weighted_enemy
from regular_selectors import patch as patch_selectors
from scx_call_arguments import UnresolvedArguments

BOSS_SEQUENCE_STAGES = frozenset(('vs_am02','vs_cs01','vs_af02','vs_fr02','vs_ef02',
                                  'vs_ef01','vs_vc01','vs_cy02','vs_wn01','vs_ba02'))


def slots_in(name, data):
    if len(data) < 32:
        raise ValueError('Short ENE: ' + name)
    count = struct.unpack_from('<H', data, 2)[0]
    base = struct.unpack_from('<I', data, 4)[0]
    if base < 32 or base + count*112 > len(data):
        raise ValueError('ENE bounds: ' + name)
    rows = []
    for record in range(count):
        start = base + record*112
        group = struct.unpack_from('<I', data, start+0x58)[0]
        for slot in range(4):
            at = start+48+slot*8
            typ, number, level = data[at:at+3]
            if number:
                rows.append(dict(file=name, record=record, slot=slot, offset=at,
                                 original_type=typ, count=number, level=level,
                                 script_group_id=group))
    return rows


def candidates(archive, seed, weights=DEFAULT_WEIGHTS):
    rows, updates = [], {}
    selectors = {int(key, 16) for key in json.loads(
        (L/'type-selector-command-catalog.json').read_text())['commands']}
    for stage in sorted(s for s in archive.stages if s.startswith('vs_')):
        if stage in BOSS_SEQUENCE_STAGES:
            rows.append(dict(stage=stage,qualified=False,reason='Boss Sequence ENE actors retained for boss mechanics'))
            continue
        files = payloads(archive, stage)
        slots = [slot for name, data in files.items() if name.endswith('.ene')
                 for slot in slots_in(name, data)]
        calls = {name: native_calls(data) for name, data in files.items() if name.endswith('.scx')}
        managers = {MANAGER_TYPES[command] for sites in calls.values() for _, command in sites if command in MANAGER_TYPES}
        present = {s['original_type'] for s in slots} & REGULAR_TYPES
        pool = sorted(managers & REGULAR_TYPES)
        mutable = present & managers
        fixed = present - managers
        row = dict(stage=stage, active_slots=len(slots), regular_slots=sum(s['original_type'] in REGULAR_TYPES for s in slots),
                   manager_pool=sorted(managers), original_types=sorted(present),
                   preserved_unmanaged_types=sorted(fixed), qualified=False)
        if not slots:
            row['reason'] = 'No ENE records'; rows.append(row); continue
        if not mutable or len(pool) < 2:
            row['reason'] = 'No mutable native manager or only one replacement type'; rows.append(row); continue
        try:
            # An unmanaged type remains byte-identical. Its groups must not
            # share a selector namespace with a changed type.
            groups = {}
            for slot in slots:
                groups.setdefault(slot['script_group_id'], set()).add(slot['original_type'])
            if any(types & fixed and types & mutable for types in groups.values()):
                raise ValueError('Unmanaged type shares an actor selector group with a mutable type')
            schedule = dict(stage=stage, slots=[s for s in slots if s['original_type'] in mutable])
            try:
                mapping = distinct_mapping(seed, stage, schedule, pool, weights)
            except ValueError:
                # The Story Mode selector adapter also supports merged native
                # pools by rewriting actor ordinals. It will fail closed below
                # if any affected selector is computed rather than literal.
                mapping = {typ:weighted_enemy(seed,stage,'native/'+str(typ),pool,weights)
                           for typ in sorted(mutable)}
            changed = files.copy()
            selector_edits = 0
            for name, sites in calls.items():
                selected = [dict(offset=at, command=command) for at, command in sites if command in selectors]
                if not selected: continue
                patched, edits = patch_selectors(files[name], selected, mapping, slots)
                changed[name] = patched
                selector_edits += len(edits)
            enemy_edits = 0
            for slot in slots:
                source = slot['original_type']
                if source not in mapping: continue
                name, at = slot['file'], slot['offset']
                data = bytearray(changed[name])
                if data[at:at+3] != bytes((source, slot['count'], slot['level'])):
                    raise ValueError('ENE record changed unexpectedly')
                data[at] = mapping[source]
                changed[name] = bytes(data)
                enemy_edits += source != mapping[source]
            row.update(qualified=True, mapping=mapping, enemy_type_changes=enemy_edits,
                       selector_changes=selector_edits, changed_files=sorted(name for name in files if changed[name] != files[name]),
                       candidate_digest=hashlib.sha256(b''.join(changed[name] for name in sorted(changed))).hexdigest())
            if row['changed_files']:
                updates[stage] = {name:changed[name] for name in row['changed_files']}
        except (UnresolvedArguments, ValueError) as error:
            row['reason'] = str(error)
        rows.append(row)
    return (dict(seed=seed, stages=rows, qualified=sum(row['qualified'] for row in rows),
                 gameplay_verified=False, archive_written=False), updates)


def preview(archive, seed, weights=DEFAULT_WEIGHTS):
    return candidates(archive, seed, weights)[0]
