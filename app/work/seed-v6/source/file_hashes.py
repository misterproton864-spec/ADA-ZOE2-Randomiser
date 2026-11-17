import portable_paths as _portable
"""Streaming hashes without importing game archives or generation dependencies."""
import hashlib
from pathlib import Path

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
