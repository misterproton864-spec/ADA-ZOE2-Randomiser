using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

// Optional per-seed HP scaler. It never changes Zoe2Mars.exe or game files.
// The game must be at its main menu when Attach starts this monitor.
public static class HealthMultiplierAdapter {
 const long ImageBase=0x140000000;
 const string ExpectedExe="b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92";
 const uint Access=0x100438,WaitTimeout=0x102;
 static readonly HashSet<int> EnemyTypes=new HashSet<int>(new int[]{10,31,32,40,41,42,43});
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadProcessMemory(IntPtr handle,IntPtr address,byte[] buffer,IntPtr length,out IntPtr read);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteProcessMemory(IntPtr handle,IntPtr address,byte[] buffer,IntPtr length,out IntPtr written);
 [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr handle,uint milliseconds);

 sealed class Scaled {
  public uint Serial;
  public int ScaledMax;
  public int BaselineMax;
  public int LastCurrent;
  public int Factor;
  public int DisplayBaselineMax;
  public int DisplayScaledMax;
  public int LastDisplayCurrent;
  public int StaleDisplayPolls;
 }
 sealed class State {
  public readonly Dictionary<long,Scaled> Actors=new Dictionary<long,Scaled>();
  public readonly Dictionary<long,int> LastBossHp=new Dictionary<long,int>();
  public int Changed,Skipped,Failures;
  public string Stage="";
  public string LogPath="";
 }
 sealed class Targets {
  public readonly Dictionary<string,HashSet<uint>> ByStage=new Dictionary<string,HashSet<uint>>(StringComparer.Ordinal);
  public bool Has(string stage,uint id) {
   HashSet<uint> ids;return ByStage.TryGetValue(stage,out ids)&&ids.Contains(id);
  }
  public int Count {
   get {int total=0;foreach(HashSet<uint> ids in ByStage.Values)total+=ids.Count;return total;}
  }
 }
 static byte[] Read(IntPtr handle,long address,int length) {
  byte[] data=new byte[length];IntPtr count;
  if(!ReadProcessMemory(handle,new IntPtr(address),data,new IntPtr(length),out count)||count.ToInt64()!=length)
   throw new InvalidOperationException("ReadProcessMemory failed at "+address.ToString("x"));
  return data;
 }
 static void Write(IntPtr handle,long address,byte[] data) {
  IntPtr count;
  if(!WriteProcessMemory(handle,new IntPtr(address),data,new IntPtr(data.Length),out count)||count.ToInt64()!=data.Length)
   throw new InvalidOperationException("WriteProcessMemory failed at "+address.ToString("x"));
 }
 static long Ptr(IntPtr handle,long address) {return BitConverter.ToInt64(Read(handle,address,8),0);}
 static uint U32(IntPtr handle,long address) {return BitConverter.ToUInt32(Read(handle,address,4),0);}
 static int I32(IntPtr handle,long address) {return BitConverter.ToInt32(Read(handle,address,4),0);}
 static int U16(IntPtr handle,long address) {return BitConverter.ToUInt16(Read(handle,address,2),0);}
 static string Stage(IntPtr handle,long image) {
  byte[] raw=Read(handle,image+(0x141535830-ImageBase),16);
  int length=Array.IndexOf(raw,(byte)0);if(length<0)length=raw.Length;
  string stage=Encoding.ASCII.GetString(raw,0,length);
  if(stage.Length>8)return "";
  foreach(char ch in stage)if(!(char.IsLetterOrDigit(ch)||ch=='_'))return "";
  return stage;
 }
 static Targets LoadTargets(string path) {
  Targets targets=new Targets();int lines=0;
  foreach(string raw in File.ReadAllLines(path,Encoding.UTF8)) {
   if(String.IsNullOrWhiteSpace(raw))continue;
   string[] cells=raw.Split('\t');
   if(cells.Length!=2||cells[0].Length<2||cells[0].Length>8)throw new InvalidOperationException("Invalid health target row");
   foreach(char ch in cells[0])if(!(char.IsLetterOrDigit(ch)||ch=='_'))throw new InvalidOperationException("Invalid target stage");
   uint id=UInt32.Parse(cells[1],CultureInfo.InvariantCulture);
   HashSet<uint> ids;
   if(!targets.ByStage.TryGetValue(cells[0],out ids)){ids=new HashSet<uint>();targets.ByStage.Add(cells[0],ids);}
   if(!ids.Add(id))throw new InvalidOperationException("Duplicate health target");
   if(++lines>1024)throw new InvalidOperationException("Too many health targets");
  }
  return targets;
 }
 static string Sha(string path) {
  using(FileStream stream=File.OpenRead(path))using(SHA256 hash=SHA256.Create())
   return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
 }
 static Process Game(int pid) {
  Process game=Process.GetProcessById(pid);
  if(!String.Equals(game.ProcessName,"Zoe2Mars",StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Wrong process");
  if(Sha(game.MainModule.FileName)!=ExpectedExe)throw new InvalidOperationException("Unsupported ZOE2 executable");
  return game;
 }
 static bool Apply(IntPtr handle,long actor,int factor,State state) {
  if(factor==1||actor==0)return false;
  uint serial=U32(handle,actor+8);
  int maximum=I32(handle,actor+0xc24),current=I32(handle,actor+0xc20);
  if(maximum<=0||maximum>100000||current<=0||current>maximum||maximum>Int32.MaxValue/factor) {
   state.Skipped++;return false;
  }
  Scaled previous;
  if(state.Actors.TryGetValue(actor,out previous)&&previous.Serial==serial&&previous.Factor==factor&&previous.ScaledMax==maximum) {
   if(current==previous.BaselineMax&&previous.LastCurrent<previous.BaselineMax) {
    Write(handle,actor+0xc20,BitConverter.GetBytes(previous.ScaledMax));
    previous.LastCurrent=previous.ScaledMax;
    state.Changed++;
    return true;
   }
   previous.LastCurrent=current;
   return false;
  }
  // A native phase reset changes maximum HP; scale that new baseline once.
  if(I32(handle,actor+0xc24)!=maximum)return false;
  int scaledMaximum=maximum*factor;
  Write(handle,actor+0xc24,BitConverter.GetBytes(scaledMaximum));
  int now=I32(handle,actor+0xc20);
  if(now>0&&now<=maximum)Write(handle,actor+0xc20,BitConverter.GetBytes(now*factor));
  state.Actors[actor]=new Scaled{Serial=serial,ScaledMax=scaledMaximum,BaselineMax=maximum,
   LastCurrent=now>0&&now<=maximum?now*factor:now,Factor=factor};
  state.Changed++;
  return true;
 }
 static bool SyncBossDisplay(IntPtr handle,long actor,int factor,State state) {
  Scaled scaled;
  if(!state.Actors.TryGetValue(actor,out scaled)||scaled.Factor!=factor||
     scaled.Serial!=U32(handle,actor+8)||I32(handle,actor+0xc20)<=0)return false;
  int combat=I32(handle,actor+0xc20);
  int current=U16(handle,actor+0x8c0),maximum=U16(handle,actor+0x8c2);
  if(maximum==scaled.DisplayScaledMax&&maximum>0) {
   if(current==scaled.DisplayBaselineMax&&scaled.LastDisplayCurrent<scaled.DisplayScaledMax&&
      combat==scaled.ScaledMax) {
    Write(handle,actor+0x8c0,BitConverter.GetBytes((ushort)scaled.DisplayScaledMax));
    scaled.LastDisplayCurrent=scaled.DisplayScaledMax;
    scaled.StaleDisplayPolls=0;
    return true;
   }
   // A native update to the display current takes priority. Repair only a
   // value that stays above the combat HP fraction for two monitor polls.
   int expected=(int)(((long)combat*maximum+scaled.ScaledMax/2)/scaled.ScaledMax);
   if(current>expected+1&&current==scaled.LastDisplayCurrent)scaled.StaleDisplayPolls++;
   else scaled.StaleDisplayPolls=0;
   if(scaled.StaleDisplayPolls>=2) {
    Write(handle,actor+0x8c0,BitConverter.GetBytes((ushort)expected));
    scaled.LastDisplayCurrent=expected;scaled.StaleDisplayPolls=0;
    return true;
   }
   scaled.LastDisplayCurrent=current;
   return false;
  }
  // The native boss factory writes these 16-bit display fields separately
  // from the 32-bit combat HP. Keep the display below the signed 16-bit cap
  // and preserve the initial phase fraction when triple combat HP is larger.
  if(maximum<=0||maximum>scaled.BaselineMax||current>maximum||maximum>32767)
   return false;
  int newMaximum=(int)Math.Min((long)maximum*factor,32767L);
  int newCurrent=(int)(((long)current*newMaximum+maximum/2)/maximum);
  Write(handle,actor+0x8c2,BitConverter.GetBytes((ushort)newMaximum));
  Write(handle,actor+0x8c0,BitConverter.GetBytes((ushort)newCurrent));
  scaled.DisplayBaselineMax=maximum;scaled.DisplayScaledMax=newMaximum;
  scaled.LastDisplayCurrent=newCurrent;scaled.StaleDisplayPolls=0;
  return true;
 }
 static HashSet<long> Bosses(IntPtr handle,long image,long player,Targets targets,int factor,State state) {
  HashSet<long> found=new HashSet<long>();
  if(!targets.ByStage.ContainsKey(state.Stage))return found;
  long sentinel=image+(0x1433fe270-ImageBase)+4*0xf8;
  long current=Ptr(handle,image+(0x1433fe300-ImageBase)+4*0xf8);
  HashSet<long> seen=new HashSet<long>();
  while(current!=0&&current!=sentinel&&seen.Count<4096&&seen.Add(current)) {
   long actor=current;
   try {
    current=Ptr(handle,actor+24);
    if(actor==player)continue;
    int type=Read(handle,actor+0x9b,1)[0];
    if(type<9||type>14)continue;
    if(targets.Has(state.Stage,U32(handle,actor+0x78))) {
     found.Add(actor);
     if(factor>1) {
      Apply(handle,actor,factor,state);
      SyncBossDisplay(handle,actor,factor,state);
     }
     int hp=I32(handle,actor+0xc20),prior;
     if(!state.LastBossHp.TryGetValue(actor,out prior)||hp!=prior) {
      state.LastBossHp[actor]=hp;
      if(state.LogPath.Length!=0)try {File.AppendAllText(state.LogPath,
       "Boss stage="+state.Stage+" actor="+U32(handle,actor+0x78)+
       " combat="+hp+"/"+I32(handle,actor+0xc24)+
       " display="+U16(handle,actor+0x8c0)+"/"+U16(handle,actor+0x8c2)+Environment.NewLine);
      } catch {state.Failures++;}
     }
    }
   } catch {state.Failures++;break;}
  }
  return found;
 }
 static void Enemies(IntPtr handle,long image,long player,HashSet<long> bossActors,int factor,State state) {
  if(factor==1)return;
  long common=Ptr(handle,image+(0x14154c0a8-ImageBase));if(common==0)return;
  int count=U16(handle,common+0x360);if(count>4096)throw new InvalidOperationException("Enemy birth count exceeds bound");
  long table=Ptr(handle,common+0x368);if(table==0)return;
  for(int i=0;i<count;i++) {
   long birth=table+i*160;
   try {
    int type=Read(handle,birth+0x95,1)[0];if(!EnemyTypes.Contains(type))continue;
    long actor=Ptr(handle,birth+0x68);
    if(actor==0||actor==player||bossActors.Contains(actor))continue;
    Apply(handle,actor,factor,state);
   } catch {state.Failures++;}
  }
 }
 static void Monitor(int pid,int enemy,int boss,string path,string signal) {
  using(Mutex mutex=new Mutex(false,"Local\\ZOE2Health-"+pid.ToString(CultureInfo.InvariantCulture))) {
   if(!mutex.WaitOne(0))throw new InvalidOperationException("A health monitor is already attached to this game process");
   try {
    Targets targets=LoadTargets(path);Process game=Game(pid);long image=game.MainModule.BaseAddress.ToInt64();
    IntPtr handle=OpenProcess(Access,false,pid);if(handle==IntPtr.Zero)throw new InvalidOperationException("Cannot open ZOE2 process");
    State state=new State();string log=Path.Combine(Path.GetDirectoryName(path),"health-multiplier.log");state.LogPath=log;
    try {
     File.AppendAllText(log,"Health monitor started: PID "+pid+", enemies "+enemy+"x, bosses "+boss+"x, boss targets "+targets.Count+Environment.NewLine);
     using(EventWaitHandle ready=EventWaitHandle.OpenExisting(signal))ready.Set();
     while(WaitForSingleObject(handle,0)==WaitTimeout) {
      try {
       string stage=Stage(handle,image);
       if(stage!=state.Stage) {
        state.Actors.Clear();state.LastBossHp.Clear();state.Stage=stage;
        File.AppendAllText(log,"Stage "+stage+Environment.NewLine);
       }
       long player=Ptr(handle,image+(0x14156d710-ImageBase));
       HashSet<long> bossActors=Bosses(handle,image,player,targets,boss,state);
       Enemies(handle,image,player,bossActors,enemy,state);
      } catch {state.Failures++;}
      Thread.Sleep(25);
     }
     File.AppendAllText(log,"Health monitor stopped: scaled "+state.Changed+", skipped "+state.Skipped+", read failures "+state.Failures+Environment.NewLine);
    } finally {CloseHandle(handle);}
   } finally {mutex.ReleaseMutex();}
  }
 }
 static void Attach(int pid,int enemy,int boss,string path) {
  if(enemy<1||enemy>3||boss<1||boss>3||enemy==1&&boss==1)throw new InvalidOperationException("Invalid health multiplier selection");
  if(!File.Exists(path))throw new FileNotFoundException("Health target list missing",path);
  Game(pid);LoadTargets(path);
  string signal="Local\\ZOE2HealthReady-"+Guid.NewGuid().ToString("N");
  using(EventWaitHandle ready=new EventWaitHandle(false,EventResetMode.ManualReset,signal)) {
   ProcessStartInfo start=new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName);
   start.Arguments="--monitor "+pid+" "+enemy+" "+boss+" \""+path.Replace("\"","")+"\" "+signal;
   start.UseShellExecute=false;start.CreateNoWindow=true;start.WindowStyle=ProcessWindowStyle.Hidden;
   start.RedirectStandardError=true;
   using(Process child=Process.Start(start)) {
    bool started=false;
    for(int attempt=0;attempt<120;attempt++) {
     if(ready.WaitOne(500)){started=true;break;}
     if(child.HasExited)throw new InvalidOperationException("Health monitor exited during startup: "+child.StandardError.ReadToEnd());
    }
    if(!started)throw new InvalidOperationException("Health monitor did not start within 60 seconds; close and relaunch ZOE2 before retrying");
   }
  }
  Console.WriteLine("Health monitor active for PID "+pid+": enemies "+enemy+"x, bosses "+boss+"x");
 }
 static void SelfTest() {
  IntPtr memory=Marshal.AllocHGlobal(0x2000),handle=OpenProcess(Access,false,Process.GetCurrentProcess().Id);
  if(handle==IntPtr.Zero)throw new InvalidOperationException("Self-test process unavailable");
  try {
   long actor=memory.ToInt64();State state=new State();
   Marshal.Copy(new byte[0x2000],0,memory,0x2000);
   Marshal.WriteInt32(new IntPtr(actor+8),7);
   Marshal.WriteInt32(new IntPtr(actor+0xc20),50);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),100);
   if(!Apply(handle,actor,2,state)||I32(handle,actor+0xc20)!=100||I32(handle,actor+0xc24)!=200)throw new Exception("Double HP failed");
   if(Apply(handle,actor,2,state))throw new Exception("Repeated scaling");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),30);
   if(Apply(handle,actor,2,state)||I32(handle,actor+0xc20)!=30)throw new Exception("Damage was overwritten");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),40);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),80);
   if(!Apply(handle,actor,3,state)||I32(handle,actor+0xc20)!=120||I32(handle,actor+0xc24)!=240)throw new Exception("Phase reset/triple HP failed");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),0);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),80);
   if(Apply(handle,actor,3,state)||I32(handle,actor+0xc20)!=0)throw new Exception("Dead actor resurrected");
   Marshal.WriteInt32(new IntPtr(actor+8),8);
   Marshal.WriteInt32(new IntPtr(actor+0xc20),60);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),100);
   if(!Apply(handle,actor,2,state)||I32(handle,actor+0xc20)!=120||I32(handle,actor+0xc24)!=200)throw new Exception("Actor reuse scaling failed");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),70);
   Apply(handle,actor,2,state);
   Marshal.WriteInt32(new IntPtr(actor+0xc20),100);
   if(!Apply(handle,actor,2,state)||I32(handle,actor+0xc20)!=200)throw new Exception("Current-only phase reset failed");
   Marshal.WriteInt32(new IntPtr(actor+8),9);
   Marshal.WriteInt32(new IntPtr(actor+0xc20),50);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),100);
   Marshal.WriteInt16(new IntPtr(actor+0x8c0),50);
   Marshal.WriteInt16(new IntPtr(actor+0x8c2),100);
   if(!Apply(handle,actor,3,state)||!SyncBossDisplay(handle,actor,3,state)||
      U16(handle,actor+0x8c0)!=150||U16(handle,actor+0x8c2)!=300)
    throw new Exception("Boss display did not scale with combat HP");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),120);
   if(SyncBossDisplay(handle,actor,3,state)||U16(handle,actor+0x8c0)!=150||
      !SyncBossDisplay(handle,actor,3,state)||U16(handle,actor+0x8c0)!=120)
    throw new Exception("Stale boss display did not follow combat damage");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),150);
   Marshal.WriteInt16(new IntPtr(actor+0x8c0),120);
   if(SyncBossDisplay(handle,actor,3,state)||U16(handle,actor+0x8c0)!=120)
    throw new Exception("Boss display damage was overwritten");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),300);
   Marshal.WriteInt16(new IntPtr(actor+0x8c0),100);
   if(!SyncBossDisplay(handle,actor,3,state)||U16(handle,actor+0x8c0)!=300)
    throw new Exception("Boss display phase refill failed");
   Marshal.WriteInt32(new IntPtr(actor+0xc20),40);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),80);
   Marshal.WriteInt16(new IntPtr(actor+0x8c0),40);
   Marshal.WriteInt16(new IntPtr(actor+0x8c2),80);
   if(!Apply(handle,actor,3,state)||!SyncBossDisplay(handle,actor,3,state)||
      U16(handle,actor+0x8c0)!=120||U16(handle,actor+0x8c2)!=240)
    throw new Exception("Boss display second phase failed");
   Marshal.WriteInt32(new IntPtr(actor+8),10);
   Marshal.WriteInt32(new IntPtr(actor+0xc20),10000);
   Marshal.WriteInt32(new IntPtr(actor+0xc24),20000);
   Marshal.WriteInt16(new IntPtr(actor+0x8c0),10000);
   Marshal.WriteInt16(new IntPtr(actor+0x8c2),20000);
   if(!Apply(handle,actor,3,state)||!SyncBossDisplay(handle,actor,3,state)||
      U16(handle,actor+0x8c0)!=16384||U16(handle,actor+0x8c2)!=32767||
      I32(handle,actor+0xc20)!=30000||I32(handle,actor+0xc24)!=60000)
    throw new Exception("Signed boss display cap changed combat HP or display fraction");
   string path=Path.GetTempFileName();
   try {
    File.WriteAllText(path,"ba02\t123\nvs_ba02\t456\n",Encoding.UTF8);
    Targets t=LoadTargets(path);
    if(t.Count!=2||!t.Has("ba02",123)||t.Has("ba02",456))throw new Exception("Seed boss target filtering failed");
    File.AppendAllText(path,"ba02\t123\n",Encoding.UTF8);
    try {LoadTargets(path);throw new Exception("Duplicate target accepted");}
    catch(InvalidOperationException error){if(error.Message=="Duplicate target accepted")throw;}
   } finally {File.Delete(path);}
   Console.WriteLine("PASS health scaling, boss display, damage, phase reset, actor reuse, death gate, seed target parsing; no game opened");
  } finally {CloseHandle(handle);Marshal.FreeHGlobal(memory);}
 }
 public static int Main(string[] args) {
  try {
   if(args.Length==1&&args[0]=="--self-test"){SelfTest();return 0;}
   if(args.Length==5&&args[0]=="--attach-menu") {
    Attach(Int32.Parse(args[1]),Int32.Parse(args[2]),Int32.Parse(args[3]),args[4]);return 0;
   }
   if(args.Length==6&&args[0]=="--monitor") {
    Monitor(Int32.Parse(args[1]),Int32.Parse(args[2]),Int32.Parse(args[3]),args[4],args[5]);return 0;
   }
   throw new InvalidOperationException("Usage: --self-test or --attach-menu PID ENEMY_MULTIPLIER BOSS_MULTIPLIER TARGETS");
  } catch(Exception error) {Console.Error.WriteLine(error);return 1;}
 }
}
