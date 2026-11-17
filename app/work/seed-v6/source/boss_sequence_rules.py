"""Deterministic Boss Sequence handoffs for the ten named menu encounters."""
import hashlib
import struct

from mixed_boss_catalog import payloads,assets
from boss_test_profile import (campaign_catalog,nephtis_support_assets,
    BA02_INHERT_BOUNDS,BA02_SOURCE_POSITION,CS01_INHERT_BOUNDS,CS01_SOURCE_POSITION)
from boss_variant_pool import variant_profiles,choose_profile
from boss_handoff import append_mixed_handoff
from boss_spawn_contracts import (NEPHTIS_STORY,ARDJET_STORY,VIC_VIPER_STORY,
                                  INHERT_STORY,ANUBIS_STORY,LATE_ANUBIS_STORY,decode_story_boss)
from scx_bytecode import native_calls
from randomizer_settings import BOSSES
from nephtis_encounter_support import pole_wrapper,actor_ids
from nephtis_arena_limits import apply as disable_arena_limits

STAGES=('vs_am02','vs_cs01','vs_ef02','vs_ef01','vs_vc01','vs_cy02','vs_wn01','vs_ba02')
PROTECTED=('vs_af02','vs_fr02')
FACTORIES={NEPHTIS_STORY,ARDJET_STORY,VIC_VIPER_STORY,*INHERT_STORY,*ANUBIS_STORY,*LATE_ANUBIS_STORY}
NATIVE={'vs_wn01':'Vic Viper','vs_vc01':'Nephtis','vs_ef01':'Nephtis',
        'vs_cs01':'Anubis','vs_ba02':'Nephtis','vs_cy02':'Nephtis',
        'vs_ef02':'Ardjet','vs_am02':'Anubis'}


def sound_packs(archive,stage):
    result=[]
    for group in archive.groups(stage):
        if group['folder']!='sound':continue
        data=archive.decode(group)
        result.extend(data[row['offset']:row['offset']+row['size']] for row in group['files'])
    return result


def allocation(seed,settings,profiles,variants,stages=STAGES,native=None,require_sequence=True):
    if native is None:native=NATIVE
    selected=set(settings['enabled_bosses'])
    if require_sequence and ('Inhert' not in selected or not settings.get('include_inhert_experimental')):
        raise ValueError('Boss Sequence requires selected experimental Inhert while its native two-phase encounter is retained')
    identities={BOSSES[name] for name in selected}
    if require_sequence and settings.get('repeat_rule','no_repeat')=='no_repeat' and len(identities)<len(stages)+1:
        raise ValueError('Boss Sequence cannot satisfy no-repeat with this many distinct identities')
    used={'Inhert'} if require_sequence else set();variant_used={};rows=[]
    for stage in stages:
        allowed=identities-{native[stage]}
        if not allowed:raise ValueError('No non-native Boss Sequence opponent for '+stage)
        remaining=allowed-used;reset=not remaining
        if reset:used-=allowed;remaining=allowed
        identity=min(remaining,key=lambda name:hashlib.sha256(
            (seed+'\0boss-sequence\0'+stage+'\0'+name).encode()).digest())
        used.add(identity)
        choice=dict(stage=stage,identity=identity,compatible=sorted(allowed),compatible_bag_reset=reset)
        profile=choose_profile(seed,choice,profiles,variants,variant_used)
        if profile.get('variant_label',profile['boss']) not in selected:
            raise ValueError('Boss Sequence selected a disabled variant')
        rows.append((choice,profile))
    return rows


def build(seed,stock,settings,stages=STAGES,native=None,require_sequence=True):
    import mixed_boss_catalog
    mixed_boss_catalog.ORIGINAL=stock.path
    _,_,profiles,_,_,_,_=campaign_catalog(seed)
    variants=variant_profiles(stock,profiles,include_viola_ai=settings['include_viola_ai'])
    variants={identity:[p for p in values if p['variant_label'] in settings['enabled_bosses']]
              for identity,values in variants.items()}
    options=allocation(seed,settings,profiles,variants,stages,native,require_sequence)
    native=payloads(stock,'vs_fr02')
    inhert=[(name,at) for name,data in native.items() if name.endswith('.scx')
            for at,command in native_calls(data) if command in INHERT_STORY]
    if len(inhert)!=2 or len({name for name,_ in inhert})!=1:
        raise ValueError('Boss Sequence native two-phase Inhert source changed')
    updates={};aliases={'main':{},'small':{}};sound_imports={};rows=[]
    for choice,profile in options:
        stage=choice['stage'];original=payloads(stock,stage);files=original.copy()
        sites=[(name,at,command) for name,data in original.items() if name.endswith('.scx')
               for at,command in native_calls(data) if command in FACTORIES]
        if len(sites)!=1:raise ValueError('Expected one Boss Sequence factory: '+stage)
        name,offset,command=sites[0];data=original[name]
        if profile['boss']=='Inhert' and stage in ('vs_ba02','vs_cs01'):
            source=decode_story_boss(data,offset,command)
            coords=source['arguments'][2:5]
            expected=BA02_SOURCE_POSITION if stage=='vs_ba02' else CS01_SOURCE_POSITION
            if tuple(arg['value'] for arg in coords)!=expected or any(arg['kind']!=0xc1 for arg in coords):
                raise ValueError('Boss Sequence Inhert source position changed; limits need review: '+stage)
            profile['arena_bounds']=BA02_INHERT_BOUNDS if stage=='vs_ba02' else CS01_INHERT_BOUNDS
        print('Boss Sequence seed='+seed+' arena='+stage+' assigned='+profile.get('variant_label',profile['boss'])+
              ' inhert_bounds='+str(profile.get('arena_bounds')),flush=True)
        patched,report=append_mixed_handoff(data,[dict(offset=offset,command=command,phase_index=0)],
            profile,hashlib.sha256(data).hexdigest(),suppress_nephtis_pole_visuals=True,guard_source_fades=True)
        required,textures,assetreport=assets(stock,profile)
        assetreport['motion_dependencies']=sorted(assetreport.get('motion_dependencies',[]),
            key=lambda row:(row['script'],row['library']))
        assetreport['files']=sorted(assetreport['files'],key=lambda row:row['name'])
        support=[]
        if profile['boss']=='Nephtis':
            for key,body in nephtis_support_assets(stock).items():
                required[key]=body
                if key not in {item['name'] for item in assetreport['files']}:
                    assetreport['files'].append(dict(name=key,size=len(body),sha256=hashlib.sha256(body).hexdigest(),
                        donor='fc01',role='native throwable support'))
            reserved={site['source_actor_id'] for site in report['sites']}
            for site in report['sites']:
                coords=site['coordinates'][:3]
                if any(arg['value'] is None for arg in coords):
                    raise ValueError('Boss Sequence Nephtis support needs static coordinates: '+stage)
                x,y,z=[struct.unpack('<f',struct.pack('<I',arg['value']))[0] if arg['kind']==0xc1 else float(arg['value']) for arg in coords]
                poles=[(x+dx,y,z+dz) for dx,dz in ((-800,-600),(0,-900),(800,-600),(-1000,0),(1000,0),(-800,600),(0,900),(800,600))]
                ids=actor_ids(seed+'/boss-sequence',stage,str(site['source_call']),len(poles),reserved)
                if any(struct.pack('<I',ident) in patched for ident in ids):
                    raise ValueError('Boss Sequence pole actor ID collision')
                body,info=pole_wrapper(len(patched),site['procedure_entry'],poles,ids)
                buffer=bytearray(patched)
                buffer[site['source_call']:site['source_call']+5]=b'\x87'+struct.pack('<I',info['entry'])
                buffer.extend(body);patched=bytes(buffer)
                support.append(dict(poles=info,gauntlet_cube_added=False))
                reserved.update(info['actor_ids'])
        for label,pairs in textures.items():
            for suffix,donor in pairs.items():
                key='@'+stage+'_'+suffix
                if key in aliases[label] and aliases[label][key]!=donor:
                    raise ValueError('Conflicting Boss Sequence texture alias')
                aliases[label][key]=donor
            if profile['boss']=='Nephtis':
                for suffix in ('.dat','.tbl'):
                    aliases[label]['@'+stage+'_389b56cb'+suffix]='@fc01_389b56cb'+suffix
        patched,arena_limits=disable_arena_limits(stage,name,patched,data)
        assetreport['files']=sorted(assetreport['files'],key=lambda row:row['name'])
        files.update(required);files[name]=patched+bytes((-len(patched))%16)
        donor=assetreport['donor'];native_sound=sound_packs(stock,stage)
        if not native_sound:raise ValueError('Missing Boss Sequence native sound: '+stage)
        if donor!=stage:
            packs=sound_packs(stock,donor)
            if not packs or any(len(p)%2048 or struct.unpack_from('<I',p)[0]!=1 for p in packs):
                raise ValueError('Invalid Boss Sequence donor sound: '+donor)
            sound_imports[stage]=packs
        updates[stage]={name:body for name,body in files.items() if name not in original or body!=original[name]}
        report.update(choice,file=name,variant=profile.get('variant_label',profile['boss']),
            assets=assetreport,nephtis_support=support,arena_limits=arena_limits,
            inhert_arena_bounds=profile.get('arena_bounds'),
            sound_pack_import=dict(donor=donor,added=len(sound_imports.get(stage,())),
                source_sha256=[hashlib.sha256(p).hexdigest() for p in sound_imports.get(stage,())],
                readback_verified=False),gameplay_verified=False)
        rows.append(report)
    return updates,dict(format=1,seed=seed,encounters=rows,protected=list(PROTECTED) if require_sequence else [],
                        native_inhert_phases_preserved=2,zakat_preserved=True,gameplay_verified=False),aliases,sound_imports
