using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;
using System.Web.Script.Serialization;

// Read-only sampling. Raw field names are retained where semantics are uncertain.
public static class CaptureEncounter {
 const long ImageBase=0x140000000, BridgeEntry=0x14a5ea740;
 const string ExpectedExe="b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92";
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadProcessMemory(IntPtr h,IntPtr p,byte[] b,IntPtr count,out IntPtr read);
 static IntPtr handle; static long image;
 static byte[] Read(long p,int count) {
  if(p<=0 || count<0 || count>65536)throw new Exception("Invalid read range");
  byte[] b=new byte[count]; IntPtr n;
  if(!ReadProcessMemory(handle,new IntPtr(p),b,new IntPtr(count),out n)||n.ToInt64()!=count)
   throw new Exception("Unreadable 0x"+p.ToString("x")+" Win32="+Marshal.GetLastWin32Error());
  return b;
 }
 static long Ptr(long p) {return BitConverter.ToInt64(Read(p,8),0);}
 static uint U32(long p) {return BitConverter.ToUInt32(Read(p,4),0);}
 static ushort U16(long p) {return BitConverter.ToUInt16(Read(p,2),0);}
 static long VA(long a) {return image+a-ImageBase;}
 static string Hex(long a) {return "0x"+a.ToString("x");}
 static Dictionary<string,object> Obj(params object[] values) {
  var r=new Dictionary<string,object>();for(int i=0;i<values.Length;i+=2)r.Add((string)values[i],values[i+1]);return r;
 }
 static object Try(Func<object> f) {try{return f();}catch(Exception e){return Obj("read_error",e.Message);}}
 static object CommonPools() {
  long common=Ptr(VA(0x14154c0a8));var pools=new List<object>();
  if(common==0)return Obj("common",Hex(common),"pools",pools);
  int[] offsets={0x318,0x2f8,0x308,0x320};int[] types={31,40,41,42};
  for(int k=0;k<4;k++) {int index=k;pools.Add(Try(delegate {
   long p=Ptr(common+offsets[index]);if(p==0)return Obj("type",types[index],"pool",Hex(p));
   int count=U16(p+0x78);long table=Ptr(p+0x88);var actors=new List<object>();
   if(count>64)throw new Exception("Pool count exceeds reviewed bound: "+count);
   for(int j=0;j<count;j++) {int aindex=j;actors.Add(Try(delegate {
    long a=Ptr(table+aindex*8);if(a==0)return Obj("index",aindex,"actor",Hex(a));
    return Obj("index",aindex,"actor",Hex(a),"raw_bec",unchecked((int)U32(a+0xbec)),
      "raw_id_08",U32(a+8),"hp_c20",U32(a+0xc20),"max_hp_c24",U32(a+0xc24),
      "raw_state_12a4",U32(a+0x12a4),"birth_pointer_13c0",Hex(Ptr(a+0x13c0)));
   }));}
   return Obj("type",types[index],"pool",Hex(p),"count",count,"actors",actors);
  }));}
  return Obj("common",Hex(common),"raw_generation_08",U32(common+8),"pools",pools);
 }
 static object Bridge() {
  long entry=VA(BridgeEntry);byte[] redirect=Read(entry,5);
  if(redirect[0]!=0xe9)return Obj("hook_present",false,"entry_bytes",BitConverter.ToString(redirect));
  long cave=entry+5+BitConverter.ToInt32(redirect,1);long config=cave+0x4000;
  // Match the known wrapper prefix before interpreting its private layout.
  byte[] header=Read(cave,8);byte[] expected={0x9c,0x50,0x51,0x52,0x41,0x50,0x41,0x51};
  bool known=true;for(int i=0;i<8;i++)if(header[i]!=expected[i])known=false;
  if(!known) {
   byte[] gate=Read(cave,12);
   if(gate[0]!=0x9c||gate[1]!=0x50||gate[2]!=0x48||gate[3]!=0xb8||BitConverter.ToInt64(gate,4)!=VA(0x141535830))
    throw new Exception("Unknown bridge redirect; private layout not read");
  }
  uint used=U32(config+0x1c),capacity=U32(config+0x20);long slots=Ptr(config+0x30);
  if(used>capacity||capacity>2048)throw new Exception("Invalid bridge storage bounds");
  var rows=new List<object>();
  for(int i=0;i<used;i++) {long slot=slots+i*256;rows.Add(Try(delegate {
   long source=Ptr(slot),manager=Ptr(slot+8),birth=slot+0x20,actor=Ptr(birth+0x68);
   return Obj("source",Hex(source),"manager",Hex(manager),"common_generation",U32(slot+0x10),
    "manager_id",U32(slot+0x14),"bridge_status",U32(slot+0x18),"occurrence",U32(slot+0x1c),
    "replacement_alive_byte",Read(slot+0xe0,1)[0],"replacement_type",Read(birth+0x95,1)[0],
    "actor",Hex(actor),"source_state",Try(delegate{return U16(source);}),
    "source_flags_30",Try(delegate{return U16(source+0x30);}),
    "source_actor_id_56",Try(delegate{return U16(source+0x56);}),
    "manager_remaining_98",Try(delegate{return U16(manager+0x98);}),
    "source_matrix_7c0_hex",Try(delegate{return BitConverter.ToString(Read(source+0x7c0,64));}),
    "birth_matrix_10_hex",BitConverter.ToString(Read(birth+0x10,64)),
    "actor_raw_bec",Try(delegate{return unchecked((int)U32(actor+0xbec));}),
    "actor_hp_c20",Try(delegate{return U32(actor+0xc20);}));
  }));}
  return Obj("hook_present",true,"cave",Hex(cave),"seed",U32(config+0x18),"used",used,
   "capacity",capacity,"spawned",U32(config+0x24),"retired",U32(config+0x28),
   "exhausted",U32(config+0x2c),"slots",rows);
 }
 static string Hash(string p) {using(var f=File.OpenRead(p))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant();}
 static int Main(string[] args) {
  try {
   if(args.Length>0&&args[0]=="--self-test") {
    handle=OpenProcess(0x410,false,Process.GetCurrentProcess().Id);if(handle==IntPtr.Zero)throw new Exception("Open self failed");
    IntPtr memory=Marshal.AllocHGlobal(64);
    try {Marshal.WriteInt32(memory,123456);if(U32(memory.ToInt64())!=123456)throw new Exception("Read self failed");
     var j=new JavaScriptSerializer();string text=j.Serialize(Obj("read_only",true,"sample",123456));
     if(!text.Contains("123456"))throw new Exception("JSON failed");
     Console.WriteLine("PASS read-only self-process sampling and JSON; no game opened.");
    } finally {Marshal.FreeHGlobal(memory);CloseHandle(handle);}return 0;
   }
   var games=Process.GetProcessesByName("Zoe2Mars");if(games.Length!=1)throw new Exception("Exactly one ZOE2 process must be running");
   var game=games[0];string exe=game.MainModule.FileName;
   if(Hash(exe)!=ExpectedExe)throw new Exception("Unsupported game executable");
   image=game.MainModule.BaseAddress.ToInt64();handle=OpenProcess(0x410,false,game.Id);
   if(handle==IntPtr.Zero)throw new Exception("Read-only game access failed, Win32="+Marshal.GetLastWin32Error());
   string folder=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"captures",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fff"));Directory.CreateDirectory(folder);
   var serializer=new JavaScriptSerializer();serializer.MaxJsonLength=8*1024*1024;
   bool watch=args.Length>0&&args[0]=="--watch";
   Console.WriteLine("Read-only encounter recording: "+folder+(watch?" (up to six hours; close this window to stop)":" (ten samples)"));
   string lastStage="";int samples=watch?21600:10;
   try {for(int i=0;i<samples;i++) {
    game.Refresh();if(game.HasExited)break;
    var snapshot=Obj("utc",DateTime.UtcNow.ToString("o"),"pid",game.Id,"image",Hex(image),"exe_sha256",ExpectedExe,
      "difficulty","not inferred; record in test notes","current_stage",Try(delegate{return System.Text.Encoding.ASCII.GetString(Read(VA(0x141535830),16)).Split((char)0)[0];}),"stage_global_hex",Try(delegate{return BitConverter.ToString(Read(VA(0x141542700),64));}),
      "registry_count",Try(delegate{return U16(VA(0x14153f4e4));}),
      "registry_tail_hex",Try(delegate{return BitConverter.ToString(Read(VA(0x1415404f0)+264*32,256));}),
      "common",Try(CommonPools),"spider_bridge",Try(Bridge),
      "interpretation","Snapshots are sampled while the process runs and may span an update; raw fields do not prove targetability or cause.");
    string json=serializer.Serialize(snapshot);
    File.WriteAllText(Path.Combine(folder,watch?"recent-"+(i%30).ToString("00")+".json":i.ToString("00")+".json"),json);
    string current=serializer.Serialize(snapshot["current_stage"]);
    if(watch&&current!=lastStage) {
     File.AppendAllText(Path.Combine(folder,"stage-observations.jsonl"),serializer.Serialize(Obj("utc",DateTime.UtcNow.ToString("o"),"from",lastStage,"to",current,"interpretation","Observed stage value only; does not prove a victory callback or stage-clear success."))+Environment.NewLine);
     File.WriteAllText(Path.Combine(folder,"stage-"+i.ToString("00000")+".json"),json);lastStage=current;
    }
    if(i<samples-1)Thread.Sleep(1000);
   }}finally{CloseHandle(handle);}
   Console.WriteLine("Saved read-only encounter samples: "+folder);return 0;
  } catch(Exception e) {Console.Error.WriteLine(e.Message);return 1;}
 }
}

