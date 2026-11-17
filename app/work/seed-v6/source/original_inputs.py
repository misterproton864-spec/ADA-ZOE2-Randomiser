import portable_paths as _portable
from pathlib import Path
from file_hashes import sha
from beta_support import STAGE as STAGE_SHA,ATLASES as ATLAS_HASHES
def pinned_input(candidates,expected):
 for p in map(Path,candidates):
  if p.is_file():
   if sha(p)!=expected:raise ValueError('Preserved original hash differs: '+str(p))
   return dict(path=str(p.resolve()),sha256=expected)
 raise FileNotFoundError('Run initial beta setup to preserve original game inputs.')
def resolve_stage(vanilla_stage=None):return pinned_input([_portable.ORIGINALS/'ZOE2/STAGE.DAT'],STAGE_SHA)
def resolve(game,vanilla_stage=None):
 return dict(format=1,game_root=str(Path(game).resolve()),stage=resolve_stage(),atlases={n:pinned_input([_portable.ORIGINALS/'atlas'/n],h) for n,h in ATLAS_HASHES.items()},source_access='read-only',original_hashes_verified=True)
