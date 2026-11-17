using System;
using System.Collections.Generic;
// Offline emitter only. Runtime attachment, save persistence and weapon assets need integration.
public static class MetatronRewardCode {
 public static readonly byte[] Pool={1,2,3,4,6,7,8,9,10,11,12};
 const long OriginalBase=0x140000000,Hook=0x1490bab79;
 static void Add(List<byte>b,params byte[]v){b.AddRange(v);}
 static void Imm(List<byte>b,uint n){b.AddRange(BitConverter.GetBytes(n));}
 public static byte[] Build(long image,long cave,uint seed,int chance) {
  if(chance<0||chance>100)throw new ArgumentOutOfRangeException("chance");
  var b=new List<byte>();var labels=new Dictionary<string,int>();var fix=new List<KeyValuePair<int,string>>();
  Action<string> mark=n=>labels.Add(n,b.Count);
  Action<string,byte[]> jump=(n,op)=>{b.AddRange(op);fix.Add(new KeyValuePair<int,string>(b.Count,n));Imm(b,0);};
  Add(b,0x9c,0x50,0x52,0x41,0x50,0x41,0x51,0x41,0x52); // flags,RAX,RDX,R8,R9,R10
  Add(b,0x8b,0x81,0xcc,0x62,0,0,0x35);Imm(b,seed); // native pickup counter XOR seed
  Add(b,0x89,0xc2,0xc1,0xea,16,0x31,0xd0,0x69,0xc0);Imm(b,0x85ebca6b);
  Add(b,0x89,0xc2,0xc1,0xea,13,0x31,0xd0,0x69,0xc0);Imm(b,0xc2b2ae35);
  Add(b,0x89,0xc2,0xc1,0xea,16,0x31,0xd0,0x41,0x89,0xc0);
  Add(b,0x31,0xd2,0x41,0xb9);Imm(b,100);Add(b,0x41,0xf7,0xf1,0x83,0xfa,(byte)chance);
  jump("done",new byte[]{0x0f,0x83}); // unsigned remainder >= chance
  Add(b,0x44,0x89,0xc0,0xc1,0xe8,8,0x31,0xd2,0x41,0xb9);Imm(b,11);Add(b,0x41,0xf7,0xf1,0x41,0x89,0xd0);
  Add(b,0x41,0xb9);Imm(b,11);Add(b,0x4c,0x8d,0x15);fix.Add(new KeyValuePair<int,string>(b.Count,"pool"));Imm(b,0);
  mark("loop");Add(b,0x43,0x0f,0xb6,0x04,0x02); // EAX=pool[R8]
  Add(b,0x83,0xbc,0x81,0xb8,0x61,0,0,0); // inventory[weapon] == 0
  jump("next",new byte[]{0x0f,0x85});
  Add(b,0xc7,0x84,0x81,0xb8,0x61,0,0,1,0,0,0);
  jump("done",new byte[]{0xe9});
  mark("next");Add(b,0x41,0xff,0xc0,0x41,0x83,0xf8,11);jump("nowrap",new byte[]{0x0f,0x82});Add(b,0x45,0x31,0xc0);
  mark("nowrap");Add(b,0x41,0xff,0xc9);jump("loop",new byte[]{0x0f,0x85});
  mark("done");Add(b,0x41,0x5a,0x41,0x59,0x41,0x58,0x5a,0x58,0x9d,0xff,0x81,0xcc,0x62,0,0);
  Add(b,0xe9);b.AddRange(BitConverter.GetBytes(checked((int)(image+Hook-OriginalBase+6-(cave+b.Count+4)))));
  mark("pool");b.AddRange(Pool);byte[] result=b.ToArray();
  foreach(var f in fix)Array.Copy(BitConverter.GetBytes(labels[f.Value]-f.Key-4),0,result,f.Key,4);
  if(result.Length>4096)throw new Exception("Code page overflow");return result;
 }
 public static int Expected(uint seed,uint counter,int chance,int[] owned) {
  if(chance<0||chance>100||owned.Length!=16)throw new ArgumentException("Invalid reward state");
  uint x=counter^seed;unchecked{x^=x>>16;x*=0x85ebca6b;x^=x>>13;x*=0xc2b2ae35;x^=x>>16;}
  if(x%100>=chance)return -1;int first=(int)((x>>8)%11);
  for(int n=0;n<11;n++){int weapon=Pool[(first+n)%11];if(owned[weapon]==0)return weapon;}
  return -1;
 }
}
