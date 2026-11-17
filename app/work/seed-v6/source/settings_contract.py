import portable_paths as _portable
"""One settings contract for profiles, GUI and generation. No silent key loss."""
import copy,json
from pathlib import Path
from randomizer_settings import DEFAULT_WEIGHTS,DEFAULT_BOSSES,WEAPONS,enemy_weights,boss_selection,weapon_selection

DEFAULTS=dict(boss_mode='shuffle_test',repeat_rule='no_repeat',enemy_percentages=DEFAULT_WEIGHTS,
 enabled_bosses=DEFAULT_BOSSES,enabled_subweapons=list(WEAPONS),include_viola_ai=False,
 include_neith_experimental=False,randomise_enemy_levels=False,randomise_music=True,
 randomise_ada=True,metatron_subweapon_chance_percent=20,
 randomise_boss_sequence=False,randomise_survival=False,randomise_extra_missions=False,
 enemy_health_multiplier=1,boss_health_multiplier=1,
 include_inhert_experimental=False,include_spider_experimental=False,include_mosquito_experimental=False,
 valley_viper_test=False,ensure_mosquito_replacements=False)
BOOLS=tuple(k for k,v in DEFAULTS.items() if type(v) is bool)

def normalise(value=None):
 if value is None:value={}
 if not isinstance(value,dict):raise ValueError('Settings must be a JSON object')
 unknown=set(value)-set(DEFAULTS)
 if unknown:raise ValueError('Unknown settings (nothing discarded): '+', '.join(sorted(unknown)))
 out=copy.deepcopy(DEFAULTS);out.update(copy.deepcopy(value))
 for name in BOOLS:
  if type(out[name]) is not bool:raise ValueError(name+' must be true or false')
 if out['boss_mode'] not in ('native','shuffle_test'):raise ValueError('Only the audited native and shuffle_test profiles are supported')
 if out['repeat_rule'] not in ('no_repeat','compatible_exhaustion'):raise ValueError('Unknown boss repeat rule')
 chance=out['metatron_subweapon_chance_percent']
 if type(chance) is not int or not 0<=chance<=100:raise ValueError('Metatron chance must be a whole number from 0 to 100')
 for name in ('enemy_health_multiplier','boss_health_multiplier'):
  if type(out[name]) is not int or out[name] not in (1,2,3):raise ValueError(name+' must be Normal (1×), Double (2×) or Triple (3×)')
 out['enemy_percentages']=enemy_weights(out['enemy_percentages'])
 out['enabled_bosses']=boss_selection(out['enabled_bosses'],out['include_viola_ai'])
 out['enabled_subweapons']=weapon_selection(out['enabled_subweapons'])
 return out

def effective(value):
 requested=normalise(value);applied=copy.deepcopy(requested);ignored=[];blocked=[]
 from boss_qualification import exclusion_blockers
 blocked.extend(exclusion_blockers(requested))
 if requested['boss_mode']=='native':
  for key in ('enabled_bosses','include_viola_ai','include_neith_experimental','include_inhert_experimental','valley_viper_test'):
   ignored.append(dict(setting=key,reason='Original-boss mode retains every native boss encounter.'))
  applied.update(enabled_bosses=[],include_viola_ai=False,include_neith_experimental=False,include_inhert_experimental=False,valley_viper_test=False)
  if requested['randomise_boss_sequence']:
   blocked.append('Boss Sequence replacement requires the experimental boss shuffle profile.')
  if requested['boss_health_multiplier']>1:
   blocked.append('Boss health scaling currently requires boss shuffle so exact combat actor identities can be verified.')
 elif 'Inhert' in requested['enabled_bosses'] and not requested['include_inhert_experimental']:
  applied['enabled_bosses'].remove('Inhert')
  ignored.append(dict(setting='Inhert',reason='Opponent imports require the experimental Inhert opt-in; its original encounter is shuffled.'))
 if requested['randomise_boss_sequence']:
  if 'Inhert' not in requested['enabled_bosses'] or not requested['include_inhert_experimental']:
   blocked.append('Boss Sequence currently needs Inhert selected and its experimental opponent opt-in to preserve both native phases.')
  if requested['repeat_rule']=='no_repeat':
   blocked.append('Boss Sequence needs compatible-exhaustion repeats; there are more fights than distinct boss identities.')
 from boss_qualification import VIOLA,VIOLA_REASON
 # The explicit Viola checkbox now enables its native rescue variant for testing.
 if not requested['enabled_subweapons']:
  applied['metatron_subweapon_chance_percent']=0
  ignored.append(dict(setting='metatron_subweapon_chance_percent',reason='Empty weapon pool: native healing retained, no random weapon grant.'))
 if requested['valley_viper_test']:
  applied['valley_viper_test']=False
  ignored.append(dict(setting='valley_viper_test',reason='Vic Viper movement and clone-death fixes now apply automatically; the old Valley-only hook is retired.'))
 if requested['include_spider_experimental']:
  applied['include_spider_experimental']=False
  ignored.append(dict(setting='include_spider_experimental',reason='Spider replacement lifecycle remains unqualified. The saved request has 0% weight; native objectives stay protected.'))
 mosquito=requested['enemy_percentages']['Mosquito / swarm']
 if mosquito and not requested['include_mosquito_experimental']:
  blocked.append('Positive Mosquito weight requires the finite-swarm experimental opt-in. The requested weight was retained.')
 if not mosquito or not requested['include_mosquito_experimental']:
  applied['include_mosquito_experimental']=False
  applied['ensure_mosquito_replacements']=False
  if requested['ensure_mosquito_replacements']:
   ignored.append(dict(setting='ensure_mosquito_replacements',reason='Requires a positive Mosquito weight and the finite-swarm opt-in. OFF/0% is respected.'))
 if requested['include_neith_experimental'] and requested['boss_mode']!='native':blocked.append('Neith original-AI port is unavailable.')
 if applied['include_inhert_experimental']:
  if 'Inhert' not in applied['enabled_bosses']:raise ValueError('Experimental Inhert requires Inhert enabled in the opponent pool')
  # Explicit diagnostic opt-in: source two-phase AI/callbacks are retained.
  # Gameplay in imported arenas is unverified; the user is testing these pairs.
 return dict(format=1,requested=requested,applied=applied,ignored=ignored,blocked=blocked,gameplay_verified=False)

def save_profile(path,value):
 from install_state import save
 save(Path(path),dict(format=2,settings=normalise(value)))

def load_profile(path):
 from install_state import read
 data=read(path)
 if not isinstance(data,dict):raise ValueError('Invalid settings profile')
 return normalise(data.get('settings',data))
