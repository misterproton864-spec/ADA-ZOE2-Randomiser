import portable_paths as _portable
"""Diagnostic boss selection policy; arena fixes replace emergency exclusions."""
VIOLA='Viola AI (full rescue fight)'
VIOLA_REASON=('Viola AI grab/deletion failed in the Mars Vic Viper replacement arena on '
              'seed zoe2-267c8f3225b64dde. Its source rescue encounter is now shuffled; '
              'native player grab setup and release delay are restored; full deletion and host progression need live retesting.')

def blockers(story):
 return []

def exclusion_blockers(settings,story=()):
 if settings.get('boss_mode')!='shuffle_test':return []
 selected=set(settings.get('enabled_bosses',()))
 reasons=[]
 for row in story:
  if row.get('variant') not in selected:reasons.append('Excluded boss in '+str(row.get('stage'))+': '+str(row.get('variant')))
 return reasons
