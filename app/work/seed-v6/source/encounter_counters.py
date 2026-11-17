import portable_paths as _portable
"""Read-only native lifecycle fields; raw counts are not gameplay certification."""
FIELDS = r'''
 static object EnemyGroupsAt(long table,int count) {
  if(count<0||count>1024)throw new Exception("ENE count exceeds reviewed bound");
  var rows=new List<object>();
  for(int i=0;i<count;i++) {int index=i;rows.Add(Try(delegate {
   long r=table+index*112;var slots=new List<object>();
   for(int j=0;j<4;j++) {byte[] b=Read(r+48+j*8,8);slots.Add(Obj("type",b[0],"authored_count",b[1],"level",b[2],"raw_live_count_04",b[4],"raw_hex",BitConverter.ToString(b)));}
   return Obj("index",index,"group",Hex(U32(r+88)),"raw_group_remaining_60",U32(r+96),"raw_event_52",U16(r+82),"slots",slots);
  }));}return rows;
 }
 static object BirthsAt(long table,int count) {
  if(count<0||count>4096)throw new Exception("Birth count exceeds reviewed bound");
  var rows=new List<object>();
  for(int i=0;i<count;i++) {int index=i;rows.Add(Try(delegate {
   long b=table+index*160;long actor=Ptr(b+0x68);
   return Obj("index",index,"group",Hex(U32(b)),"type",Read(b+0x95,1)[0],"level",Read(b+0x94,1)[0],
    "flags_60",U16(b+0x60),"flags_62",U16(b+0x62),"actor",Hex(actor),
    "alive_counter",Hex(Ptr(b+0x70)),"group_counter",Hex(Ptr(b+0x78)),
    "alive_counter_value",Try(delegate{return Read(Ptr(b+0x70),1)[0];}),
    "group_counter_value",Try(delegate{return U32(Ptr(b+0x78));}));
  }));}return rows;
 }
 static object SwarmAt(long pool) {
  if(pool==0)return Obj("pool",Hex(pool));
  int count=Read(pool+0x90,1)[0];long table=Ptr(pool+0x98);var rows=new List<object>();
  for(int i=0;i<count;i++) {int index=i;rows.Add(Try(delegate {
   long t=table+index*32;long r=Ptr(t);long s=Ptr(t+8);
   return Obj("index",index,"record",Hex(r),"slot",Hex(s),"group",Hex(U32(r+88)),
    "initial_budget",U16(t+20),"remaining_budget",U16(t+22),"raw_live_18",Read(t+24,1)[0],
    "raw_live_19",Read(t+25,1)[0],"raw_live_1a",Read(t+26,1)[0],"flags_1b",Read(t+27,1)[0],
    "slot_count",Read(s+1,1)[0],"slot_raw_live_04",Read(s+4,1)[0]);
  }));}return Obj("pool",Hex(pool),"tracking_count",count,"tracking",rows);
 }
 static object NativeSpidersAt(long first,long mission) {
  var rows=new List<object>();var seen=new HashSet<long>();long current=first;
  while(current!=0) {
   if(rows.Count>=256||!seen.Add(current))return Obj("records",rows,"truncated_or_cycle",true);
   long s=current;rows.Add(Try(delegate {
    long manager=Ptr(s+0x38);long render=Ptr(s+0xa20);
    return Obj("record",Hex(s),"state",U16(s),"identity",U16(s+0x56),"manager",Hex(manager),
     "manager_remaining_98",Try(delegate{return U16(manager+0x98);}),
     "manager_capacity_9a",Try(delegate{return U16(manager+0x9a);}),
     "manager_script_mode_84",Try(delegate{return U32(manager+0x84);}),
     "hp_raw_50",U16(s+0x50),"mandatory_render",Hex(render),
     "render_flags_ea",Try(delegate{return U16(render+0xea);}));
   }));current=Ptr(s+0x48);
  }
  var groups=new List<object>();
  if(mission!=0)for(int i=0;i<3;i++) {int index=i;groups.Add(Try(delegate {
   long g=mission+index*0x180;
   return Obj("index",index,"active",Read(g+0x5a6,1)[0],"capacity",Read(g+0x5a7,1)[0],"pending",Read(g+0x5a8,1)[0]);
  }));}
  return Obj("records",rows,"mission",Hex(mission),"mission_remaining_94",Try(delegate{return U32(mission+0x94);}),
   "mission_pending_98",Try(delegate{return U32(mission+0x98);}),"mission_groups",groups);
 }
 static object SpiderManagersAt(long first,long sentinel,long vtable) {
  var managers=new List<object>();var seen=new HashSet<long>();long current=first;
  while(current!=0&&current!=sentinel) {
   if(seen.Count>=4096||!seen.Add(current))return Obj("managers",managers,"truncated_or_cycle",true);
   byte[] header=Read(current,40);long obj=current;current=BitConverter.ToInt64(header,24);
   if(BitConverter.ToInt64(header,0)!=vtable)continue;
   managers.Add(Try(delegate {
    long table=Ptr(obj+0x90);int count=U16(obj+0x9a);
    if(count>64)throw new Exception("Spider pool capacity exceeds reviewed bound");
    var actors=new List<object>();
    for(int i=0;i<count;i++) {long s=table+i*0x1270;actors.Add(Try(delegate {
     long render=Ptr(s+0xa20);
     return Obj("record",Hex(s),"state",U16(s),"hp_raw_50",U16(s+0x50),"identity",U16(s+0x56),
       "render",Hex(render),"render_flags",Try(delegate{return U16(render+0xea);}));
    }));}
    return Obj("manager",Hex(obj),"identity",U32(obj+0x7c),"mode",U32(obj+0x84),"remaining",U16(obj+0x98),
     "capacity",count,"completion_callback",Hex(U32(obj+0x9c)),"actors",actors);
   }));
  }return Obj("managers",managers,"visited_objects",seen.Count);
 }
 static object ViperState() {
  var rows=new List<object>();var seen=new HashSet<long>();long end=VA(0x1433fe270)+4*0xf8;
  long current=Ptr(VA(0x1433fe300)+4*0xf8);long player=Ptr(VA(0x14156d710));
  while(current!=0&&current!=end&&seen.Count<4096&&seen.Add(current)) {
   long a=current;byte[] header=Read(a,40);current=BitConverter.ToInt64(header,24);
   if(BitConverter.ToInt64(header,0)!=VA(0x140d8a0c8))continue;
   rows.Add(Try(delegate {
    float x=BitConverter.ToSingle(Read(a+0x980,4),0),y=BitConverter.ToSingle(Read(a+0x984,4),0),z=BitConverter.ToSingle(Read(a+0x988,4),0);
    double dx=player==0?0:x-BitConverter.ToSingle(Read(player+0x980,4),0),dy=player==0?0:y-BitConverter.ToSingle(Read(player+0x984,4),0),dz=player==0?0:z-BitConverter.ToSingle(Read(player+0x988,4),0);
    return Obj("actor",Hex(a),"script_id",Hex(U32(a+0x78)),"hp",U32(a+0xc20),"maximum_hp",U32(a+0xc24),
     "state",U32(a+0x12a0),"next_state",U32(a+0x12a4),"ai",Hex(Ptr(a+0x1658)),"mode_flags_15d4",Hex(U32(a+0x15d4)),
     "aircraft",(U32(a+0xbe8)&4)!=0,"completion_callback",U32(a+0x164c),"completion_latch",U32(a+0x1430),
     "position",new float[]{x,y,z},"distance_from_player",Math.Sqrt(dx*dx+dy*dy+dz*dz));
   }));
  }return Obj("actors",rows,"visited",seen.Count,"read_only",true);
 }
 static object NativeCounters() {
  long common=Ptr(VA(0x14154c0a8));
  return Obj("enemy_groups",Try(delegate{return EnemyGroupsAt(Ptr(VA(0x14154c098)),U16(VA(0x14154c094)));}),
   "births",Try(delegate{return common==0?null:BirthsAt(Ptr(common+0x368),U16(common+0x360));}),
   "swarm",Try(delegate{return common==0?null:SwarmAt(Ptr(common+0x2f0));}),
   "native_spiders",Try(delegate{return NativeSpidersAt(Ptr(VA(0x14156f798)),Ptr(VA(0x14154c510)));}),
   "ordinary_spider_managers",Try(delegate{return SpiderManagersAt(Ptr(VA(0x1433fe300)+4*0xf8),VA(0x1433fe270)+4*0xf8,VA(0x140d8d9f8));}),
   "vic_viper",Try(ViperState),"read_only",true,"interpretation","Raw lifecycle fields only. Do not force completion or equate a zero sampled count with a verified room clear.");
 }
 static void CounterSelfTest() {
  IntPtr allocation=Marshal.AllocHGlobal(0x5000);long p=allocation.ToInt64();
  try {
   Marshal.Copy(new byte[0x5000],0,allocation,0x5000);
   Marshal.WriteInt32(new IntPtr(p+88),123);Marshal.WriteInt32(new IntPtr(p+96),3);
   Marshal.WriteByte(new IntPtr(p+48),32);Marshal.WriteByte(new IntPtr(p+49),3);
   Marshal.WriteInt64(new IntPtr(p+0x1000+0x98),p+0x1200);Marshal.WriteByte(new IntPtr(p+0x1000+0x90),1);
   Marshal.WriteInt64(new IntPtr(p+0x1200),p);Marshal.WriteInt64(new IntPtr(p+0x1208),p+48);
   Marshal.WriteInt16(new IntPtr(p+0x1214),18);Marshal.WriteInt16(new IntPtr(p+0x1216),6);
   Marshal.WriteInt64(new IntPtr(p+0x2000+0x38),p+0x3400);Marshal.WriteInt16(new IntPtr(p+0x2000),15);
   Marshal.WriteInt16(new IntPtr(p+0x3400+0x98),2);Marshal.WriteInt16(new IntPtr(p+0x3400+0x9a),28);
   Marshal.WriteInt32(new IntPtr(p+0x4000+0x94),2);
   var j=new JavaScriptSerializer();
   string text=j.Serialize(Obj("enemy",EnemyGroupsAt(p,1),"births",BirthsAt(p+0x1800,1),
     "swarm",SwarmAt(p+0x1000),"spiders",NativeSpidersAt(p+0x2000,p+0x4000)));
   if(!text.Contains("\"remaining_budget\":6")||!text.Contains("\"mission_remaining_94\":2")||!text.Contains("\"raw_group_remaining_60\":3"))throw new Exception("Counter fixture values differ");
   foreach(int n in new int[]{-1,1025}) {bool rejected=false;try{EnemyGroupsAt(p,n);}catch{rejected=true;}if(!rejected)throw new Exception("Counter bounds not enforced");}
   Marshal.WriteInt64(new IntPtr(p+0x2000+0x48),p+0x2000);
   if(!j.Serialize(NativeSpidersAt(p+0x2000,0)).Contains("\"truncated_or_cycle\":true"))throw new Exception("Spider cycle guard failed");
   Marshal.WriteInt64(new IntPtr(p+0x3400),0x12345678);Marshal.WriteInt64(new IntPtr(p+0x3400+0x90),p+0x800);
   Marshal.WriteInt16(new IntPtr(p+0x3400+0x9a),1);
   if(!j.Serialize(SpiderManagersAt(p+0x3400,0,0x12345678)).Contains("\"remaining\":2"))throw new Exception("Ordinary Spider manager fixture failed");
   Console.WriteLine("PASS read-only ENE, birth, swarm and native Spider counter fixtures; no game opened.");
  } finally {Marshal.FreeHGlobal(allocation);}
 }
'''

def augment(source):
 marker=' static string Hash(string p)'
 if source.count(marker)!=1:raise ValueError('Recorder method boundary changed')
 source=source.replace(marker,FIELDS+'\n'+marker)
 old='int[] offsets={0x318,0x2f8,0x308,0x320};int[] types={31,40,41,42};'
 if source.count(old)!=1:raise ValueError('Recorder normal pool layout changed')
 source=source.replace(old,'int[] offsets={0x318,0x300,0x2f8,0x308,0x310,0x320};int[] types={31,32,40,41,43,42};').replace('for(int k=0;k<4;k++)','for(int k=0;k<6;k++)')
 marker='      "common",Try(CommonPools),"spider_bridge",Try(Bridge),'
 if source.count(marker)!=1:raise ValueError('Recorder snapshot boundary changed')
 source=source.replace(marker,marker+'\n      "native_counters",Try(NativeCounters),')
 marker='     Console.WriteLine("PASS read-only self-process sampling and JSON; no game opened.");'
 if source.count(marker)!=1:raise ValueError('Recorder self-test boundary changed')
 return source.replace(marker,'     CounterSelfTest();\n'+marker)
