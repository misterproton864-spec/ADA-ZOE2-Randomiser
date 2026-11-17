import portable_paths as _portable
"""Feed the verified original archive to the reused music compiler after reinstall."""
from pathlib import Path

def pinned_music_input(text,original_stage):
    old="archive=Archive(GAME/'ZOE2/STAGE.DAT.zoe2-ca01-loader-v1.bak')"
    if text.count(old)!=1:raise ValueError('Cannot identify the music compiler original-input boundary')
    from music_selection import patch_compiler
    return patch_compiler(text.replace(old,'archive=Archive(Path('+repr(str(Path(original_stage)))+'))',1))
