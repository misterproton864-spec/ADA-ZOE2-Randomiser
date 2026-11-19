typedef unsigned char u8; typedef unsigned short u16;
typedef unsigned int u32; typedef unsigned long long u64;
typedef struct {u64 actor;u32 serial,death,done,pad;} Track;
typedef struct {u64 stage,player,vtable,ground,trace;u32 enabled,magic,spawns,escapes,blocks,completed;u64 last_stage;Track tracks[128];u16 stuck[128],cooldown[128];} Config;
typedef struct {u64 stage;u32 actor,close,recover;} Binding;
#include "viper-bindings.h"
#define U32(a,o) (*(u32*)((u8*)(a)+(o)))
#define U64(a,o) (*(u64*)((u8*)(a)+(o)))
#define F(a,o) (*(float*)((u8*)(a)+(o)))
static int finite(float f){union{float f;u32 u;}x;x.f=f;return (x.u&0x7fffffff)<0x7f800000;}
static u64 stage_key(const char*s){u64 v=0;for(u32 i=0;i<8;i++){u8 ch=(u8)s[i];v|=(u64)ch<<(i*8);if(!ch)return v;}return 0;}
static const Binding* binding(void*a,Config*c){
 if(!c->enabled||c->magic!=0x56495032||U64(a,0)!=c->vtable||((u8*)a)[0x9b]!=13||(U64(a,0x1450)&0x70000000))return 0;
 u64 key=stage_key((const char*)c->stage);u32 actor=U32(a,0x78);
 for(u32 i=0;i<sizeof(bindings)/sizeof(bindings[0]);i++)if(bindings[i].stage==key&&bindings[i].actor==actor)return &bindings[i];
 return 0;
}
int viper_imported(void*a,Config*c){return binding(a,c)!=0;}
u32 viper_config_size(void){return sizeof(Config);}
static int flight(u32 s){return s==2||s==14||(s>=37&&s<=40);}
static void request(void*a,u32 state){
 if(U64(a,0x12c8))((void(*)(void*,u32))U64(a,0x12c8))(a,U32(a,0x12a4));
 U64(a,0x12c8)=0;((u8*)a)[0x129c]=1;U32(a,0x12a4)=state;U32(a,0xbec)|=4;
}
static void humanoid(void*a){
 u64 m=U64(a,0x80),p=U64(a,0x1458),mc=U64(a,0x88),pc=U64(a,0x14a0);
 if(!m||!p||!mc||!pc)return;
 *(u16*)(m+0xea)&=0xfffe;*(u16*)(p+0xea)|=1;
 *(u32*)(mc+0x10)&=~2u;*(u32*)(pc+0x10)|=2;
 U32(a,0xbe8)&=~4u;U32(a,0x14a8)=~0u;
}
static void position(void*a,float x,float y,float z){
 F(a,0x980)=x;F(a,0x984)=y;F(a,0x988)=z;
 /* 0xb60 is gravity, NOT a position cache. Preserve native physics fields.
    Synchronise the collision sweep endpoints (144d906a0) and model matrix
    using the same copy as native 14407e780, without advancing animation. */
 F(a,0xb0)=x;F(a,0xb4)=y;F(a,0xb8)=z;
 F(a,0xc0)=x;F(a,0xc4)=y;F(a,0xc8)=z;
 u64 model=U64(a,0x80);
 if(model)for(u32 i=0;i<8;i++)U64((void*)model,0x40+i*8)=U64(a,0x950+i*8);
 F(a,0x1720)=x;F(a,0x1724)=y;F(a,0x1728)=z;
 F(a,0xa90)=0;F(a,0xa94)=0;F(a,0xa98)=0;
 F(a,0xaa0)=0;F(a,0xaa4)=0;F(a,0xaa8)=0;
}
void viper_tick(void*a,Config*c,u32 post){
 const Binding*b=binding(a,c);if(!b)return;
 if(c->last_stage!=b->stage){
  for(u32 i=0;i<128;i++){c->tracks[i].actor=0;c->tracks[i].serial=0;c->tracks[i].death=0;c->tracks[i].done=0;c->stuck[i]=0;c->cooldown[i]=0;}
  c->last_stage=b->stage;
 }
 u32 serial=U32(a,8);Track*t=0,*empty=0;
 for(u32 i=0;i<128;i++){
  if(c->tracks[i].actor==(u64)a){t=&c->tracks[i];break;}
  if(!empty&&!c->tracks[i].actor)empty=&c->tracks[i];
 }
 if(!t)t=empty;if(!t)return;
 int first=t->actor!=(u64)a||t->serial!=serial;
 u32 slot=(u32)(t-c->tracks);
 if(first){t->actor=(u64)a;t->serial=serial;t->death=0;t->done=0;t->pad=U32(a,0x78);c->stuck[slot]=0;c->cooldown[slot]=0;c->spawns++;}
 /* Observe native state/callback completion; never manufacture a defeat. */
 if((int)U32(a,0xc20)<=0||U32(a,0x12a0)==13||U32(a,0x12a4)==13){
  t->death=1;
  if(U32(a,0x1430)==1&&!t->done){t->done=1;c->completed++;}
  return;
 }
 /* One initial native controller; subsequent locomotion, transformation,
    targeting and attacks belong to the game's state machine in every host.
    No position writes, forced humanoid swaps, or repeated state-zero resets. */
 if(first){
  U64(a,0x1658)=c->ground;
  U32(a,0x15d4)&=~0x202u;
 }
}
