# Pokémon Emerald for Android (64-bit)

A native Android build of Pokémon Emerald, compiled from the
[pret/pokeemerald](https://github.com/pret/pokeemerald) decompilation through the
[gradenGnostic/pokeemerald-multiplatform](https://github.com/gradenGnostic/pokeemerald-multiplatform)
SDL2 port. The game's C code runs directly on the phone: there is no emulator and
no ROM file.

This repository holds no game source. It holds the **patches, build scripts, tests
and CI** that turn the fork into a working arm64 APK, plus a few additions on top.

**Download:** the [`latest` release](../../releases/tag/latest) has
`pokeemerald-arm64-v8a.apk` (for any modern phone) and `pokeemerald-armeabi-v7a.apk`
(old 32-bit phones only). It is a debug-signed sideload build: Android will ask you
to allow installing from an unknown source.

## What's in the build

| | |
|---|---|
| **64-bit port** | The fork only ever ran as a 32-bit program. This is its first 64-bit build: every pointer-width assumption in the game code and data was found and fixed (details below). |
| **[Emerald Arena](https://github.com/GBurgardt/pokemon-emerald-arena)** v0.13.0 by GBurgardt | Real-time battles: supported wild and single-trainer battles are fought by moving, aiming and dodging. Others stay classic. On a fresh save, press **SELECT** on NEW GAME for a quick start, then **L+R** in the field to fight. **Switch it off** in the gear panel (Game → Real-time battles) and every battle is classic; the setting is saved, and you can flip it any time. |
| **Touch controls** | A one-piece D-pad you can roll your thumb around (with diagonals), A/B, START/SELECT, L/R, plus arena buttons: **BALL** (L+R in one tap) and **< >** to switch attacks. Vibration, size, opacity and a drag-to-move layout editor. |
| **Themes** | A gallery of 56 themes in seven categories, each card a live miniature of how it looks: **Handhelds** (12 shells that draw a whole handheld around the game, with animated buttons and a pivoting D-pad), **Hoenn** scenes, **Weather** (the game's own rain, snow, ash, sandstorm, fog and bubbles), **PC Box** (the game's box wallpapers, decoded from its own tiles), **Box Pals**, **Classic** and **Minimal**. Every theme picks a matching button style; 25 styles in all. Gear button (left side, under SELECT) → **Browse themes**. |
| **Saves** | Every build is signed with one permanent key, so a new APK installs over the old one and keeps the save. The save is copied to `Downloads/PokemonEmerald` whenever you leave the game, and the gear panel can back up or restore it. |
| **60fps** | Frame pacing that sleeps instead of spinning a CPU core, and catches up without slowing the game when the phone falls behind. |

## Repository layout

| Path | What it is |
|---|---|
| [`android-build/patches/`](android-build/patches) | `0001` the 64-bit port; `0003` touch controls, themes, saves and signing. Applied in order to a clean fork checkout. |
| [`android-build/arena/`](android-build/arena) + [`emerald-arena.sh`](android-build/emerald-arena.sh) | Fetches Emerald Arena at a pinned commit and applies its engine patch, rebased onto the fork with its 64-bit fixes. `EMERALD_ARENA=0` builds without it. |
| [`android-build/build-android.sh`](android-build/build-android.sh) | Builds the APK. |
| [`android-build/build-native64.sh`](android-build/build-native64.sh) | Builds the same code as a 64-bit desktop program and plays it headless. This is CI's crash test (see below). |
| [`android-build/themes/`](android-build/themes) | Generates the background themes at build time from the game's own graphics (sprites, PC box wallpapers, weather effects), and softens the fork's two painted ones so buttons read over them. |
| [`android-build/controls-tests/`](android-build/controls-tests) | Tests and image previews for the touch controls, running the app's real layout and drawing code on a plain JVM. |
| [`.github/workflows/pokeemerald-android.yml`](.github/workflows/pokeemerald-android.yml) | Builds both APKs, runs the crash test, and publishes the `latest` release. |
| [`android-build/ARM64-PORT.md`](android-build/ARM64-PORT.md) | The engineering log: every bug found, how, and how it was fixed. |
| [`android-build/SIGNING.md`](android-build/SIGNING.md) | The permanent signing key and how to set it up. |

## How it is tested

You can't run an APK in CI, so the same code is also built as a **64-bit desktop
program linked position-independent**. It loads above 4GB like Android does, so the
pointer bugs that crash a phone crash it too. CI then plays it headless at 20× speed:

- a scripted route through the intro, out of the moving truck and into Littleroot;
- four seeds of random play with a random wild battle whenever the player is free;
- three seeds of Emerald Arena's quick start with random real-time fighting, each
  required to actually enter the arena, and one with the arena switched off,
  required never to.

Any crash fails the build, and its log names the function. Static checks also run:
zero compiler-reported pointer truncations, no misaligned pointer tables in the
hand-assembled game data, and every bytecode command handler cross-checked against
the macro that encodes it.

The themes are checked too. Every background is laid under the app's real
control layout at four phone shapes, and the theme list in the app is checked
against what the generator actually made, number by number. Under each button the art must be calm
(no sprite edges or bright moons behind a label) and the label must keep a 3:1
contrast. Every button style's ink must read on each face it is drawn on.

Every bug fixed here was found this way or from a crash report on a phone. They
include a DMA register that truncated a pointer, map event tables laid out 4 bytes
off (so no step-triggered event ever ran, which is why the game crashed getting
off the truck), list menus overflowing their task slot (the Bag crash), and battle
commands reading operands at their GBA offsets (every battle froze after the first
move). [`ARM64-PORT.md`](android-build/ARM64-PORT.md) has all of them.

**Not covered:** CI never runs the Android touch overlay or the app on a device.
Those are compiled and unit-tested, and phone testing is manual. The automated play
covers the early game; later story events, contests and link features have not been
exercised.

## Building it yourself

```sh
# APK: JDK 17, Android SDK with ndk;26.3.11579264 and cmake;3.22.1
sudo apt-get install -y build-essential binutils-arm-none-eabi binutils-aarch64-linux-gnu \
                        libpng-dev python3-pil
POKEEMERALD_ABI=arm64-v8a ./android-build/build-android.sh

# Desktop 64-bit crash test: also needs libsdl2-dev libsdl2-image-dev
./android-build/build-native64.sh
```

Without the signing secrets the APK is signed with a throwaway key
(see [`SIGNING.md`](android-build/SIGNING.md)).

## Legal

Pokémon and Pokémon Emerald are trademarks of Nintendo, Creatures Inc. and
GAME FREAK inc. This is an unofficial, non-commercial fan project, not affiliated
with or endorsed by them. The repository contains only patches, scripts and tests.
The APKs it builds are compiled from the decompilation project and so contain the
game's own graphics, text and music. Emerald Arena's new code is MIT-licensed; its
Pokémon sprites come from PMDCollab's SpriteCollab, whose terms do not allow
commercial use.

---

*`Packages/` and `docs/` hold an earlier, unrelated project from this repository
(a play-aid for the tabletop RPG* Alone Against the Zone*). The Emerald build does
not use them.*
