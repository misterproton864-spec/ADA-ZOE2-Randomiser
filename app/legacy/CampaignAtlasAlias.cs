using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Security.Cryptography;
public static class CampaignAtlasAlias {
 class Entry { public string Name; public ulong Size, Offset; }
 class Index { public bool Big;public int Width; public ulong Names,Table,Data;public List<Entry> Entries=new List<Entry>(); }
 static ulong Num(BinaryReader r,bool big,int width){byte[] b=r.ReadBytes(width);if(b.Length!=width)throw new EndOfStreamException();if(big)Array.Reverse(b);return width==4?BitConverter.ToUInt32(b,0):BitConverter.ToUInt64(b,0);}
 static void Put(BinaryWriter w,ulong value,bool big,int width){if(width==4 && value>UInt32.MaxValue)throw new Exception("32-bit offset overflow");byte[] b=width==4?BitConverter.GetBytes((uint)value):BitConverter.GetBytes(value);if(big)Array.Reverse(b);w.Write(b);}
 static Index Read(FileStream f) {
  f.Position=0;var r=new BinaryReader(f,Encoding.ASCII,true);byte[] head=r.ReadBytes(12);
  if(head.Length!=12 || Encoding.ASCII.GetString(head,0,4)!="PAC\0")throw new Exception("Invalid PAC magic");
  string ver=Encoding.ASCII.GetString(head,4,5);if(ver!="0.01a" && ver!="0.01b")throw new Exception("Invalid PAC version");
  var x=new Index();x.Big=ver=="0.01a";x.Width=x.Big?4:8;ulong n=Num(r,x.Big,4);x.Names=Num(r,x.Big,x.Width);x.Table=Num(r,x.Big,x.Width);x.Data=Num(r,x.Big,x.Width);
  if(n==0 || n>1000000 || x.Names!=(x.Big?32UL:48UL) || x.Table!=x.Names+n*32 || x.Data!=x.Table+n*(ulong)(2*x.Width) || x.Data>(ulong)f.Length)throw new Exception("Unsupported archive layout");
  var unique=new HashSet<string>(StringComparer.Ordinal);
  for(ulong i=0;i<n;i++) {
   f.Position=(long)(x.Names+i*32);byte[] bytes=r.ReadBytes(32);int end=Array.IndexOf(bytes,(byte)0);if(end<0)end=32;
   var e=new Entry();e.Name=Encoding.ASCII.GetString(bytes,0,end);if(!unique.Add(e.Name))throw new Exception("Duplicate archive name");
   f.Position=(long)(x.Table+i*(ulong)(2*x.Width));e.Size=Num(r,x.Big,x.Width);e.Offset=Num(r,x.Big,x.Width);
   if(e.Offset>(ulong)f.Length-x.Data || e.Size>(ulong)f.Length-x.Data-e.Offset)throw new Exception("Invalid entry bounds");x.Entries.Add(e);
  }return x;
 }
 static void Match(Index x,string report) {
  var rows=new List<string>();foreach(string line in File.ReadAllLines(report)){string[] c=line.Split('\t');ulong a,b;if(c.Length==3 && UInt64.TryParse(c[1],out a) && UInt64.TryParse(c[2],out b))rows.Add(line);}
  if(rows.Count!=x.Entries.Count)throw new Exception("Archive differs from supplied index");
  for(int i=0;i<rows.Count;i++){string[] c=rows[i].Split('\t');Entry e=x.Entries[i];if(c[0]!=e.Name || UInt64.Parse(c[1])!=e.Size || UInt64.Parse(c[2])!=x.Data+e.Offset)throw new Exception("Archive index mismatch: "+e.Name);}
 }
 static void Copy(Stream src,Stream dst,long count){byte[] b=new byte[1048576];while(count>0){int n=src.Read(b,0,(int)Math.Min(count,b.Length));if(n==0)throw new EndOfStreamException();dst.Write(b,0,n);count-=n;}}
 static byte[] HashRange(FileStream f,ulong offset){f.Position=(long)offset;using(var h=SHA256.Create())return h.ComputeHash(f);}
 public static void Build(string input,string output,string report,string aliasReport) { BuildCore(input,output,report,aliasReport,false); }
 public static void BuildWithReplacements(string input,string output,string report,string aliasReport) { BuildCore(input,output,report,aliasReport,true); }
 static void BuildCore(string input,string output,string report,string aliasReport,bool replaceExisting) {
  using(var source=new FileStream(input,FileMode.Open,FileAccess.Read,FileShare.Read)) {
   Index x=Read(source);Match(x,report);var all=new List<Entry>(x.Entries);int added=0;
   var targets=new HashSet<string>(StringComparer.Ordinal);
   foreach(string row in File.ReadAllLines(aliasReport)) {
    string[] pair=row.Split('\t');
    if(pair.Length!=2)throw new Exception("Invalid alias row");
    string target=pair[0],donor=pair[1];
    if(!targets.Add(target))throw new Exception("Duplicate alias target");
    if(!target.StartsWith("@",StringComparison.Ordinal) || target.Length>32 || !donor.StartsWith("@",StringComparison.Ordinal))throw new Exception("Invalid atlas alias name");
    string suffix=target.EndsWith(".tbl",StringComparison.Ordinal)?".tbl":".dat";
    if(!target.EndsWith(suffix,StringComparison.Ordinal) || !donor.EndsWith(suffix,StringComparison.Ordinal))throw new Exception("Alias extension mismatch");
    Entry d=x.Entries.Find(e=>e.Name==donor);
    if(d==null)throw new Exception("Missing donor "+donor);
    int existing=all.FindIndex(e=>e.Name==target);
    if(existing>=0 && !replaceExisting)throw new Exception("Target already exists: "+target);
    Entry a=new Entry();a.Name=target;a.Size=d.Size;a.Offset=d.Offset;
    if(existing>=0){all[existing]=a;added++;continue;}
    string stage=target.Substring(0,target.IndexOf('_')+1);
    int at=all.FindIndex(e=>e.Name.StartsWith(stage,StringComparison.Ordinal) && e.Name.EndsWith(suffix,StringComparison.Ordinal) && (suffix!=".dat" || !e.Name.EndsWith("_msk.dat",StringComparison.Ordinal)));
    if(at<0)at=all.FindIndex(e=>e.Name.EndsWith(suffix,StringComparison.Ordinal) && (suffix!=".dat" || !e.Name.EndsWith("_msk.dat",StringComparison.Ordinal)));
    if(at<0)throw new Exception("Missing texture group");all.Insert(at,a);added++;
   }
   ulong table=x.Names+(ulong)all.Count*32,data=table+(ulong)all.Count*(ulong)(2*x.Width);
   using(var dest=new FileStream(output,FileMode.CreateNew,FileAccess.ReadWrite,FileShare.None)) {
    var w=new BinaryWriter(dest,Encoding.ASCII,true);source.Position=0;byte[] header=new byte[(int)x.Names];int got=source.Read(header,0,header.Length);if(got!=header.Length)throw new EndOfStreamException();w.Write(header);
    dest.Position=12;Put(w,(ulong)all.Count,x.Big,4);Put(w,x.Names,x.Big,x.Width);Put(w,table,x.Big,x.Width);Put(w,data,x.Big,x.Width);
    dest.Position=(long)x.Names;
    foreach(Entry e in all){byte[] name=Encoding.ASCII.GetBytes(e.Name);if(name.Length>32)throw new Exception("Name too long");w.Write(name);w.Write(new byte[32-name.Length]);}
    foreach(Entry e in all){Put(w,e.Size,x.Big,x.Width);Put(w,e.Offset,x.Big,x.Width);}
    source.Position=(long)x.Data;Copy(source,dest,source.Length-(long)x.Data);w.Flush();dest.Flush();
    if(dest.Length!=source.Length+(long)(data-x.Data))throw new Exception("Output length mismatch");
    Index y=Read(dest);if(y.Entries.Count!=all.Count)throw new Exception("Output index mismatch");
    for(int i=0;i<all.Count;i++){Entry a=all[i],b=y.Entries[i];if(a.Name!=b.Name || a.Offset!=b.Offset || a.Size!=b.Size)throw new Exception("Output entry mismatch");}
    if(!Equal(HashRange(source,x.Data),HashRange(dest,y.Data)))throw new Exception("Original atlas payload verification failed");
   }
   Console.WriteLine("Verified atlas: "+added+" aliases added; all original payload bytes preserved.");
  }
 }
 static bool Equal(byte[] a,byte[] b){if(a.Length!=b.Length)return false;for(int i=0;i<a.Length;i++)if(a[i]!=b[i])return false;return true;}
}
