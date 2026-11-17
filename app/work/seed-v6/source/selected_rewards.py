import portable_paths as _portable
"""Generate a Metatron helper whose pool matches the selected story rewards."""
import json,subprocess
from pathlib import Path
from archive_tools import L
CSC=_portable.compiler()
def configure(package,pool):
 p=Path(package);runtime=p/'runtime';pool=list(pool)
 # An empty selected pool uses chance=0 and a harmless compile-time singleton;
 # native healing and the saved pickup counter still follow the original path.
 effective=pool or [1]
 emitter=(L/'MetatronRewardCode.cs').read_text()
 assert emitter.count('Pool={1,2,3,4,6,7,8,9,10,11,12}')==1
 emitter=emitter.replace('Pool={1,2,3,4,6,7,8,9,10,11,12}','Pool={'+','.join(map(str,effective))+'}')
 emitter=emitter.replace('Imm(b,11)','Imm(b,(uint)Pool.Length)').replace('0x83,0xf8,11','0x83,0xf8,(byte)Pool.Length')
 emitter=emitter.replace('%11','%Pool.Length').replace('n<11','n<Pool.Length')
 source=(L/'SeededMetatronAdapter.cs').read_text()
 if not pool:source=source.replace('Chance=Int32.Parse(chance);','Chance=0;')
 (runtime/'MetatronRewardCode.cs').write_text(emitter)
 (runtime/'SeededMetatronAdapter.cs').write_text(source)
 subprocess.run([CSC,'/nologo','/platform:x64','/optimize+','/out:'+str(runtime/'SeededMetatronAdapter.exe'),str(runtime/'SeededMetatronAdapter.cs'),str(runtime/'MetatronRewardCode.cs')],check=True)
 (runtime/'selected-reward-pool.json').write_text(json.dumps(dict(pool=pool,vector_cannon_protected=True,empty_pool_chance=0),indent=2)+'\n')

