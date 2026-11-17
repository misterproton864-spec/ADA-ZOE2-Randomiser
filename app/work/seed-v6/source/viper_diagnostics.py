import portable_paths as _portable
"""Add read-only observations of the installed Viper controller to captures."""
def augment(source):
 marker=' static int Main(string[] args) {'
 method=''' static object ViperRuntime() {
  byte[] redirect=Read(VA(0x140772d10),5);
  if(redirect[0]!=0xe9)return Obj("status","not attached");
  long cave=VA(0x140772d10)+5+BitConverter.ToInt32(redirect,1);
  if(cave<image+0x20000000||cave>image+0x60000000)return Obj("status","native update");
  byte[] config=Read(cave+0x8000,3656);
  if(BitConverter.ToUInt32(config,44)!=0x56495032)return Obj("status","different helper");
  var actors=new List<object>();
  for(int i=0;i<128;i++){int at=72+i*24;long actor=BitConverter.ToInt64(config,at);if(actor==0)continue;
   actors.Add(Obj("actor_id",BitConverter.ToUInt32(config,at+20),"position_hex",BitConverter.ToString(Read(actor+0x980,12)),"physics_hex",BitConverter.ToString(Read(actor+0xb60,12)),"model_position_hex",BitConverter.ToString(Read(Ptr(actor+0x80)+0x70,12)),"serial",BitConverter.ToUInt32(config,at+8),"native_death_seen",BitConverter.ToUInt32(config,at+12)!=0,"native_completion_flag_seen",BitConverter.ToUInt32(config,at+16)!=0));}
  return Obj("status","attached","component","viper-combat-experimental-7","session_spawns",BitConverter.ToUInt32(config,48),"session_repositions",BitConverter.ToUInt32(config,52),"session_flight_redirects",BitConverter.ToUInt32(config,56),"session_native_completion_flags",BitConverter.ToUInt32(config,60),"current_arena_actors",actors,"interpretation","Native death/completion flags observed; confirm the next encounter or exit separately.");
 }
'''
 if source.count(marker)!=1:raise ValueError('Capture recorder main boundary changed')
 source=source.replace(marker,method+marker)
 marker='      "registry_count",'
 if source.count(marker)!=1:raise ValueError('Capture recorder snapshot boundary changed')
 return source.replace(marker,'      "viper_runtime",Try(ViperRuntime),\n'+marker)
