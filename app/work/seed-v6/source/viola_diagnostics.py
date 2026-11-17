import portable_paths as _portable
"""Read-only deletion observations. Sampled warnings never force progression."""
import json

def augment(source,seed):
 marker=' static int Main(string[] args) {'
 methods=r'''
 static string violaStage="";
 static Dictionary<string,string> violaStates=new Dictionary<string,string>();
 static Dictionary<string,int> violaFailures=new Dictionary<string,int>();
 static List<object> violaEvents=new List<object>();
 static string ViolaFailure(uint variant,uint hp,uint remaining,uint success,long handler,long expected,uint playerType) {
  if(variant!=1||hp==0)return "";
  if(playerType>12&&handler!=expected)return "missing_player_grab_handler";
  if(remaining==0&&success!=0)return "ai_counter_zero_without_success_dispatch";
  return "";
 }
 static object ViolaState() {
  string stage=System.Text.Encoding.ASCII.GetString(Read(VA(0x141535830),16)).Split((char)0)[0];
  if(stage!=violaStage){violaStates.Clear();violaFailures.Clear();violaStage=stage;}
  long player=Ptr(VA(0x14156d710));long handler=0;uint playerType=0;
  if(player!=0){playerType=U32(player+0xc08);long table=Ptr(player+0xc00);if(table!=0)handler=Ptr(table+0x6c0);}
  var actors=new List<object>();var failures=new List<object>();var seen=new HashSet<long>();
  long end=VA(0x1433fe270)+4*0xf8,current=Ptr(VA(0x1433fe300)+4*0xf8);
  while(current!=0&&current!=end&&seen.Count<4096&&seen.Add(current)) {
   long a=current;byte[] header=Read(a,40);current=BitConverter.ToInt64(header,24);
   if(BitConverter.ToInt64(header,0)!=VA(0x140d732e8)||Read(a+0x1470,1)[0]!=1)continue;
   uint hp=U32(a+0xc20),remaining=U32(a+0x16b8),success=U32(a+0x1480),state=U32(a+0x12a0),next=U32(a+0x12a4);
   string key=Hex(a)+":"+U32(a+8),failure=ViolaFailure(1,hp,remaining,success,handler,VA(0x1406e9df0),playerType);
   var row=Obj("actor",Hex(a),"serial",U32(a+8),"actor_id",Hex(U32(a+0x78)),"boss_variant","Viola AI (full rescue fight)",
    "state",state,"next_state",next,"animation",Read(a+0x99,1)[0],"hp",hp,"ai_remaining",remaining,
    "success_callback",success,"recovery_callback",U32(a+0x1484),"failure_callback",U32(a+0x1488),
    "native_state_block_hex",BitConverter.ToString(Read(a+0x12a0,64)));
   actors.Add(row);
   string signature=state+":"+next+":"+Read(a+0x99,1)[0]+":"+success+":"+U32(a+0x1484)+":"+(remaining==0);
   string previous;
   if(!violaStates.TryGetValue(key,out previous)||previous!=signature){
    violaEvents.Add(Obj("utc",DateTime.UtcNow.ToString("o"),"seed",VIOLA_SEED,"arena",stage,"boss_variant","Viola AI (full rescue fight)","event","sampled_state_transition","previous",previous,"actor_state",row));violaStates[key]=signature;
   }
   string fkey=key+":"+failure;int count=0;
   if(failure!=""){
    violaFailures.Remove(key+":"+(failure=="missing_player_grab_handler"?"ai_counter_zero_without_success_dispatch":"missing_player_grab_handler"));
    violaFailures.TryGetValue(fkey,out count);violaFailures[fkey]=++count;
    if(count>=5)failures.Add(Obj("code",failure,"consecutive_samples",count,"actor",Hex(a),"suspected",true));
    if(count==5)violaEvents.Add(Obj("utc",DateTime.UtcNow.ToString("o"),"seed",VIOLA_SEED,"arena",stage,"boss_variant","Viola AI (full rescue fight)","event","suspected_missing_event","code",failure,"actor_state",row));
   } else {violaFailures.Remove(key+":missing_player_grab_handler");violaFailures.Remove(key+":ai_counter_zero_without_success_dispatch");}
  }
  return Obj("arena",stage,"actors",actors,"player_grab_handler",Hex(handler),"expected_grab_handler",Hex(VA(0x1406e9df0)),
   "native_grab_count",U32(VA(0x141547724)),"ai_enabled",Read(VA(0x14154772d),1)[0],"recovery_enabled",Read(VA(0x14154772c),1)[0],
   "deletion_input",U32(VA(0x143606e68)),"hold_damage_input",U32(VA(0x143606e6c)),
   "player",player==0?null:Obj("state",U32(player+0x12a0),"next_state",U32(player+0x12a4),"pending_custom_state",U32(player+0x12d4),"custom_state_table",Hex(Ptr(player+0x12d8)),"hold_target",Hex(Ptr(player+0x1280)),"hold_phase",U32(player+0x18b0),"animation",Read(player+0x99,1)[0]),
   "missing_event_failures",failures,"sampling","One-second observations can miss transient states; warnings are diagnostic, not confirmed causes.");
 }
 static void DrainViolaEvents(string folder) {
  if(violaEvents.Count==0)return;var serializer=new JavaScriptSerializer();
  foreach(object row in violaEvents)File.AppendAllText(Path.Combine(folder,"viola-deletion-events.jsonl"),serializer.Serialize(row)+Environment.NewLine);
  violaEvents.Clear();
 }
 static void ViolaSelfTest() {
  if(ViolaFailure(1,1000,100,1,0,123,13)!="missing_player_grab_handler")throw new Exception("Viola missing-handler diagnostic failed");
  if(ViolaFailure(1,1000,0,1,123,123,13)!="ai_counter_zero_without_success_dispatch")throw new Exception("Viola missing-success diagnostic failed");
  if(ViolaFailure(1,1000,100,1,123,123,13)!=""||ViolaFailure(1,0,0,1,0,123,13)!=""||ViolaFailure(0,1000,100,1,0,123,13)!="")throw new Exception("Viola diagnostic scope failed");
 }
'''.replace('VIOLA_SEED',json.dumps(str(seed)))
 if source.count(marker)!=1:raise ValueError('Capture main boundary changed')
 source=source.replace(marker,methods+marker)
 marker='      "registry_count",'
 if source.count(marker)!=1:raise ValueError('Capture snapshot boundary changed')
 source=source.replace(marker,'      "viola_deletion",Try(ViolaState),\n'+marker)
 source=source.replace('string json=serializer.Serialize(snapshot);','string json=serializer.Serialize(snapshot);\n    DrainViolaEvents(folder);')
 marker='Console.WriteLine("PASS read-only self-process sampling and JSON; no game opened.");'
 if source.count(marker)!=1:raise ValueError('Capture self-test boundary changed')
 return source.replace(marker,'ViolaSelfTest();'+marker)
