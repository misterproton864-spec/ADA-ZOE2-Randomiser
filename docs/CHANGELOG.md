# ADA Local.22 — development changelog

- Boss health display: keep display values within the signed 16-bit range while preserving the combat HP multiplier. If combat HP falls and the display current stays unchanged for two monitor polls, update the display to the combat fraction. Native display changes take priority. Log shuffled bosses' combat and display HP when combat HP changes.
- Bug-report export: use the actual Local.22 version and include side-mode verification, attachment and health-target diagnostics where available.
- Keep the Local.21 boss, enemy, mode, audio, Inhert and clone-pair code unchanged. Vic Viper v7 remains in place because the latest Valley playtest still reports stationary AI and its cause has not been isolated.

The health display change passed private-memory tests. A full regression seed build verifies script/resource and progression contracts. Neither result proves the HUD appears correctly in gameplay. The latest user playtest confirmed health visibly decreased for Inhert in Compressed Space with Jehuty Ver. 2; other bosses still need observation.
