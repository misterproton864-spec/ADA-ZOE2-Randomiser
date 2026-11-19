using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;

public static class FakeAumaanReachAdapter {
 const long ImageBase=0x140000000;
 const long Factory=0x1404f4c90;
 const long CentreXY=0x1434c8f10, CentreZW=0x1434c8f18;
 static readonly byte[] Stolen={233,171,210,42,7};
 const string ExpectedExe="b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92";
 const uint MEM_COMMIT=0x1000,MEM_RESERVE=0x2000,MEM_RELEASE=0x8000;
 const uint PAGE_READWRITE=4,PAGE_EXECUTE_READ=0x20,PAGE_EXECUTE_READWRITE=0x40;
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool ReadProcessMemory(IntPtr h,IntPtr address,byte[] buffer,IntPtr size,out IntPtr read);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool WriteProcessMemory(IntPtr h,IntPtr address,byte[] buffer,IntPtr size,out IntPtr written);
 [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr VirtualAllocEx(IntPtr h,IntPtr address,IntPtr size,uint type,uint protect);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool VirtualFreeEx(IntPtr h,IntPtr address,IntPtr size,uint type);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool VirtualProtectEx(IntPtr h,IntPtr address,IntPtr size,uint protect,out uint old);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool FlushInstructionCache(IntPtr h,IntPtr address,IntPtr size);
 static void Check(bool ok,string what) { if(!ok) throw new InvalidOperationException(what+" (Win32 "+Marshal.GetLastWin32Error()+")"); }
 static byte[] Read(IntPtr h,long address,int count) {
  byte[] b=new byte[count];IntPtr n;
  Check(ReadProcessMemory(h,new IntPtr(address),b,new IntPtr(count),out n)&&n.ToInt64()==count,"Read memory");
  return b;
 }
 static void Write(IntPtr h,long address,byte[] b) {
  IntPtr n;Check(WriteProcessMemory(h,new IntPtr(address),b,new IntPtr(b.Length),out n)&&n.ToInt64()==b.Length,"Write memory");
 }
 static bool Equal(byte[] a,byte[] b) {
  if(a.Length!=b.Length)return false;
  for(int i=0;i<a.Length;i++)if(a[i]!=b[i])return false;
  return true;
 }
 static byte[] Rel32(long target,long next) { return BitConverter.GetBytes(checked((int)(target-next))); }
 static void Add(List<byte> b,params byte[] bytes) { b.AddRange(bytes); }
 static readonly byte[] Wrapper={83,72,131,236,64,72,137,203,72,186,0,128,0,96,1,0,0,0,69,49,192,72,184,0,16,0,96,1,0,0,0,255,208,72,137,217,72,184,64,31,122,71,1,0,0,0,255,208,72,137,217,72,186,0,128,0,96,1,0,0,0,65,184,1,0,0,0,72,184,0,16,0,96,1,0,0,0,255,208,72,131,196,64,91,195};
 static readonly byte[] Tick={65,86,86,87,85,83,72,129,236,192,0,0,0,68,15,41,188,36,176,0,0,0,68,15,41,180,36,160,0,0,0,68,15,41,172,36,144,0,0,0,68,15,41,164,36,128,0,0,0,102,68,15,127,92,36,112,102,68,15,127,84,36,96,102,68,15,127,76,36,80,68,15,41,68,36,64,15,41,124,36,48,15,41,116,36,32,131,122,36,0,15,132,146,5,0,0,72,139,2,68,15,182,0,65,131,248,102,116,34,65,131,248,99,117,58,128,120,1,97,117,52,128,120,2,48,117,46,128,120,3,50,117,40,128,120,4,0,64,15,148,199,235,32,128,120,1,97,117,24,128,120,2,48,117,18,128,120,3,49,117,12,128,120,4,0,64,15,148,198,49,255,235,4,49,255,49,246,64,132,255,117,9,64,132,246,15,132,51,5,0,0,72,139,1,72,59,66,16,15,133,38,5,0,0,139,65,120,59,66,32,15,133,26,5,0,0,15,182,129,155,0,0,0,68,15,182,199,71,141,4,64,65,131,192,10,65,57,192,15,133,254,4,0,0,131,185,32,12,0,0,0,15,142,241,4,0,0,64,132,255,116,39,131,185,160,18,0,0,13,15,132,223,4,0,0,131,185,164,18,0,0,13,15,132,210,4,0,0,246,129,83,20,0,0,112,15,133,197,4,0,0,64,132,246,116,39,131,185,160,22,0,0,0,15,133,179,4,0,0,131,185,164,22,0,0,0,15,143,166,4,0,0,131,185,248,20,0,0,0,15,133,153,4,0,0,72,139,66,8,72,139,0,72,133,192,15,132,137,4,0,0,102,15,110,184,128,9,0,0,102,65,15,126,248,65,129,224,255,255,255,127,65,129,248,255,255,127,127,15,135,104,4,0,0,102,15,110,176,132,9,0,0,102,65,15,126,240,65,129,224,255,255,255,127,65,129,248,255,255,127,127,15,135,71,4,0,0,102,68,15,110,128,136,9,0,0,102,68,15,126,192,37,255,255,255,127,61,255,255,127,127,15,135,41,4,0,0,102,68,15,110,153,128,9,0,0,102,68,15,126,216,37,255,255,255,127,61,255,255,127,127,15,135,11,4,0,0,102,68,15,110,137,132,9,0,0,102,68,15,126,200,37,255,255,255,127,61,255,255,127,127,15,135,237,3,0,0,102,68,15,110,145,136,9,0,0,102,68,15,126,208,37,255,255,255,127,61,255,255,127,127,15,135,207,3,0,0,102,69,15,111,227,243,68,15,92,231,102,69,15,111,234,243,69,15,92,232,65,15,40,197,243,65,15,89,197,69,15,40,244,243,69,15,89,244,243,68,15,88,240,102,68,15,126,240,37,255,255,255,127,61,255,255,127,127,15,135,143,3,0,0,102,69,15,111,249,243,68,15,92,254,102,68,15,126,248,37,255,255,255,127,61,255,255,127,127,15,135,112,3,0,0,72,137,203,73,137,214,72,57,74,40,117,13,139,67,8,65,57,70,48,117,7,49,237,235,22,139,67,8,76,137,241,73,137,94,40,65,137,70,48,65,131,70,52,1,64,181,1,64,132,255,15,132,19,1,0,0,73,139,70,24,72,137,217,72,137,131,88,22,0,0,184,252,253,255,255,35,131,212,21,0,0,131,200,1,137,131,212,21,0,0,246,131,232,11,0,0,4,15,132,165,0,0,0,72,139,131,128,0,0,0,72,133,192,15,132,149,0,0,0,72,139,139,88,20,0,0,72,133,201,15,132,133,0,0,0,72,139,147,136,0,0,0,72,133,210,116,121,76,139,131,160,20,0,0,77,133,192,116,109,128,160,234,0,0,0,254,128,137,234,0,0,0,1,128,98,16,253,65,128,72,16,2,72,137,216,128,163,232,11,0,0,251,199,131,168,20,0,0,255,255,255,255,65,131,70,64,1,72,139,131,200,18,0,0,72,133,192,116,11,72,137,217,139,147,164,18,0,0,255,208,72,137,216,72,199,131,200,18,0,0,0,0,0,0,198,131,156,18,0,0,1,199,131,164,18,0,0,0,0,0,0,128,139,236,11,0,0,4,64,132,237,117,68,139,131,164,18,0,0,131,248,2,116,57,131,248,14,116,52,131,192,215,131,248,251,119,44,139,131,160,18,0,0,131,248,2,116,33,131,248,14,116,28,131,192,215,131,248,252,115,20,243,15,16,5,185,2,0,0,235,89,243,15,16,5,171,2,0,0,235,74,72,139,131,200,18,0,0,72,133,192,116,11,72,137,217,139,147,164,18,0,0,255,208,72,137,216,72,199,131,200,18,0,0,0,0,0,0,198,131,156,18,0,0,1,199,131,164,18,0,0,0,0,0,0,128,139,236,11,0,0,4,65,131,70,56,1,243,15,16,5,99,2,0,0,64,132,237,117,41,15,40,200,243,15,89,200,68,15,46,241,119,28,68,15,46,61,77,2,0,0,119,18,243,15,16,13,71,2,0,0,65,15,46,207,15,134,1,1,0,0,64,132,255,116,79,68,15,46,53,56,2,0,0,118,104,15,87,201,243,65,15,81,206,243,15,16,21,42,2,0,0,243,15,94,209,243,68,15,89,226,243,68,15,88,231,243,68,15,89,234,243,69,15,88,232,184,32,23,0,0,185,36,23,0,0,186,40,23,0,0,69,15,40,213,68,15,40,206,69,15,40,220,235,72,243,68,15,16,13,228,1,0,0,243,68,15,88,206,184,0,20,0,0,185,4,20,0,0,186,8,20,0,0,69,15,40,208,235,33,243,68,15,16,21,201,1,0,0,243,69,15,88,208,184,32,23,0,0,185,36,23,0,0,186,40,23,0,0,68,15,40,206,68,15,40,223,73,137,216,243,68,15,17,155,128,9,0,0,243,68,15,17,139,132,9,0,0,243,68,15,17,147,136,9,0,0,243,68,15,17,155,96,11,0,0,243,68,15,17,139,100,11,0,0,243,68,15,17,147,104,11,0,0,72,199,131,160,10,0,0,0,0,0,0,199,131,168,10,0,0,0,0,0,0,65,131,70,60,1,243,68,15,17,28,3,243,68,15,17,12,11,243,68,15,17,20,19,64,132,255,185,80,21,0,0,184,176,24,0,0,15,69,193,72,137,217,243,15,16,12,3,243,15,92,207,243,15,16,84,3,8,243,65,15,92,208,243,15,89,210,243,15,89,201,243,15,88,202,102,15,126,201,129,225,255,255,255,127,129,249,255,255,127,127,119,32,243,15,16,84,3,4,243,15,92,214,102,15,126,209,129,225,255,255,255,127,129,249,255,255,127,127,15,134,145,0,0,0,72,141,72,4,72,137,218,102,68,15,126,28,3,72,131,200,8,102,68,15,126,12,11,102,68,15,126,20,3,64,132,246,116,27,102,68,15,126,155,192,20,0,0,102,68,15,126,139,196,20,0,0,102,68,15,126,147,200,20,0,0,15,40,116,36,32,15,40,124,36,48,68,15,40,68,36,64,68,15,40,76,36,80,68,15,40,84,36,96,68,15,40,92,36,112,68,15,40,164,36,128,0,0,0,68,15,40,172,36,144,0,0,0,68,15,40,180,36,160,0,0,0,68,15,40,188,36,176,0,0,0,72,129,196,192,0,0,0,91,93,95,94,65,94,195,243,15,89,192,15,46,200,15,135,98,255,255,255,15,46,21,46,0,0,0,15,135,85,255,255,255,243,15,16,5,36,0,0,0,15,46,194,15,134,97,255,255,255,233,63,255,255,255,0,0,0,0,0,0,0,0,0,0,0,0,250,67,0,128,34,68,0,0,52,67,0,0,52,195,0,0,240,66,111,18,131,58,0,0,200,67};
 public static byte[] BuildCave(long image,long cave){byte[] b=new byte[0x1000+Tick.Length];Buffer.BlockCopy(Wrapper,0,b,0,Wrapper.Length);Buffer.BlockCopy(BitConverter.GetBytes(cave+0x8000),0,b,10,8);Buffer.BlockCopy(BitConverter.GetBytes(cave+0x8000),0,b,53,8);Buffer.BlockCopy(BitConverter.GetBytes(cave+0x1000+0),0,b,23,8);Buffer.BlockCopy(BitConverter.GetBytes(cave+0x1000+0),0,b,69,8);Buffer.BlockCopy(BitConverter.GetBytes(image+125443904),0,b,38,8);Buffer.BlockCopy(Tick,0,b,0x1000,Tick.Length);return b;}
 public static byte[] Config(long image){List<byte>b=new List<byte>();b.AddRange(BitConverter.GetBytes(image+22239280));b.AddRange(BitConverter.GetBytes(image+22468368));b.AddRange(BitConverter.GetBytes(image+14156592));b.AddRange(BitConverter.GetBytes(image+7783440));b.AddRange(BitConverter.GetBytes((uint)4294959705));b.AddRange(BitConverter.GetBytes((uint)1));b.AddRange(new byte[32]);return b.ToArray();}
 public static byte[] BuildRedirect(long image,long cave) {
  List<byte> b=new List<byte>();Add(b,0xe9);b.AddRange(Rel32(cave,image+Factory-ImageBase+5));
  while(b.Count<Stolen.Length)b.Add(0x90);
  return b.ToArray();
 }
 static string Sha(string path) {
  using(FileStream f=File.OpenRead(path))using(SHA256 s=SHA256.Create()) {
   return BitConverter.ToString(s.ComputeHash(f)).Replace("-","").ToLowerInvariant();
  }
 }
 static void SelfTest(string folder){Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}){long cave=image+0x20000000;byte[] b=BuildCave(image,cave);if(Config(image).Length!=72||b.Length>=0x8000)throw new Exception("Payload bounds");File.WriteAllBytes(Path.Combine(folder,"reach-"+image.ToString("x")+".bin"),b);}Console.WriteLine("Reach payload relocation passed; no game opened.");}
 static IntPtr AllocateNearby(IntPtr h,long image) {
  // Windows reservation addresses use 64 KiB granularity. Search between
  // occupied helper slots, rather than probing only five shared addresses.
  for(long delta=0x20000000;delta<=0x60000000;delta+=0x10000) {
   IntPtr p=VirtualAllocEx(h,new IntPtr(image+delta),new IntPtr(0x9000),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
   if(p!=IntPtr.Zero)return p;
  }
  return IntPtr.Zero;
 }
 static void Attach(int pid) {
  Process process=Process.GetProcessById(pid);
  if(!String.Equals(process.ProcessName,"Zoe2Mars",StringComparison.OrdinalIgnoreCase))throw new Exception("Wrong process");
  string exe=process.MainModule.FileName;long image=process.MainModule.BaseAddress.ToInt64();
  if(Sha(exe)!=ExpectedExe)throw new Exception("Unsupported executable hash");
  IntPtr h=OpenProcess(0x438,false,pid);Check(h!=IntPtr.Zero,"Open process");
  IntPtr allocation=IntPtr.Zero;bool redirectAttempted=false,redirectVerified=false;
  long entry=image+Factory-ImageBase;
  try {
   byte[] healRedirect=Read(h,image+0x76d9916,10);
   if(healRedirect[0]!=0xe9)throw new Exception("Attach the seed normal helpers first: Aumaan healing guard missing");
   long healCave=image+0x76d9916+5+BitConverter.ToInt32(healRedirect,1);
   byte[] expectedHeal=AumaanArenaGuard.BuildCave(image,healCave);
   if(!Equal(Read(h,healCave,expectedHeal.Length),expectedHeal))throw new Exception("Existing Aumaan healing guard differs");
   if(!Equal(Read(h,entry,Stolen.Length),Stolen))throw new Exception("Damage bytes differ or adapter already active");
   allocation=AllocateNearby(h,image);
   Check(allocation!=IntPtr.Zero,"Allocate nearby code");
   long cave=allocation.ToInt64();byte[] code=BuildCave(image,cave),patch=BuildRedirect(image,cave);
   Write(h,cave,code);Write(h,cave+0x8000,Config(image));if(!Equal(Read(h,cave+0x8000,72),Config(image)))throw new Exception("Reach configuration readback failed");if(!Equal(Read(h,cave,code.Length),code))throw new Exception("Code verification failed");
   uint old;Check(VirtualProtectEx(h,allocation,new IntPtr(0x8000),PAGE_EXECUTE_READ,out old),"Protect code");
   Check(FlushInstructionCache(h,allocation,new IntPtr(code.Length)),"Flush code");
   uint entryOld;Check(VirtualProtectEx(h,new IntPtr(entry),new IntPtr(Stolen.Length),PAGE_EXECUTE_READWRITE,out entryOld),"Protect factory");
   try {
    redirectAttempted=true;Write(h,entry,patch);
    Check(FlushInstructionCache(h,new IntPtr(entry),new IntPtr(patch.Length)),"Flush redirect");
    if(!Equal(Read(h,entry,patch.Length),patch))throw new Exception("Redirect verification failed");
    redirectVerified=true;
   } catch {
    Write(h,entry,Stolen);
    Check(FlushInstructionCache(h,new IntPtr(entry),new IntPtr(Stolen.Length)),"Flush restored factory");
    if(!Equal(Read(h,entry,Stolen.Length),Stolen))throw new Exception("Restore verification failed; close game");
    redirectAttempted=false;throw;
   } finally {
    uint ignored;Check(VirtualProtectEx(h,new IntPtr(entry),new IntPtr(Stolen.Length),entryOld,out ignored),"Restore factory protection");
   }
   Console.WriteLine("Runtime fa01 boss proximity adapter active for PID "+pid+". Closing the game removes it. Disk executable unchanged.");
  } finally {
   // Never release code after a verified detour or an uncertain partial write.
   if(allocation!=IntPtr.Zero&&!redirectVerified&&!redirectAttempted)VirtualFreeEx(h,allocation,IntPtr.Zero,MEM_RELEASE);
   CloseHandle(h);
  }
 }
 public static int Main(string[] args) {
  try {
   if(args.Length==2&&args[0]=="--self-test"){SelfTest(args[1]);return 0;}
   if(args.Length==2&&args[0]=="--attach-menu"){Attach(Int32.Parse(args[1]));return 0;}
   Console.WriteLine("Offline preview helper. --self-test <output folder>; --attach-menu <game PID> only while at menu. Not a full randomiser.");
   return 0;
  } catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}
 }
}
