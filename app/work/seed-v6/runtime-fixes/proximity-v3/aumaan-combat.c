typedef unsigned char u8;
typedef unsigned int u32;
typedef unsigned long long u64;

typedef struct { u64 stage; u32 actor; } Binding;
#include "aumaan-bindings.h"

typedef struct {
    u64 actor;
    u32 serial, frames, separated;
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
        (int)U32(a,0xc20) <= 0 || U32(a,0x16a0) || (int)U32(a,0x16a4) > 0 ||
        U32(a,0x14f8) || ((U32(c->flags,0) | U32(c->flags,4)) & 0x10000000)) return 0;

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
    if (state == 20) ++c->heal_blocks;
    else ++c->shared_motion_blocks;
    c->last_blocked_state = state;
    // Block the panel-heal and the two combat branches that share motion 0x15
    // before their handlers write the motion, effects or arena-panel globals.
    // Native state 2 plays its own transition motion and returns to combat selection.
    ((void(*)(void*,u32,u32))c->request)(a,2,1);
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
    if (!post) return;
    u64 stage = encounter(a,c);
    if (!stage) return;
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

    // Short attack lunges and camera cuts should finish naturally. A sustained
    // separation or blocked line of sight can trigger one recovery attempt.
    int far = outside(boss,player);
    track->separated = far ? track->separated + 1 : 0;
    ++track->frames;
    if (track->frames < 18) return;
    track->frames = 0;
    u64 (*trace)(const float*,const float*,void*,u32) = (void*)c->trace;
    if (track->separated < 12 && !trace(player,boss,0,0x100)) return;
    float point[4] = {player[0],player[1]+100.0f,player[2],1.0f};
    if (trace(player,point,0,0x100)) {
        point[1] = player[1]-100.0f;
        if (trace(player,point,0,0x100)) {
            ++c->blocked_returns;
            return;
        }
    }
    position(a,point);
    ++c->returns;
    track->separated = 0;
}
