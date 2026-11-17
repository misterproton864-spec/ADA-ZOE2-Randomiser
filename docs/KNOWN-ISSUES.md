# Known issues — ADA Beta Tester Edition

This is an experimental beta candidate. Offline validation does not establish that every boss fight can be completed.

## Vic Viper in the Valley Nephtis arena

The latest Local.21 playtest reported that Vic Viper spawned but stopped moving and acting. Instant teleporting appears resolved. His health did not visibly decrease; the playtest does not establish whether damage was rejected or the health bar failed to update. This fight may block Story progression. For a run where progression matters, deselect **Vic Viper** in the boss options. You can enable him for a focused test and capture a stuck encounter. The tool does not remove him silently.

## Triple boss health bars

Local.21 bars were visually corrupted or failed to decrease in some encounters with Triple boss health. The user confirmed health visibly decreased for Inhert in Compressed Space with Jehuty Ver. 2, but has not confirmed every boss. Local.22 adds a signed-range display cap and a cautious stale-display correction. Combat HP and display HP are now logged separately in `health-multiplier.log` for shuffled bosses. The new display behaviour is not yet verified in gameplay. If a bar looks wrong, record whether the boss can still be damaged and defeated; test the same seed with **Normal** boss health as a control. For a long uninterrupted run, use Normal boss health until the Triple display is verified in the encounters you intend to play.

## Inhert AI in shuffled arenas

Inhert was completed in Compressed Space in a recent playtest, including a visible decrease in health. In other shuffled arenas, his teleport or countdown behaviour may still leave him unreachable or stalled. If that happens, capture the encounter while the game is open and report the arena and phase. For Story Mode, deselect **Inhert** if an untested placement would block progression. Boss Sequence currently requires Inhert; avoid that mode for an uninterrupted run if you cannot accept this risk.

## Anubis and Aumaan Anubis can stall

Anubis and Aumaan Anubis occasionally get stuck in shuffled encounters. Aumaan's healing behaviour has had targeted repairs, but this latest report means a stall remains possible. Record the exact boss variant, stage, phase and whether the boss can still be damaged. For an uninterrupted run, deselect the affected variants until they pass a live retest.

## Randomised clone fights

Phobos clone fights can show AI or graphical problems with certain boss pairs. Earlier builds showed severe corruption with two Ardjets. Local.22's generator requires two distinct boss identities for the two clone slots; the regression seed selects Ardjet and Vic Viper. If two copies of the same boss appear, treat that as a bug in the current build and report the seed, both visible bosses, and the exported mapping. Even a distinct pair needs a live completion check.

## Anubis 2 in Boss Sequence

A Local.20 Boss Sequence run crashed while fighting Anubis 2 in the Nephtis arena before Viola AI (`vs_ef01`). The captured game dump shows a null object read during combat, but the missing object's cause remains unknown. The latest playtest reported no major crash, which does not prove this placement is stable. For an uninterrupted Boss Sequence run, deselect **Anubis 2** until this encounter has passed another live test. Report any repeat with the selected seed and mode path.

## Other limits

- A later Local.22 playtest reported Ardjet crashing immediately after defeat in the Viola AI host arena. The unfinished Local.23 transition candidate is not included in this release.
- A later Local.22 playtest reported Vic Viper jerking or moving toward Jehuty in Inhert's indoor arena rather than maintaining the requested long range.

- Music, ADA dialogue and combat sound randomisation passed offline checks; audible playback varies by game situation and needs tester feedback.
- Boss-specific mechanics and transitions in uncommon shuffled arenas remain experimental. Export a bug report for a softlock, missing boss, or failed victory transition.
- The tool supports only the pinned Steam Windows executable stated in the README. It rejects other game versions rather than applying an unknown patch.
