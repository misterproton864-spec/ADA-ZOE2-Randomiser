"""Read-only telemetry for the shared native identifier pool."""

def augment(source):
 main=' static int Main(string[] args) {';field='      "registry_count",';selftest='     CounterSelfTest();'
 if any(source.count(x)!=1 for x in (main,field,selftest)):raise ValueError('Recorder boundaries changed')
 method=r'''
 static object IdentifierPoolAt(long table,uint scanMode,uint cursor) {
  byte[] slots=Read(table,8193);int occupied=0;
  for(int i=1;i<8192;i++)if(slots[i]!=0)occupied++;
  return Obj("occupied_nonzero_ids",occupied,"available_nonzero_ids",8191-occupied,
   "scan_mode",scanMode,"native_cursor",cursor,"reserved_zero",slots[0],"byte_after_pool",slots[8192],
   "read_only",true,"interpretation","Sampled shared ID occupancy; a full pool is a possible crash mechanism, not proof of this crash.");
 }
 static object IdentifierPool() {
  return IdentifierPoolAt(VA(0x1438804a0),Read(VA(0x1438803cb),1)[0],U16(VA(0x140fd6c74)));
 }
 static void IdentifierPoolSelfTest() {
  IntPtr p=Marshal.AllocHGlobal(8193);
  try {
   byte[] slots=new byte[8193];slots[1]=1;slots[8191]=1;slots[8192]=42;Marshal.Copy(slots,0,p,slots.Length);
   string json=new JavaScriptSerializer().Serialize(IdentifierPoolAt(p.ToInt64(),1,200));
   if(!json.Contains("\"occupied_nonzero_ids\":2")||!json.Contains("\"available_nonzero_ids\":8189")||!json.Contains("\"byte_after_pool\":42"))throw new Exception("ID pool sample differs");
  } finally {Marshal.FreeHGlobal(p);}
 }
'''
 return source.replace(main,method+main).replace(field,'      "native_identifier_pool",Try(IdentifierPool),\n'+field).replace(selftest,selftest+'\n     IdentifierPoolSelfTest();')
