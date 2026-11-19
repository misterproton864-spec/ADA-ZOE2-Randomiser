typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;

typedef struct { u64 stage; u32 actor; } Binding;
#include "aumaan-bindings.h"

typedef struct {
    u64 actor;
    u32 serial, cooldown, separated;
} Track;

typedef struct {
    u64 stage, player, vtable, trace, flags, request;
    u32 spawns, heal_blocks, returns, blocked_returns;
    u64 last_stage;
    u32 last_actor, last_state, last_pending, last_motion;
    u32 shared_motion_blocks, last_blocked_state;
    Track tracks[8];
} Config;

#define U32(a,o) (*(u32*)((u8*)(a)+(o)))
#define U64(a,o) (*(u64*)((u8*)(a)+(o)))
#define F(a,o) (*(float*)((u8*)(a)+(o)))

static int finite(float f) {
    union { float f; u32 u; } bits = {f};
    return (bits.u & 0x7fffffff) < 0x7f800000;
}

static u64 encounter(void *a, Config *c) {
    if (U64(a,0) != c->vtable || ((u8*)a)[0x9b] != 10 ||
        (int)U32(a,0xc20) <= 0 || U32(a,0x16a0) || ((U32(c->flags,0) | U32(c->flags,4)) & 0x10000000)) return 0;

    const u8 *name = (const u8*)c->stage;
    u64 key = 0;
    for (u32 i = 0; i < 8 && name[i]; ++i) key |= (u64)name[i] << (8 * i);
    u32 actor = U32(a,0x78);
    for (u32 i = 0; i < sizeof(bindings)/sizeof(bindings[0]); ++i) {
        if (bindings[i].stage == key && bindings[i].actor == actor) return key;
    }
    return 0;
}

int aumaan_block_windup(void *a, Config *c, u32 state) {
    if (!encounter(a,c)) return 0;
    if (state == 20 || state == 21 || state == 24) ++c->heal_blocks;
    else ++c->shared_motion_blocks;
    c->last_blocked_state = state;
    // Block three healing branches and the two branches sharing motion 0x15
    // before their handlers write the motion, effects or arena-panel globals.
    // Native state 2 plays its own transition motion and returns to combat selection.
    // The native request routine ignores a request while BEC bit 4 is set.
    // Heal windups can run with that bit already set; replace only the unsafe
    // pending request, using the same native cancellation callback once.
    u32 pending=U32(a,0x12a4);
    if ((pending>=20 && pending<=24) || !(U32(a,0xbec)&4)) {
        if(U64(a,0x12c8))((void(*)(void*,u32))U64(a,0x12c8))(a,pending);
        U64(a,0x12c8)=0;((u8*)a)[0x129c]=1;U32(a,0x12a4)=2;
    }
    return 1;
}

static void position(void *a, const float *point) {
    // Shared native movement reads 0xb60 as gravity. Use the model matrix and
    // collision sweep endpoints instead, as in the corrected Viper helper.
    for (u32 axis = 0; axis < 12; axis += 4) {
        float value = point[axis / 4];
        F(a,0x980+axis) = value;
        F(a,0xb0+axis) = value;
        F(a,0xc0+axis) = value;
        F(a,0x1400+axis) = value;
        F(a,0x14c0+axis) = value;
        F(a,0xa90+axis) = 0;
        F(a,0xaa0+axis) = 0;
    }
    u64 model = U64(a,0x80);
    if (model) for (u32 i = 0; i < 8; ++i) U64(model,0x40+i*8) = U64(a,0x950+i*8);
}

static int outside(const float *point, const float *player) {
    float x = point[0] - player[0], y = point[1] - player[1], z = point[2] - player[2];
    return x*x + z*z > 420.0f*420.0f || y > 160.0f || y < -160.0f;
}

void aumaan_tick(void *a, Config *c, u32 post) {
    u64 stage = encounter(a,c);
    if (!stage) return;
    if (!post) {
        u32 pending=U32(a,0x12a4);
        if (pending>=20 && pending<=24) aumaan_block_windup(a,c,pending);
        return;
    }
    void *p = *(void**)c->player;
    if (!p) return;
    float *boss = (float*)((u8*)a+0x980), *player = (float*)((u8*)p+0x980);
    for (u32 axis = 0; axis < 3; ++axis) {
        if (!finite(boss[axis]) || !finite(player[axis])) return;
    }

    if (c->last_stage != stage) {
        for (u32 i = 0; i < 8; ++i) c->tracks[i].actor = 0;
        c->last_stage = stage;
    }
    u32 serial = U32(a,8);
    Track *track = &c->tracks[serial & 7];
    if (track->actor != (u64)a || track->serial != serial) {
        *track = (Track){(u64)a,serial,0,0};
        ++c->spawns;
    }
    c->last_actor = U32(a,0x78);
    c->last_state = U32(a,0x12a0);
    c->last_pending = U32(a,0x12a4);
    c->last_motion = ((u8*)a)[0x99];

    // A transient collision query must not trigger a relocation. Never snap
    // onto Jehuty or retry every few updates when the arena stays obstructed.
    if (!c->trace) return;
    u64 (*trace)(const float*,const float*,void*,u32) = (void*)c->trace;
    int bad = outside(boss,player) || trace(player,boss,0,0x100);
    if (bad) {
        if (track->separated < 90) ++track->separated;
    } else track->separated = 0;
    if (track->cooldown) --track->cooldown;
    if (track->separated < 90 || track->cooldown) return;
    static const float offsets[4][2]={{300,0},{-300,0},{0,300},{0,-300}};
    for (u32 height=0;height<2;++height) for (u32 i=0;i<4;++i) {
        float point[4]={player[0]+offsets[i][0],player[1]+(height ? -100.0f : 100.0f),player[2]+offsets[i][1],1.0f};
        if (trace(player,point,0,0x100)) continue;
        position(a,point);
        ++c->returns;
        track->separated=0;
        track->cooldown=180;
        return;
    }
    ++c->blocked_returns;
    track->cooldown=30;
}
