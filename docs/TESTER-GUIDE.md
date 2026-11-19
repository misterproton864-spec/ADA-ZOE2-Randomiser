ADA Randomiser 6.4.15-local.24 - audio and diagnostics test candidate

This is a test candidate. Inhert's intermittent attacks-passing-through fault
is NOT fixed or claimed fixed. It has expanded read-only encounter observations.
In-game validation of the new audio is still required.

Changes:
- Keep normal gameplay speech separate from multichannel scene recordings.
- Vector Cannon charging cues receive mono speech no longer than their native
  cue slot. Native weapon mechanics, triggers and event timing are unchanged.
- Chaos covers 319 identified spoken ADA recordings, including 12 explicitly
  named English scene recordings omitted by the older filename filter.
- The 12 long scene recordings stay in their own 8-channel pool, with a maximum
  2:1 duration ratio. Semi-random preserves them in their authored context.
- All 26 silent native placeholders remain excluded as donors.
- Recovery now manages the 12 additional originals. Use Local.24 for Restore
  after applying a Local.24 seed; older utilities do not know those extra files.

Setup:
Extract the whole folder and keep ADA Randomiser.exe, app and runtime together.
Choose your supported Steam game folder. Close the game before Build, Apply
or Restore. Build a new seed: updating the app does not update existing seeds.
Apply only after reviewing the build. Launch ZOE2 through Steam, then Attach
at its main menu before loading a save or side mode.

Local comparison: seed zoe2-e74c794de3243cb0 with the actual Local.23 playtest
settings (Chaos ADA, 1.5x enemies, normal health, all side modes enabled).
The newly built STAGE archive and boss/enemy/reward/side-mode mappings match
the actual installed Local.23 test seed exactly. Offline preflight passed.
This is preservation evidence, not a new completed gameplay run.

Test Vector Cannon voice playback from charging through firing. Report any
still-unchanged ordinary gameplay line with the words and situation if possible.
For Inhert, run the generated runtime/CaptureEncounter.exe --watch before the
fight. Stop promptly after the fault, then use Export bug report in ADA.
The recorder reads the game; it does not change HP, positions or combat flags.

No game assets, original caches, generated game seeds, saves or diagnostics
are included in this ZIP. Each player supplies their own game installation.
The existing MIT and third-party notices are retained. GitHub publication of
this revision remains pending review and further testing.

The default profile remains %LOCALAPPDATA%\ADA Local23 C Test for compatibility. Strict full-run boss uniqueness remains unresolved.
