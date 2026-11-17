import portable_paths as _portable
#!/usr/bin/env python3
"""Read-only ZOE2 MARS STAGE.DAT inspector. This is NOT a randomiser.

Archive algorithms adapted from Missingno_force/Missingmew's tools-mgs,
dat-extract_enc.c and strcode.c. This is an altered Python implementation,
not the upstream tool. See THIRD_PARTY_LICENSE.txt and RESEARCH.md.
Only the encrypted little-endian ZOE2 archive profile is supported.
"""
import argparse
import array
import json
from pathlib import Path
import re
import struct
import sys
import zlib

MASK = 0xffffffff
MULT = 0x02e90edd
FOLDERS = {0x7f010000: 'nocache', 0x7f000002: 'cache',
           0x7f000003: 'resident', 0x7f000010: 'sound',
           0x7f000004: 'delayload', 0x7f000005: 'delayload_w'}
RAW = {0x7f000010, 0x7f000004, 0x7f000005}
EXT = {0x3b12fb:'mdz', 0x1e5452:'tex', 0x66e60c1:'flw', 0x54d5:'o2d',
       0xed22c7:'mtl', 0x856a:'mts', 0xcb3b7a:'cvz', 0x37b1e7:'hzt',
       0x62877d7f:'bin', 0x3696528:'fnt', 0x863be:'scx', 0x38ab1d7:'mfl',
       0x1ced17:'lit', 0x10abbd:'hz2', 0x688d9eb:'ene', 0x37e6b:'eft',
       0x1373d8:'trz', 0x398168e9:'row', 0x321e:'rpd', 0x3b530d:'mtz',
       0x104639:'ric', 0xe56:'var'}

def align(n, boundary=2048):
    return (n + boundary - 1) // boundary * boundary

def strcode32(s):
    result = 0
    for n, c in enumerate(s.encode('ascii')):
        result = (result + ((result << (c & 15)) |
                  ((result >> 3) + (c << (n & 15)) + c))) & MASK
    return result

def xor_words(data, key, increment):
    if len(data) % 4:
        raise ValueError('Word stream is not aligned')
    words = array.array('I')
    words.frombytes(data)
    if sys.byteorder != 'little':
        words.byteswap()
    for i in range(len(words)):
        words[i] ^= key
        key = (key * MULT + increment) & MASK
    if sys.byteorder != 'little':
        words.byteswap()
    return words.tobytes()

def read_exact(f, start, size):
    if start < 0 or size < 0:
        raise ValueError('Negative file range')
    f.seek(start)
    result = f.read(size)
    if len(result) != size:
        raise ValueError('Truncated archive')
    return result

class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.size = self.path.stat().st_size
        with self.path.open('rb') as f:
            self.seed = struct.unpack('<I', read_exact(f, 0, 4))[0]
            header = xor_words(read_exact(f, 4, 12), self.seed, self.seed ^ 0xf0f0)
            version, blocks, count, game, tag = struct.unpack('<4HI', header)
            if version != 1 or game != 0x0806 or not 0 < count < 10000:
                raise ValueError('Unsupported archive profile')
            table_size = 12 + 20 * count
            if table_size + 4 > blocks * 2048:
                raise ValueError('Invalid archive directory size')
            table = xor_words(read_exact(f, 4, table_size), self.seed, self.seed ^ 0xf0f0)
            self.header = dict(version=version, directory_sectors=blocks,
                               section_count=count, game=game, tag=tag, seed=self.seed)
            self.stages = {}
            for i in range(count):
                raw, sector = struct.unpack_from('<16sI', table, 12 + 20 * i)
                name = raw.split(b'\0', 1)[0].decode('ascii')
                if not re.fullmatch('[A-Za-z0-9_]+', name) or name in self.stages:
                    raise ValueError('Invalid or duplicate section name')
                if not blocks * 2048 <= sector * 2048 < self.size:
                    raise ValueError('Section outside archive')
                self.stages[name] = sector * 2048

    def groups(self, name):
        pos = self.stages[name]
        h = strcode32(name)
        key = (129 * h + self.seed + 0xa78925d9) & MASK
        inc = (129 * h + 0x7a88fb59) & MASK
        with self.path.open('rb') as f:
            count = struct.unpack('<I', xor_words(read_exact(f, pos, 4), key, inc))[0]
            if not 0 < count < 100000:
                raise ValueError('Invalid section table size')
            raw = xor_words(read_exact(f, pos, 4 + 12 * count), key, inc)
        entries = [struct.unpack_from('<III', raw, 4 + 12*i) for i in range(count)]
        data_start = pos + align(len(raw))
        stream_pos = data_start
        groups = []
        i = 0
        while i < count and entries[i][0] and entries[i][2]:
            folder, _, decoded_size = entries[i]
            if folder not in FOLDERS:
                raise ValueError(f'Unknown group {folder:08x}')
            i += 1
            if folder in RAW:
                location, compressed_size = stream_pos, None
            else:
                packed, _, rel = entries[i]
                if packed >> 24 != 0x7e:
                    raise ValueError('Missing compression descriptor')
                compressed_size = packed & 0xffffff
                location = data_start + rel
                i += 1
            start = i
            while i < count and entries[i][0] != 0x7f000000:
                i += 1
            if i == count:
                raise ValueError('Missing group terminator')
            files = []
            for j in range(start, i):
                ext, hash_id, offset = entries[j]
                end = entries[j+1][2]
                if not 0 <= offset <= end <= decoded_size:
                    raise ValueError('Invalid contained file range')
                extension = EXT.get(ext, f'ext_{ext:08x}') if folder not in RAW else 'sdx'
                filename = f'{hash_id:08x}.{extension}' if folder not in RAW else f'pk{ext:06x}.sdx'
                files.append(dict(name=filename, offset=offset, size=end-offset))
            stored_size = compressed_size if compressed_size is not None else decoded_size
            if location + align(stored_size, 4) > self.size:
                raise ValueError('Group outside archive')
            groups.append(dict(folder=FOLDERS[folder], location=location,
                               compressed_size=compressed_size, decoded_size=decoded_size,
                               files=files))
            stream_pos = align(stream_pos + align(stored_size, 4))
            i += 1
        return groups

    def decode(self, group):
        with self.path.open('rb') as f:
            if group['compressed_size'] is None:
                return read_exact(f, group['location'], group['decoded_size'])
            data = read_exact(f, group['location'], align(group['compressed_size'], 4))
        key16 = struct.unpack_from('<H', data)[0] ^ 0x9385
        key = key16 | ((key16 ^ 0x6576) << 16)
        data = bytearray(xor_words(data, key, key16 * 0x116))
        first = (struct.unpack_from('<H', data)[0] + 0x8f3) & 0xffff
        struct.pack_into('<H', data, 0, first)
        decoder = zlib.decompressobj()
        result = decoder.decompress(data, group['decoded_size'] + 1)
        if len(result) != group['decoded_size'] or not decoder.eof:
            raise ValueError('Decoded size or zlib end marker mismatch')
        return result

    def inventory(self):
        return dict(archive=self.path.name, size=self.size, header=self.header,
                    stages={name: dict(offset=pos, groups=self.groups(name))
                            for name, pos in self.stages.items()})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--index', type=Path, help='Write a JSON archive index')
    parser.add_argument('--stage', help='Extract selected section, e.g. wn02')
    parser.add_argument('--out', type=Path, help='Output folder; originals are never modified')
    parser.add_argument('--extensions', default='scx,ene', help='Comma-separated file extensions')
    args = parser.parse_args()
    archive = Archive(args.archive)
    if args.index:
        with args.index.open('x', encoding='utf-8') as f:
            json.dump(archive.inventory(), f, indent=2)
        print(f'Indexed {len(archive.stages)} sections: {args.index}')
    if args.stage:
        if args.out is None:
            parser.error('--stage requires --out')
        wanted = {'.' + x.lstrip('.') for x in args.extensions.split(',')}
        for group in archive.groups(args.stage):
            selected = [x for x in group['files'] if Path(x['name']).suffix in wanted]
            if not selected:
                continue
            data = archive.decode(group)
            for entry in selected:
                dest = args.out / args.stage / group['folder'] / entry['name']
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open('xb') as f:
                    f.write(data[entry['offset']:entry['offset']+entry['size']])
                print(dest)
    if not args.index and not args.stage:
        print('\n'.join(archive.stages))

if __name__ == '__main__':
    main()
