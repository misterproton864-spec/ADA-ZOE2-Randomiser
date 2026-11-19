typedef unsigned char u8;typedef unsigned int u32;typedef unsigned long long u64;
typedef struct {u64 stage,vtable;u32 enabled,magic;} Config;
typedef struct {u64 stage;u32 actor;} Binding;
#include "inhert-bindings.h"
int inhert_imported(void*a,Config*c){
 if(!c->enabled||c->magic!=0x494e4831||*(u64*)a!=c->vtable||((u8*)a)[0x9b]!=12||*(u32*)((u8*)a+0x14e4)!=0||(*(u32*)((u8*)a+0x14e0)&0x1000000))return 0;
 const u8*s=(const u8*)c->stage;u64 key=0;u32 i=0;for(;i<8&&s[i];++i)key|=(u64)s[i]<<(8*i);if(i==8)return 0;
 u32 id=*(u32*)((u8*)a+0x78);
 for(i=0;i<sizeof(bindings)/sizeof(bindings[0]);++i)if(bindings[i].stage==key&&bindings[i].actor==id)return 1;
 return 0;
}
