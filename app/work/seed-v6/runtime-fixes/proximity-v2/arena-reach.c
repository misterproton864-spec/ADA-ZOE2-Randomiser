typedef unsigned char u8;typedef unsigned int u32;typedef unsigned long long u64;
typedef struct {u64 stage,player,vtable,ground;u32 actor_id,enabled;u64 tracked;u32 serial,spawns,blocks,tethers,recoveries,pad;} Config;
#define U32(a,o) (*(u32*)((u8*)(a)+(o)))
#define U64(a,o) (*(u64*)((u8*)(a)+(o)))
#define F(a,o) (*(float*)((u8*)(a)+(o)))
static int finite(float f){union{float f;u32 u;}x;x.f=f;return (x.u&0x7fffffff)<0x7f800000;}
static int flight(u32 s){return s==2||s==14||(s>=37&&s<=40);}
static void request(void*a,u32 state){
 if(U64(a,0x12c8))((void(*)(void*,u32))U64(a,0x12c8))(a,U32(a,0x12a4));
 U64(a,0x12c8)=0;((u8*)a)[0x129c]=1;U32(a,0x12a4)=state;U32(a,0xbec)|=4;
}
static void position(void*a,float x,float y,float z){
 F(a,0x980)=x;F(a,0x984)=y;F(a,0x988)=z;
 F(a,0xb60)=x;F(a,0xb64)=y;F(a,0xb68)=z;
 F(a,0xaa0)=0;F(a,0xaa4)=0;F(a,0xaa8)=0;
}
void reach_tick(void*a,Config*c,u32 post){
 if(!c->enabled)return;
 const char*s=(const char*)c->stage;
 int viper=s[0]=='c'&&s[1]=='a'&&s[2]=='0'&&s[3]=='2'&&!s[4];
 int aumaan=s[0]=='f'&&s[1]=='a'&&s[2]=='0'&&s[3]=='1'&&!s[4];
 if(!viper&&!aumaan)return;
 if(U64(a,0)!=c->vtable||U32(a,0x78)!=c->actor_id)return;
 if(((u8*)a)[0x9b]!=(viper?13:10)||(int)U32(a,0xc20)<=0)return;
 if(viper&&(U32(a,0x12a0)==13||U32(a,0x12a4)==13||(U64(a,0x1450)&0x70000000)))return;
 if(aumaan&&(U32(a,0x16a0)!=0||(int)U32(a,0x16a4)>0||U32(a,0x14f8)!=0))return;
 void*p=*(void**)c->player;if(!p)return;
 float px=F(p,0x980),py=F(p,0x984),pz=F(p,0x988);
 float x=F(a,0x980),y=F(a,0x984),z=F(a,0x988);
 if(!finite(px)||!finite(py)||!finite(pz)||!finite(x)||!finite(y)||!finite(z))return;
 float dx=x-px,dz=z-pz,dy=y-py,d2=dx*dx+dz*dz;
 if(!finite(d2)||!finite(dy))return;
 int first=c->tracked!=(u64)a||c->serial!=U32(a,8);
 if(first){c->tracked=(u64)a;c->serial=U32(a,8);c->spawns++;}
 if(viper){
  // Phase-two humanoid combat uses the native ground controller. Only ca02.
  U64(a,0x1658)=c->ground;U32(a,0x15d4)=(U32(a,0x15d4)&~0x202u)|1;
  if((U32(a,0xbe8)&4)!=0){
   u64 m=U64(a,0x80),model=U64(a,0x1458),mc=U64(a,0x88),pc=U64(a,0x14a0);
   if(m&&model&&mc&&pc){
    *(unsigned short*)(m+0xea)&=0xfffe;*(unsigned short*)(model+0xea)|=1;
    *(u32*)(mc+0x10)&=~2u;*(u32*)(pc+0x10)|=2;U32(a,0xbe8)&=~4u;U32(a,0x14a8)=~0u;
    c->recoveries++;request(a,0);
   }
  }
  if(first||flight(U32(a,0x12a4))||flight(U32(a,0x12a0))){request(a,0);c->blocks++;}
 }
 float limit=viper?650.0f:500.0f;
 if(first||d2>limit*limit||dy>180.0f||dy< -180.0f){
  if(viper){
   if(d2>0.001f){float scale=400.0f/__builtin_sqrtf(d2);x=px+dx*scale;z=pz+dz*scale;}
   else{x=px;z=pz+400.0f;}
   y=py;
  }else{
   // Put Aumaan on Jehuty's side of any wall, directly above the reachable
   // player position. No interpolation through an unqualified arena boundary.
   x=px;y=py+120.0f;z=pz;
  }
  position(a,x,y,z);c->tethers++;
  if(viper){F(a,0x1720)=x;F(a,0x1724)=y;F(a,0x1728)=z;}
  else{F(a,0x1400)=x;F(a,0x1404)=y;F(a,0x1408)=z;}
 }
 // Clamp the native destination, so AI cannot immediately flee again.
 u32 target=viper?0x1550:0x18b0;
 dx=F(a,target)-px;dy=F(a,target+4)-py;dz=F(a,target+8)-pz;d2=dx*dx+dz*dz;
 if(!finite(d2)||!finite(dy)||d2>limit*limit||dy>180||dy< -180){
  F(a,target)=x;F(a,target+4)=y;F(a,target+8)=z;
 }
 if(aumaan){
  // The original update tests its previous combat position against Aumaan's
  // original arena range. Keep that cache beside the replacement as well.
  F(a,0x14c0)=x;F(a,0x14c4)=y;F(a,0x14c8)=z;
 }
}
