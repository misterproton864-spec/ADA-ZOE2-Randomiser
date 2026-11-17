# ADA Beta Tester Edition — experimental candidate

ADA is an unofficial ZOE2 M∀RS randomiser for Windows. This ZIP contains the randomiser program and its supporting files. It contains no ZOE2 game files, game executable, voices or saves. You must use your own legitimate Steam installation.

**Before a long run:** Triple boss health can make health bars appear wrong. Vic Viper and Inhert can have AI problems in shuffled arenas. Anubis and Aumaan Anubis can occasionally get stuck. Randomised clone fights can have visual or AI problems, especially if two copies of the same boss appear. These fights may block progression. Read [Known Issues](KNOWN-ISSUES.md) and keep a seed you can restore.

## Supported installation

The tool checks the game files before building or applying a seed. The supported `Zoe2Mars.exe` has SHA-256 `b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92`. A different executable is rejected. The first launch asks you to select the folder containing `Zoe2Mars.exe`.

## Install and play

1. Extract the entire ZIP to a folder you can write to. Keep `ADA Randomiser.exe`, `app`, and `runtime` together.
2. Close ZOE2. Launch **ADA Randomiser.exe** and choose your game folder if asked.
3. Select a seed and options. Use **REROLL + Build** for a new random seed, or enter an earlier seed to reproduce its assignments. Review [Known Issues](KNOWN-ISSUES.md) before including Vic Viper or Anubis 2.
4. Click **Build selected seed**. The tool validates the original installation, keeps a checked original-file cache, generates encounter mappings and checks the finished build. A failed build does not install a seed.
5. Click **Apply build**. The installer checks the current game and backup state again, backs up files, installs the seed, and verifies hashes. Keep ZOE2 closed during this step.
6. Start the game through Steam. At the game's **main menu, before loading a save or mode**, click **Attach at main menu** in ADA. This starts the seed's runtime helpers, including health scaling when selected.
7. To undo a seed, close ZOE2 and click **Restore previous** or **Restore game to vanilla**. Review the completion message before launching again.

Do not copy `STAGE.DAT` or atlas files from another installation into the beta ZIP. Each tester builds a seed from their own supported game installation.
ADA keeps its settings, original-file cache, builds and logs under `%LOCALAPPDATA%\ADA Beta Tester Edition` by default. The beta does not require an F: drive.

## Reports

Record the seed, options, mode, stage and boss names when something goes wrong. Click **Export bug report** in ADA to make a redacted diagnostic ZIP containing logs and mappings. The export excludes game assets, saves and crash dumps. Use [the report template](BUG-REPORT-TEMPLATE.md) for your description. If the game stays open during a stuck encounter, run **Capture stuck encounter.cmd** in the applied seed folder before closing it.

The Local.22 health and Vic Viper behaviour require gameplay testing. See [Known Issues](KNOWN-ISSUES.md) before starting a long run. The futuristic ADA interface and custom voice system are future work and are not included here.
