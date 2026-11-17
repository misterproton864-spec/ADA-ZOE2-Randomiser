# ADA - The ZOE2 MARS Randomiser

An unofficial Windows randomiser for **ZONE OF THE ENDERS THE 2nd RUNNER: MARS**.

**Current version: 6.4.15-local.22, experimental beta.** Boss AI, health-bar displays and victory transitions can still fail. This is a testing release; read the [known issues](docs/KNOWN-ISSUES.md) before starting a run.

## Download and play

Open this repository's **Releases** page and download the **ADA Beta Tester Edition ZIP** attached to the Local.22 pre-release. GitHub's automatically generated **Source code** ZIP is for developers and does not include the bundled Python runtime.

1. Extract the entire tester ZIP. Keep `ADA Randomiser.exe`, `app` and `runtime` together.
2. Close ZOE2, run **ADA Randomiser.exe**, and select your own Steam game folder.
3. Choose a seed and options, build it, review the result, then apply it while the game is closed.
4. Start the game through Steam. At its main menu, use **Attach at main menu** in ADA before loading a save or game mode.
5. Close the game before using **Restore previous** or **Restore game to vanilla**.

See the [full tester guide](docs/TESTER-GUIDE.md) for setup, storage and reporting details. Requires Windows x64, .NET Framework 4.8 and the supported Steam game installation. Testers do not need to install Python.

## What it randomises

- Story enemies, boss assignments and subweapon rewards, with configurable seed settings.
- Optional enemy levels and health settings.
- Music and ADA dialogue using compatibility checks.
- Boss Sequence/Boss Battles, Survival and Extra Missions through their respective options. Offline generation checks cover these modes; live behaviour still needs testing.

Bosses stay in the boss pool. Zakat and Vector Cannon retain their established protections. Special encounter mechanics and uncommon boss placements remain experimental. Neith/ZOE1 ports and unfinished Local.23 changes are outside this release.

## Known limits

Vic Viper can stop acting in the Valley; Inhert, Anubis and Aumaan Anubis can stall in shuffled arenas. Triple boss health can produce misleading HUD bars. Clone fights can show graphical or AI problems. A Local.22 report also described an Ardjet post-victory crash in the Viola AI arena; its fix is outside this release.

The tool validates the supported executable and input files. It rejects unknown versions. Local.22 passed recorded offline generation and package checks; that does **not** establish a clean gameplay run or second-PC compatibility.

## Report a problem or contribute

Use **Issues** for bugs and include the seed, options, mode, host arena, replacement boss, Attach status and what happened. Use ADA's **Export bug report** when useful; review the export before posting. Do not upload game assets, saves or crash dumps publicly.

Developers: read [BUILDING.md](BUILDING.md), [CONTRIBUTING.md](CONTRIBUTING.md) and the [source map](docs/SOURCE-MAP.md). This repository is separate from Cronos and has its own history and releases.

## Licence and credits

ADA's original code is available under the [MIT licence](LICENSE). The archive reader adapts Missingno_force / Missingmew's tools-mgs algorithms and retains their separate notice. Bundled Python, Tcl/Tk and Microsoft runtime components retain their own terms. See [third-party notices](THIRD-PARTY-NOTICES.txt).

No Konami game executable, archive, voice, music, model, texture or save is included. Each tester supplies their own supported game installation. This project is not affiliated with or endorsed by Konami.
