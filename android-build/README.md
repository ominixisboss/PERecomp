# Pokemon Emerald on Android

Build harness for the Android target of
[gradenGnostic/pokeemerald-multiplatform](https://github.com/gradenGnostic/pokeemerald-multiplatform),
a fork of the `pret/pokeemerald` decompilation with an SDL2 port.

## Why this fork

The game's decompiled C is compiled and run **directly** on the device. There is
no bundled emulator and no commercial ROM involved, which is both faster to get
working and far cleaner legally than shipping a built `.gba` inside an APK.

The fork already provides, and this harness only drives:

- a Gradle + CMake Android project under `android/`
- an `SDLActivity` subclass with a labeled multitouch overlay (D-pad, A, B,
  Start, Select, L, R) and SDL gamepad support
- writable save storage in the app's private directory, plus lifecycle handling
- launcher icons and a display-settings page

> The project overview, download link and testing approach are in the
> [top-level README](../README.md). The 64-bit port's engineering log is
> [ARM64-PORT.md](ARM64-PORT.md); signing is in [SIGNING.md](SIGNING.md).
> This page covers the build harness itself.

## Building

```sh
export JAVA_HOME=...          # JDK 17
export ANDROID_HOME=...       # with ndk;26.3.11579264 and cmake;3.22.1
sudo apt-get install -y build-essential binutils-arm-none-eabi binutils-aarch64-linux-gnu \
                        libpng-dev python3-pil

POKEEMERALD_ABI=arm64-v8a ./android-build/build-android.sh
```

The APK lands at
`.pokeemerald-multiplatform/android/app/build/outputs/apk/debug/app-debug.apk`.
The script applies `patches/*.patch` in order, adds Emerald Arena
(`emerald-arena.sh`; `EMERALD_ARENA=0` to skip), generates the themes, and builds.
`.github/workflows/pokeemerald-android.yml` runs it for both ABIs, runs the 64-bit
crash test (`build-native64.sh`) and publishes the `latest` release.

## Fixes this harness applies on top of the fork

The fork's Android target is not covered by its own CI, and none of the
following is mentioned in its README. Each was found by building it:

1. **The documented patch command cannot work.** The README says to run
   `git -C android/SDL2 apply ../patches/sdl2-android-lifecycle.patch`, but that
   patch is generated with zero context lines, which `git apply` rejects
   outright. `--unidiff-zero` is required. The script also reverse-checks first,
   so re-running against an existing checkout is a no-op rather than an error.
2. **`make tools` is never run.** The CMake build shells out to
   `tools/preproc/preproc` for every translation unit but does not build it.
3. **`make generated` is never run.** `global.h` reaches `map_groups.h`, which
   `tools/mapjson` generates and which is not checked in, so otherwise every
   translation unit fails preprocessing.
4. **Binary assets are never generated.** Every `INCBIN_*()` names a `.4bpp` /
   `.gbapal` / `.lz` that `gbagfx` derives from the checked-in PNGs. This fork
   predates pokeemerald's `build/assets` layout -- its `preproc` has no `-g`
   flag -- so they have to land in the source tree. Note that a single
   `INCBIN_U32()` takes several comma-separated paths spanning many lines, so
   scanning for the macro line by line silently misses most of them; the script
   matches any quoted asset-directory path instead.
5. **Map includes are never generated.** The per-map `header.inc` /
   `events.inc` / `connections.inc` that `mapjson` derives from each `map.json`
   are prerequisites of the ROM's `maps.o`, not members of `AUTO_GEN_TARGETS`.
   Without them the link fails on undefined `gMapGroups`.
6. **Song assembly is never generated.** `sound/songs/midi/` ships 420 `.mid`
   files and no `.s` at all; `mid2agb` produces them. Without them the link
   fails on every `se_*` and `mus_*` symbol.

Items 5 and 6 must happen *before* Gradle, because the CMake globs those files
at configure time. That also means a rebuild in an already-dirty tree can
succeed where a clean checkout fails.

Note also that `make modern` -- the obvious way to generate everything at once
-- does not work in this fork: the ROM build fails because `src/platform/bios.c`
is SDL port code that will not compile for the GBA target. That is why the
script asks make for precisely the files it needs.

## Legal

See the [top-level README](../README.md#legal).
