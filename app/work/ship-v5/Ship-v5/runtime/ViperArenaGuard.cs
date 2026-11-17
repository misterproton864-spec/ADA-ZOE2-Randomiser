using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;

public static class ViperArenaGuard {
 const long ImageBase=0x140000000;
 const long Factory=0x140764970;
 const long CentreXY=0x1434c8f10, CentreZW=0x1434c8f18;
 static readonly byte[] Stolen={0x40,0x53,0x48,0x83,0xec,0x30,0x48,0x83,0x89,0x50,0x14,0x0,0x0,0x2};
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
 static readonly byte[] Payload={0x9c,0x50,0x41,0x52,0x85,0xd2,0xf,0x85,0x9,0x1,0x0,0x0,0xf6,0x81,0xe8,0xb,0x0,0x0,0x4,0xf,0x85,0xfc,0x0,0x0,0x0,0x48,0xb8,0x30,0x58,0x53,0x41,0x1,0x0,0x0,0x0,0x80,0x78,0x0,0x76,0xf,0x85,0x5c,0x0,0x0,0x0,0x80,0x78,0x1,0x73,0xf,0x85,0x52,0x0,0x0,0x0,0x80,0x78,0x2,0x5f,0xf,0x85,0x48,0x0,0x0,0x0,0x80,0x78,0x3,0x62,0xf,0x85,0x3e,0x0,0x0,0x0,0x80,0x78,0x4,0x61,0xf,0x85,0x34,0x0,0x0,0x0,0x80,0x78,0x5,0x30,0xf,0x85,0x2a,0x0,0x0,0x0,0x80,0x78,0x6,0x32,0xf,0x85,0x20,0x0,0x0,0x0,0x80,0x78,0x7,0x0,0xf,0x85,0x16,0x0,0x0,0x0,0x44,0x8b,0x51,0x78,0x41,0x81,0xfa,0x7b,0x36,0xff,0xff,0xf,0x84,0x70,0x0,0x0,0x0,0xe9,0x8c,0x0,0x0,0x0,0x80,0x78,0x0,0x76,0xf,0x85,0x5c,0x0,0x0,0x0,0x80,0x78,0x1,0x73,0xf,0x85,0x52,0x0,0x0,0x0,0x80,0x78,0x2,0x5f,0xf,0x85,0x48,0x0,0x0,0x0,0x80,0x78,0x3,0x76,0xf,0x85,0x3e,0x0,0x0,0x0,0x80,0x78,0x4,0x63,0xf,0x85,0x34,0x0,0x0,0x0,0x80,0x78,0x5,0x30,0xf,0x85,0x2a,0x0,0x0,0x0,0x80,0x78,0x6,0x31,0xf,0x85,0x20,0x0,0x0,0x0,0x80,0x78,0x7,0x0,0xf,0x85,0x16,0x0,0x0,0x0,0x44,0x8b,0x51,0x78,0x41,0x81,0xfa,0x7b,0x36,0xff,0xff,0xf,0x84,0xa,0x0,0x0,0x0,0xe9,0x26,0x0,0x0,0x0,0xe9,0x21,0x0,0x0,0x0,0xc6,0x81,0x9c,0x12,0x0,0x0,0x1,0x48,0xc7,0x81,0xc8,0x12,0x0,0x0,0x0,0x0,0x0,0x0,0xc7,0x81,0xa4,0x12,0x0,0x0,0x26,0x0,0x0,0x0,0x41,0x5a,0x58,0x9d,0xc3,0x41,0x5a,0x58,0x9d,0x40,0x53,0x48,0x83,0xec,0x30,0x48,0x83,0x89,0x50,0x14,0x0,0x0,0x2,0xe9,0x52,0x48,0x76,0xe0};
 public static byte[] BuildCave(long image,long cave) {byte[] b=(byte[])Payload.Clone();Buffer.BlockCopy(BitConverter.GetBytes(image+0x1535830),0,b,27,8);Buffer.BlockCopy(Rel32(image+Factory-ImageBase+Stolen.Length,cave+b.Length),0,b,b.Length-4,4);return b;}
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
 Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
 long cave=image+0x20000000;byte[] b=BuildCave(image,cave),p=BuildRedirect(image,cave);
 if(image+Factory-ImageBase+5+BitConverter.ToInt32(p,1)!=cave)throw new Exception("Redirect mismatch");
 if(cave+b.Length+BitConverter.ToInt32(b,b.Length-4)!=image+Factory-ImageBase+Stolen.Length)throw new Exception("Continuation mismatch");
 File.WriteAllBytes(Path.Combine(folder,"viper-"+image.ToString("x")+".bin"),b);
 }Console.WriteLine("Tight-arena aircraft-entry guard generated at three image bases; no game opened.");
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
   if(!Equal(Read(h,entry,Stolen.Length),Stolen))throw new Exception("Aircraft-entry bytes differ or guard already active");
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
   Console.WriteLine("Runtime Vic Viper tight-arena aircraft-entry guard active for PID "+pid+". Closing the game removes it. Disk executable unchanged.");
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
