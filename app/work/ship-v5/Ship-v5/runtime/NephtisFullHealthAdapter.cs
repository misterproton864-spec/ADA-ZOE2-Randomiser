using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;

public static class NephtisFullHealthAdapter {
 const long ImageBase=0x140000000;
 const long Factory=0x14633856d;
 const long CentreXY=0x1434c8f10, CentreZW=0x1434c8f18;
 static readonly byte[] Stolen={0x8b,0x87,0x24,0x0c,0x00,0x00,0x99,0x4c,0x89,0x9f,0x08,0x19,0x00,0x00,0x29,0xd0,0xc6,0x87,0x18,0x19,0x00,0x00,0x03,0xd1,0xf8,0x89,0x87,0x20,0x0c,0x00,0x00};
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
  List<byte> b=new List<byte>();
  Add(b,0x50); // preserve RAX and flags; MOV/PUSH/POP do not modify flags
  Add(b,0x48,0x8b,0x87,0x80,0x09,0,0); // actor position XY
  Add(b,0x48,0x89,0x05);b.AddRange(Rel32(image+CentreXY-ImageBase,cave+b.Count+4));
  Add(b,0x48,0x8b,0x87,0x88,0x09,0,0); // actor position ZW
  Add(b,0x48,0x89,0x05);b.AddRange(Rel32(image+CentreZW-ImageBase,cave+b.Count+4));
  Add(b,0x58);
  // Replay original arithmetic/phase setup; reload maximum HP before original store.
  for(int i=0;i<Stolen.Length-6;i++)b.Add(Stolen[i]);
  Add(b,0x8b,0x87,0x24,0x0c,0,0);
  for(int i=Stolen.Length-6;i<Stolen.Length;i++)b.Add(Stolen[i]);
  Add(b,0xe9);b.AddRange(Rel32(image+Factory-ImageBase+Stolen.Length,cave+b.Count+4));
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
  long[] bases={ImageBase,0x180000000,0x7ff600000000};
  foreach(long image in bases) {
   long cave=image+0x20000000;byte[] code=BuildCave(image,cave),redirect=BuildRedirect(image,cave);
   if(code.Length!=72||redirect.Length!=31)throw new Exception("Bad code length");
   if(cave+15+BitConverter.ToInt32(code,11)!=image+CentreXY-ImageBase)throw new Exception("Bad XY displacement");
   if(cave+29+BitConverter.ToInt32(code,25)!=image+CentreZW-ImageBase)throw new Exception("Bad ZW displacement");
   if(cave+72+BitConverter.ToInt32(code,68)!=image+Factory-ImageBase+31)throw new Exception("Bad return displacement");
   if(image+Factory-ImageBase+5+BitConverter.ToInt32(redirect,1)!=cave)throw new Exception("Bad detour displacement");
  }
  File.WriteAllBytes(Path.Combine(folder,"nephtis-centre-cave.bin"),BuildCave(ImageBase,ImageBase+0x20000000));
  File.WriteAllBytes(Path.Combine(folder,"nephtis-centre-redirect.bin"),BuildRedirect(ImageBase,ImageBase+0x20000000));
  Console.WriteLine("Self-test passed at 3 image bases. No process or game files changed.");
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
   if(!Equal(Read(h,entry,Stolen.Length),Stolen))throw new Exception("Factory bytes differ or adapter already active");
   for(long delta=0x20000000;delta<=0x60000000;delta+=0x10000000) {
    allocation=VirtualAllocEx(h,new IntPtr(image+delta),new IntPtr(4096),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(allocation!=IntPtr.Zero)break;
   }
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
   Console.WriteLine("Runtime full-health arena adapter active for PID "+pid+". Closing the game removes it. Disk executable unchanged.");
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
