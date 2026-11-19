import portable_paths as _portable
"""Campaign boss shuffle: only Zakat stays native; exclusions cover original fights."""
import hashlib
import json
import struct
from archive_tools import L
from mixed_boss_catalog import catalog,payloads,assets
from boss_variant_pool import variant_profiles,choose_profile
from boss_handoff import append_mixed_handoff
from randomizer_settings import BOSSES,boss_selection

STAGES=('ca02','ba02','ba03','wn01','cy02','vc01','ef01','ef02g','fr02','cs01','fa01','fr04g','am01g','am02')
PROTECTED_STAGES=('af02',)
BOSS_HELPERS=frozenset(('ViperCombatAdapter.exe','FakeAumaanReachAdapter.exe','AumaanArenaGuard.exe','ViperArenaGuard.exe','FakeAnubisDamageAdapter.exe',
                        'FakeAnubisDamageTableAdapter.exe','InhertPhaseAdapter.exe','NephtisFullHealthAdapter.exe','NephtisDialogueAdapter.exe'))
# Native Inhert starts with fr02 limits: X/Z +/-2200 and Y -5500..-1000.
# The cs01 source boss spawns at (0, 800, -500), outside that Y interval.
# Use the factory's native D1 limit option for both imported combat phases.
CS01_INHERT_BOUNDS=(-600.0,400.0,-1100.0,600.0,1200.0,100.0)
CS01_SOURCE_POSITION=(0,1145569280,3287941120)
# The BAHRAM Nephtis host starts at (0, 300, -0). Keep both Inhert phases
# near the central combat floor instead of using fr02's distant Y limits.
BA02_INHERT_BOUNDS=(-600.0,100.0,-600.0,600.0,600.0,600.0)
BA02_SOURCE_POSITION=(0,1133903872,2147483648)
# Both Phobos clone slots are centred at X=-8290, Z=-5690. The native
# fr02 Inhert limits are centred around the origin and exclude this arena.
PHOBOS_INHERT_BOUNDS=(-10000.0,-500.0,-7400.0,-6500.0,1800.0,-3900.0)
PHOBOS_SOURCE_XZ=(3321989120,3316764672)

def stages(settings):return STAGES
def boss_helpers(settings,rows=()):return set(BOSS_HELPERS)

def nephtis_support_assets(stock):
    native=payloads(stock,'fc01')
    return {name:native[name] for name in ('389b56cb.tex','91da1b63.mdz')}


def compatible(stage,enabled,include_inhert=False,valley_test=False):
    selected={BOSSES[name] for name in enabled}
    allowed=selected&{'Ardjet','Nephtis','Anubis','Vic Viper'}
    if include_inhert:allowed |= selected&{'Inhert'}
    return allowed

def campaign_catalog(seed):
    """Extend the pinned source catalog with the formerly protected rescue fight."""
    result=list(catalog(seed));archive,_,profiles,sources=result[:4]
    from boss_spawn_contracts import decode_story_boss,ARDJET_STORY
    row=next(r for r in json.loads((L/'additional-verified-boss-contracts.json').read_text()) if r['stage']=='ef02g')
    data=payloads(archive,'ef02g')[row['file']]
    if hashlib.sha256(data).hexdigest()!=row['source_sha256']:raise ValueError('Rescue source hash differs')
    contract=decode_story_boss(data,row['offset'],ARDJET_STORY)
    if contract['variant']!=1:raise ValueError('Rescue source variant differs')
    sources['ef02g']=[dict(data=data,offset=row['offset'],command=ARDJET_STORY,file=row['file'],contract=contract)]
    return tuple(result)

def schedule(seed,enabled,include_inhert=False,valley_test=False):
    selected={BOSSES[name] for name in boss_selection(enabled,include_viola_ai='Viola AI (full rescue fight)' in enabled)}
    used=set();cycle=0;rows=[]
    for stage in stages(dict(valley_viper_test=valley_test)):
        allowed=compatible(stage,enabled,include_inhert,valley_test)
        if not allowed:raise ValueError('No enabled compatible bosses for '+stage)
        remaining=allowed-used;reset=not remaining
        if reset:used-=allowed;remaining=allowed;cycle+=1
        identity=min(remaining,key=lambda key:hashlib.sha256((seed+'\0boss-test\0'+stage+'/'+key).encode()).digest())
        used.add(identity)
        rows.append(dict(stage=stage,identity=identity,compatible=sorted(allowed),cycle=cycle,compatible_bag_reset=reset))
    return rows


def build(seed,stock,updates,enabled,include_viola=False,include_inhert=False,valley_test=False):
    import mixed_boss_catalog
    mixed_boss_catalog.ORIGINAL=stock.path
    _,_,profiles,sources,_,_,_=campaign_catalog(seed)
    variants=variant_profiles(stock,profiles,include_viola_ai=include_viola)
    variants={identity:[v for v in rows if v['variant_label'] in enabled] for identity,rows in variants.items()}
    used={};rows=[];aliases={'main':{},'small':{}}
    for allocation in schedule(seed,enabled,include_inhert,valley_test):
        stage=allocation['stage'];source=sources[stage]
        files=updates.setdefault(stage,payloads(stock,stage).copy())
        names={s['file'] for s in source}
        if len(names)!=1:raise ValueError('Ambiguous native boss source script')
        name=names.pop();data=files[name]
        profile=choose_profile(seed,allocation,profiles,variants,used)
        if stage in ('cs01','ba02') and profile['boss']=='Inhert':
            if len(source)!=1:
                raise ValueError('Bounded Inhert arena requires one source spawn: '+stage)
            coords=source[0]['contract']['arguments'][2:5]
            expected=CS01_SOURCE_POSITION if stage=='cs01' else BA02_SOURCE_POSITION
            if tuple(arg['value'] for arg in coords)!=expected or any(arg['kind']!=0xc1 for arg in coords):
                raise ValueError('Bounded Inhert source position changed; limits need review: '+stage)
            profile['arena_bounds']=CS01_INHERT_BOUNDS if stage=='cs01' else BA02_INHERT_BOUNDS
        print('Boss setup seed='+seed+' arena='+stage+' assigned='+profile.get('variant_label',profile['boss'])+' point=script-and-resources',flush=True)
        sites=[dict(offset=r['offset'],command=r['command'],phase_index=i) for i,r in enumerate(source)]
        clone_safety=None;site_profiles=None
        if stage=='am01g':
            if len(source)!=2 or len({r['file'] for r in source})!=1:
                raise ValueError('Phobos clone source changed; independent assignments need review')
            if profile.get('full_viola_ai'):
                profile=next(p for p in variants['Ardjet'] if p['variant_label']=='Ardjet')
            remaining=compatible(stage,enabled,include_inhert,valley_test)-{allocation['identity']}
            if not remaining:raise ValueError('Phobos clones need two distinct enabled boss identities')
            second=min(remaining,key=lambda identity:hashlib.sha256((seed+'\0phobos-second\0'+identity).encode()).digest())
            other=choose_profile(seed,dict(stage=stage+'/clone2',identity=second),profiles,variants,used)
            if other.get('full_viola_ai'):
                other=next(p for p in variants['Ardjet'] if p['variant_label']=='Ardjet')
            for source_site in source:
                coords=source_site['contract']['arguments'][2:6]
                if (coords[0]['kind'],coords[0]['value'],coords[2]['kind'],coords[2]['value'])!=(0xc1,PHOBOS_SOURCE_XZ[0],0xc1,PHOBOS_SOURCE_XZ[1]):
                    raise ValueError('Phobos clone source position changed; Inhert limits need review')
            for chosen in (profile,other):
                if chosen['boss']=='Inhert':chosen['arena_bounds']=PHOBOS_INHERT_BOUNDS
            site_profiles={sites[0]['offset']:profile,sites[1]['offset']:other}
            clone_safety=dict(reason='Each Phobos clone has its own seeded boss; native Ardjet shared state permits only one Ardjet',
                              identities=[allocation['identity'],second],
                              variants=[p.get('variant_label',p['boss']) for p in (profile,other)],
                              source_sites=2,duplicate_bosses=False,gameplay_verified=False)
        patched,report=append_mixed_handoff(data,sites,profile,hashlib.sha256(data).hexdigest(),
                                          suppress_nephtis_pole_visuals=True,guard_source_fades=True,
                                          site_profiles=site_profiles)
        required,textures,assetreport=assets(stock,profile)
        if site_profiles:
            second_assets,second_textures,second_report=assets(stock,other)
            for key,body in second_assets.items():
                if key in required and required[key]!=body:raise ValueError('Phobos boss resource collision: '+key)
                required[key]=body
            known={r['name']:r for r in assetreport['files']}
            for row in second_report['files']:
                if row['name'] in known and known[row['name']]['sha256']!=row['sha256']:
                    raise ValueError('Phobos boss resource provenance collision: '+row['name'])
                known[row['name']]=row
            assetreport['files']=list(known.values())
            assetreport['motion_dependencies']+=second_report.get('motion_dependencies',[])
            assetreport['donors']=[assetreport['donor'],second_report['donor']]
            for label,pairs in second_textures.items():
                for suffix,donor in pairs.items():
                    if suffix in textures[label] and textures[label][suffix]!=donor:
                        raise ValueError('Phobos boss texture alias collision: '+suffix)
                    textures[label][suffix]=donor
        assetreport['motion_dependencies']=sorted(assetreport.get('motion_dependencies',[]),key=lambda r:(r['script'],r['library']))
        support=[]
        if any(site['replacement_identity']=='Nephtis' for site in report['sites']):
            from nephtis_encounter_support import pole_wrapper,actor_ids
            for key,body in nephtis_support_assets(stock).items():
                required[key]=body
                if key not in {r['name'] for r in assetreport['files']}:
                    assetreport['files'].append(dict(name=key,size=len(body),sha256=hashlib.sha256(body).hexdigest(),donor='fc01',role='native throwable support'))
            reserved={s['source_actor_id'] for s in report['sites']}
            for site in (row for row in report['sites'] if row['replacement_identity']=='Nephtis'):
                dynamic=stage=='am01g' and site['coordinates'][1]['value'] is None
                x,y,z=[None if dynamic and i==1 else struct.unpack('<f',struct.pack('<I',a['value']))[0] if a['kind']==0xc1 else float(a['value']) for i,a in enumerate(site['coordinates'][:3])]
                poles=[(x+dx,y,z+dz) for dx,dz in ((-800,-600),(0,-900),(800,-600),(-1000,0),(1000,0),(-800,600),(0,900),(800,600))]
                ids=actor_ids(seed+'/bosses',stage,str(site['source_call']),len(poles),reserved)
                if any(struct.pack('<I',ident) in patched for ident in ids):raise ValueError('Pole actor identifier collision')
                if dynamic:
                    from dynamic_nephtis_poles import height_expression,pole_wrapper as dynamic_wrapper
                    body,pole_info=dynamic_wrapper(len(patched),site['procedure_entry'],poles,ids,height_expression(data,site['source_call']))
                else:body,pole_info=pole_wrapper(len(patched),site['procedure_entry'],poles,ids)
                updated=bytearray(patched);updated[site['source_call']:site['source_call']+5]=b'\x87'+struct.pack('<I',pole_info['entry']);updated.extend(body)
                patched=bytes(updated)
                info=dict(poles=pole_info,gauntlet_cube_added=False)
                support.append(info)
                reserved.update(info['poles']['actor_ids'])
        for label,pairs in textures.items():
            for suffix,donor in pairs.items():aliases[label]['@'+stage+'_'+suffix]=donor
            if any(site['replacement_identity']=='Nephtis' for site in report['sites']):
                for suffix in ('.dat','.tbl'):aliases[label]['@'+stage+'_389b56cb'+suffix]='@fc01_389b56cb'+suffix
        from nephtis_arena_limits import apply as disable_arena_limits
        patched,arena_limits=disable_arena_limits(stage,name,patched,source[0]['data'])
        report['arena_limits']=arena_limits
        if arena_limits:
            report['original_prefix_preserved']=False
            report['output_sha256']=hashlib.sha256(patched).hexdigest()
        files.update(required);files[name]=patched+bytes((-len(patched))%16)
        if stage=='vc01':
            from nephtis_arena_geometry import FILE as geometry_file,apply as remove_perimeter
            files[geometry_file],report['arena_geometry']=remove_perimeter(files[geometry_file])
        report.update(allocation,file=name,assets=assetreport,variant=profile.get('variant_label',profile['boss']),
                      inhert_arena_bounds=profile.get('arena_bounds'),clone_safety=clone_safety,
                      sound_donors=assetreport.get('donors',[assetreport['donor']]),
                      nephtis_support=support,gameplay_verified=False)
        rows.append(report)
        print('Boss test',stage,'->',report['variant'],flush=True)
    return rows,aliases
