"""Keep shuffled speech compatible with its destination's playback context."""
import hashlib
import re


def vector_cue(name):
    return re.fullmatch(r'vca0c[0-9a-f]{3}\.wav', name) is not None


def compatible(destination, donor, media, audibility):
    """WEM headers alone cannot guarantee a valid destination voice layout."""
    left, right = media[destination], media[donor]
    if destination == donor or left['data'] == right['data']:
        return False
    for field in ('codec_tag', 'sample_rate'):
        if left['format'][field] != right['format'][field]:
            return False
    # Mono and stereo gameplay speech share the normal voice bus. Seven-channel
    # authored scenes remain within the cinematic pool, including processed pairs.
    if (left['format']['channels'] > 2) != (right['format']['channels'] > 2):
        return False
    if left['format']['channels'] > 2 and left['format']['channels'] != right['format']['channels']:
        return False
    scene = lambda item: re.fullmatch(r's[0-9]+m[0-9]+_(?:Re_)?Ada_E(?:ab|bb)?\.wav',item['name']) is not None
    if scene(left) != scene(right):
        return False
    if scene(left):
        low, high = sorted((audibility[destination]['seconds'], audibility[donor]['seconds']))
        if low <= 0 or high > 2 * low:
            return False
    if vector_cue(left['name']):
        # Charging cues are advanced/stopped by the native weapon sequence.
        # Keep a donor within the original slot; do not alter weapon timing.
        return (left['format']['channels'] == right['format']['channels']
                and audibility[donor]['seconds'] <= audibility[destination]['seconds'])
    return True


def constrain(mapping, media, audibility, seed):
    """Repair the permutation, preferring existing donors where safe.

    An augmenting path moves an already assigned donor when another destination
    needs it. Every selected line still changes and every donor is used once.
    """
    candidates = {}
    for destination in sorted(mapping):
        choices = [donor for donor in mapping
                   if compatible(destination, donor, media, audibility)]
        choices.sort(key=lambda donor: (
            donor != mapping[destination],
            hashlib.sha256((str(seed)+'\0ada-routing-v1\0'+destination+'\0'+donor).encode()).digest()))
        if not choices:
            raise ValueError('No compatible spoken donor for '+media[destination]['name'])
        candidates[destination] = choices
    owner = {}

    def assign(destination, seen):
        for donor in candidates[destination]:
            if donor in seen:
                continue
            seen.add(donor)
            if donor not in owner or assign(owner[donor], seen):
                owner[donor] = destination
                return True
        return False

    for destination in sorted(mapping, key=lambda key: (len(candidates[key]), key)):
        if not assign(destination, set()):
            raise ValueError('Cannot shuffle every selected ADA line with safe playback constraints')
    result = {destination: donor for donor, destination in owner.items()}
    if set(result) != set(mapping) or set(result.values()) != set(mapping):
        raise ValueError('ADA routing lost a selected line')
    return result


def summary(mapping, media, audibility):
    vectors = []
    for destination, donor in sorted(mapping.items()):
        if not compatible(destination, donor, media, audibility):
            raise ValueError('Incompatible ADA playback route: '+media[destination]['name'])
        if vector_cue(media[destination]['name']):
            vectors.append(dict(destination=media[destination]['name'], donor=media[donor]['name'],
                                native_seconds=audibility[destination]['seconds'],
                                donor_seconds=audibility[donor]['seconds']))
    return dict(gameplay_and_cinematic_layouts_separated=True, scene_recordings_separated=True,
                scene_duration_ratio_limit=2, codec_and_rate_checked=True, checked_lines=len(mapping),
                vector_cannon_timing_checked=True, vector_cannon_routes=vectors,
                native_weapon_mechanics_unchanged=True, in_game_playback_verified=False)
