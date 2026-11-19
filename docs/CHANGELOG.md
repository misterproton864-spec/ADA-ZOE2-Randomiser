# Local.24 test candidate

- Repair unsafe gameplay/cinematic speech assignments and Vector Cannon cue lengths.
- Include twelve omitted, explicitly identified English ADA scene recordings in Chaos.
- Extend original-file verification and recovery for those twelve files.
- Add read-only Inhert combat/body/transform observations; collision bug remains open.
- Preserve the fixed-seed Story and side-mode archive and mappings.

Seven focused audio/catalogue tests and isolated twelve-file recovery/rollback
checks pass. Real seed generation, preflight and startup/package checks are
recorded in build-verification.json. In-game voice playback remains unverified.

## Local.23 changes carried forward

local.23 experimental candidates

- Ardjet/Viola host: remove an inappropriate ordinary-donor rescue observer and
  extra rescue transition effect while retaining native host progression.
- Foreign Inhert: phase-1 script and zero-HP defeat gate; native phases retained.
- Foreign Aumaan: cancel pending heal/panel transitions and block related states.
- Foreign Vic Viper: initialise once, preserve native range/movement/attacks;
  remove repeated forced-mode resets and helper recovery snap.
- Compact seed storage, compatible music variation, ADA modes and optional
  experimental regular-enemy density work are carried forward.

Read START HERE.txt for limitations and test priorities. No live game validation.

18 November: corrected two cached-original ADA fingerprints and refreshed
full-decode audibility metadata for clean Steam installations.

## Earlier history

# ADA Local.22 â€” development changelog

- Boss health display: keep display values within the signed 16-bit range while preserving the combat HP multiplier. If combat HP falls and the display current stays unchanged for two monitor polls, update the display to the combat fraction. Native display changes take priority. Log shuffled bosses' combat and display HP when combat HP changes.
- Bug-report export: use the actual Local.22 version and include side-mode verification, attachment and health-target diagnostics where available.
- Keep the Local.21 boss, enemy, mode, audio, Inhert and clone-pair code unchanged. Vic Viper v7 remains in place because the latest Valley playtest still reports stationary AI and its cause has not been isolated.

The health display change passed private-memory tests. A full regression seed build verifies script/resource and progression contracts. Neither result proves the HUD appears correctly in gameplay. The latest user playtest confirmed health visibly decreased for Inhert in Compressed Space with Jehuty Ver. 2; other bosses still need observation.
