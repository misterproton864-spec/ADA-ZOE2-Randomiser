"""Add read-only Aumaan combat observations to the stuck encounter report."""


def augment(source):
    main = ' static int Main(string[] args) {'
    snapshot = '      "registry_count",'
    method = ''' static object AumaanRuntime() {
  long entry=VA(0x1404f4c90);
  byte[] redirect=Read(entry,5);
  if(redirect[0]!=0xe9)return Obj("status","not attached");
  long cave=entry+5+BitConverter.ToInt32(redirect,1);
  if(cave<image+0x20000000||cave>image+0x60000000)return Obj("status","native update");
  byte[] config=Read(cave+0x8000,288);
  if(BitConverter.ToInt64(config,16)!=VA(0x140d80330)||BitConverter.ToInt64(config,40)!=VA(0x14016d6d0))
   return Obj("status","different helper");
  return Obj("status","attached","variant","Aumaan Anubis",
    "last_arena",System.Text.Encoding.ASCII.GetString(config,64,8).Split((char)0)[0],
    "spawns",BitConverter.ToUInt32(config,48),"heal_entries_blocked",BitConverter.ToUInt32(config,52),
    "shared_motion_entries_blocked",BitConverter.ToUInt32(config,88),"last_blocked_state",BitConverter.ToUInt32(config,92),
    "returns_to_player",BitConverter.ToUInt32(config,56),"blocked_return_destinations",BitConverter.ToUInt32(config,60),
    "actor_id",BitConverter.ToUInt32(config,72),"state",BitConverter.ToUInt32(config,76),
    "pending_state",BitConverter.ToUInt32(config,80),"motion",BitConverter.ToUInt32(config,84));
 }
'''
    if source.count(main) != 1 or source.count(snapshot) != 1:
        raise ValueError('Aumaan capture recorder boundaries changed')
    return source.replace(main, method+main).replace(snapshot, '      "aumaan_runtime",Try(AumaanRuntime),\n'+snapshot)
