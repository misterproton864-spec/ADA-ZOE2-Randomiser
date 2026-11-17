using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;

public static class FakeAnubisDamageTableAdapter {
 const long ImageBase=0x140000000;
 const long Factory=0x14781eb8c;
 const long CentreXY=0x1434c8f10, CentreZW=0x1434c8f18;
 static readonly byte[] Stolen={0x45,0x0f,0xbf,0x0c,0x41};
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
 public static byte[] BuildCave(long image,long cave) {
  List<byte> b=new List<byte>();List<int> branches=new List<int>();
  b.AddRange(Stolen);Add(b,0x9c,0x41,0x52);
  // The native function receives actor+0x150 and the shared Anubis variant in R8D.
  Add(b,0x45,0x85,0xc0,0x0f,0x85);branches.Add(b.Count);b.AddRange(new byte[4]);
  Add(b,0x49,0xba);b.AddRange(BitConverter.GetBytes(image+0xd80700));
  Add(b,0x4c,0x39,0x91,0xb0,0xfe,0xff,0xff,0x0f,0x85);branches.Add(b.Count);b.AddRange(new byte[4]);
  Add(b,0x45,0x85,0xc9,0x0f,0x85);branches.Add(b.Count);b.AddRange(new byte[4]);
  Add(b,0x3d);b.AddRange(BitConverter.GetBytes((uint)76));
  Add(b,0x0f,0x83);branches.Add(b.Count);b.AddRange(new byte[4]);
  Add(b,0x4c,0x8d,0x15);int tableFix=b.Count;b.AddRange(new byte[4]);
  Add(b,0x45,0x0f,0xbf,0x0c,0x42);
  int finish=b.Count;Add(b,0x41,0x5a,0x9d,0xe9);
  b.AddRange(Rel32(image+Factory-ImageBase+Stolen.Length,cave+b.Count+4));
  int tableOffset=b.Count;
  foreach(short value in new short[]{0,0,3,7,0,150,70,3,85,19,2,6,0,0,0,0,4,17,12,11,20,3,23,1,30,42,64,9,15,27,51,45,37,75,12,3,1,0,9,0,0,2,11,0,3,7,11,0,0,0,5,7,15,15,2,0,25,25,3,0,18,0,0,9,0,0,0,0,0,0,0,0,0,0,0,31})b.AddRange(BitConverter.GetBytes(value));
  foreach(int fix in branches){byte[] rel=BitConverter.GetBytes(finish-(fix+4));for(int j=0;j<4;j++)b[fix+j]=rel[j];}
  byte[] tableRel=BitConverter.GetBytes(tableOffset-(tableFix+4));for(int j=0;j<4;j++)b[tableFix+j]=tableRel[j];
  return b.ToArray();
 }
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
 static void SelfTest(string folder) {
  Directory.CreateDirectory(folder);
  foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
   long cave=image+0x20000000;byte[] code=BuildCave(image,cave),patch=BuildRedirect(image,cave);
   if(patch.Length!=5)throw new Exception("Redirect length");
  }
  File.WriteAllBytes(Path.Combine(folder,"table-cave.bin"),BuildCave(ImageBase,ImageBase+0x20000000));
  Console.WriteLine("Fake-only stock damage table payload generated at three image bases.");
 }
 static IntPtr AllocateNearby(IntPtr h,long image) {
  // Windows reservation addresses use 64 KiB granularity. Search between
  // occupied helper slots, rather than probing only five shared addresses.
  for(long delta=0x20000000;delta<=0x60000000;delta+=0x10000) {
   IntPtr p=VirtualAllocEx(h,new IntPtr(image+delta),new IntPtr(4096),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
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
   if(!Equal(Read(h,entry,Stolen.Length),Stolen))throw new Exception("Damage bytes differ or adapter already active");
   allocation=AllocateNearby(h,image);
   Check(allocation!=IntPtr.Zero,"Allocate nearby code");
   long cave=allocation.ToInt64();byte[] code=BuildCave(image,cave),patch=BuildRedirect(image,cave);
   Write(h,cave,code);if(!Equal(Read(h,cave,code.Length),code))throw new Exception("Code verification failed");
   uint old;Check(VirtualProtectEx(h,allocation,new IntPtr(4096),PAGE_EXECUTE_READ,out old),"Protect code");
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
   Console.WriteLine("Runtime Fake Anubis stock damage table adapter active for PID "+pid+". Closing the game removes it. Disk executable unchanged.");
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
