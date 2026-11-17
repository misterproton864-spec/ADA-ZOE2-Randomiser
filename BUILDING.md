# Running and packaging Local.22

## Run the source on Windows

Use 64-bit Python 3.12 with Tcl/Tk installed. The sealed beta used Python 3.12.14. .NET Framework 4.8 is required for C# helpers compiled during seed generation.

From this checkout:

```powershell
python tools/audit_repository.py
python app/main.py --self-test
python app/main.py
```

The self-test opens and closes a hidden Tk window, checks core imports and prints the version. It does not build or apply a seed, attach to a game or qualify gameplay. It creates only the app's user-state directories; set `ZOE2_BETA_HOME` to an isolated folder if you already use the tester edition.

Do not run multiple copies against the same app state. Original-file capture and seed generation require the supported game installation. Read the tester guide before applying changes.

## Make a portable package

The packaging script reuses only the Python/Tk runtime and launcher from the pinned, asset-free Local.22 tester ZIP, then copies the app from this checkout and adds the public licence/notices. No game installation or game files are required for packaging.

```powershell
python tools/package_release.py --baseline-zip "F:\ZOE2-Randomiser\releases\ADA-Beta-Tester-Edition-6.4.15-local.22-experimental.zip" --output "F:\ZOE2-Randomiser\releases\ADA-Beta-Tester-Edition-6.4.15-local.22-github.1.zip"
```

It refuses to overwrite an existing output, verifies the baseline ZIP's SHA-256, rebuilds the package manifest, checks CRC and hashes, and rejects game-asset filenames. `github.1` changes the distribution documentation and includes recovered helper source; it does not change the Local.22 gameplay implementation. The original sealed beta remains available as the input to this process.

## Helper binaries and source

Eight small Windows helper executables and one finite-Mosquito object are retained byte-for-byte from the sealed Local.22 app. Their baseline hashes are in `packaging/baseline-local22.json`. Corresponding C# source is included; four legacy helper source files were recovered from project authoring files, and are identified in that manifest. Their source-to-binary equivalence has not been independently proven. Recompiling is a new build and requires its own validation before distribution.

To compile a C# helper, use the .NET Framework compiler with `/platform:x64`, `/optimize+` and, where `System.Web.Script.Serialization` is used, `/r:System.Web.Extensions.dll`. The GUI launcher source is `packaging/Launcher.cs`; compile it as `/target:winexe` with `/r:System.Windows.Forms.dll`.

The original finite-Mosquito C source is stored in `C_CODE` in `app/work/seed-v6/source/mosquito_runtime.py`. Its recorded build used Zig 0.13.0: `zig cc -target x86_64-windows-gnu -O2 -g0 -ffreestanding -fno-stack-protector -fno-asynchronous-unwind-tables -c finite-mosquito.c -o finite-mosquito.obj`. Zig and its toolchain are not bundled in this repository.

This is a usable source snapshot with preserved bootstrap binaries, not a claim of a bit-for-bit reproducible clean-toolchain build.
