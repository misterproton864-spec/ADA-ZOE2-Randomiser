"""Add bounded read-only Inhert observations to the encounter recorder."""

def augment(source):
 main=' static int Main(string[] args) {'
 field='      "registry_count",'
 selftest='     CounterSelfTest();'
 if any(source.count(x)!=1 for x in (main,field,selftest)):
  raise ValueError('Capture recorder boundaries changed')
 method=r'''
 static float[] FiniteVec3(long address) {
  byte[] raw=Read(address,12);float[] v={BitConverter.ToSingle(raw,0),BitConverter.ToSingle(raw,4),BitConverter.ToSingle(raw,8)};
  foreach(float f in v)if(float.IsNaN(f)||float.IsInfinity(f))throw new Exception("Nonfinite actor vector");
  return v;
 }
 static object InhertActorsAt(long current,long sentinel,long vtable) {
  var actors=new List<object>();var seen=new HashSet<long>();
  while(current!=0&&current!=sentinel&&seen.Count<4096&&seen.Add(current)) {
   long a=current;byte[] header=Read(a,40);current=BitConverter.ToInt64(header,24);
   if(BitConverter.ToInt64(header,0)!=vtable)continue;
   actors.Add(Try(delegate{return Obj("actor",Hex(a),"serial",U32(a+8),"actor_id",Hex(U32(a+0x78)),
    "hp",U32(a+0xc20),"max_hp",U32(a+0xc24),"native_variant",U32(a+0x14e4),
    "state",U32(a+0x12a0),"next_state",U32(a+0x12a4),"motion",Read(a+0x99,1)[0],
    "native_flags_14e0",Hex(U32(a+0x14e0)),"control_flags_bec",Hex(U32(a+0xbec)),
    "body_flags_1bc",Hex(U32(a+0x1bc)),"body_raw_150",BitConverter.ToString(Read(a+0x150,0x80)),
    "model_flags_ea",Try(delegate{long model=Ptr(a+0x80);return model==0?null:(object)Hex(U16(model+0xea));}),
    "ai_script_step",Read(a+0x1d25,1)[0],"ai_script_timer",U32(a+0x1d28),
    "position",FiniteVec3(a+0x980),"movement_min",FiniteVec3(a+0x14b0),
    "movement_max",FiniteVec3(a+0x14c0),"movement_centre",FiniteVec3(a+0x14d0),
    "previous_transform_position",FiniteVec3(a+0x14a0),
    "completion_callback",U32(a+0x14f0));}));
  }
  return Obj("actors",actors,"visited",seen.Count,"cycle_or_limit",current!=0&&current!=sentinel,"read_only",true);
 }
 static object InhertActors() {
  return InhertActorsAt(Ptr(VA(0x1433fe300)+4*0xf8),VA(0x1433fe270)+4*0xf8,VA(0x140d754c8));
 }
 static void InhertSelfTest() {
  IntPtr memory=Marshal.AllocHGlobal(0x2000);long a=memory.ToInt64();
  try {
   Marshal.Copy(new byte[0x2000],0,memory,0x2000);Marshal.WriteInt64(memory,1234);Marshal.WriteInt32(new IntPtr(a+0x78),5678);
   Marshal.WriteInt32(new IntPtr(a+0xc20),100);Marshal.WriteInt32(new IntPtr(a+0xc24),200);Marshal.WriteInt32(new IntPtr(a+0x14e4),1);
   string json=new JavaScriptSerializer().Serialize(InhertActorsAt(a,0,1234));
   if(!json.Contains("5678") && !json.Contains("0x162e"))throw new Exception("Inhert actor identity missing");
   if(!json.Contains("\"native_variant\":1")||!json.Contains("\"max_hp\":200"))throw new Exception("Inhert fields missing");
   if(!json.Contains("\"native_flags_14e0\"")||!json.Contains("\"body_raw_150\"")||!json.Contains("\"previous_transform_position\""))throw new Exception("Inhert collision observations missing");
   string other=new JavaScriptSerializer().Serialize(InhertActorsAt(a,0,4321));
   if(!other.Contains("\"actors\":[]"))throw new Exception("Wrong actor vtable accepted");
  } finally {Marshal.FreeHGlobal(memory);}
 }
'''
 return source.replace(main,method+main).replace(field,'      "inhert_actors",Try(InhertActors),\n'+field).replace(selftest,selftest+'\n     InhertSelfTest();')
