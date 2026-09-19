# arm64 port: analysis and plan

The fork is `armeabi-v7a` only, which cannot install on a 64-bit-only device
(Pixel 7 and later, recent flagships, modern emulator images). This is the
analysis of what it would take to build for `arm64-v8a`, measured rather than
assumed.

## What is NOT a problem

The game's assembly is **ABI-neutral**. All 545 `.s` files -- `data/*.s`, the
110 `sound/songs/*.s` and the 420 generated `sound/songs/midi/*.s` -- assemble
for aarch64 with **zero failures**. They contain only data directives
(`.byte`, `.word`, `.short`, `.align`, `.global`), no ARM instructions.

So there is no "rewrite the assembly for a new architecture" problem. There is
exactly one blocker.

## The one blocker

The data contains **48,316 four-byte pointer slots**, which assemble to
`R_AARCH64_ABS32` relocations. An absolute 32-bit relocation against a symbol
cannot exist in a shared object, and every Android app is a PIE/shared library:

```
relocation R_AARCH64_ABS32 against `PetalburgCity_EventScript_WallysMom'
can not be used when making a shared object
```

Minimal repro confirms both halves of this: `.word symbol` fails to link into a
`-shared` object, and `.xword symbol` links fine, becoming a relative dynamic
relocation.

## Where the 48,316 slots are

They split almost evenly into two classes that need different fixes.

| Source | Slots | Class |
| --- | ---: | --- |
| `data/event_scripts.s` | 17,438 | bytecode |
| `data/battle_anim_scripts.s` | 4,231 | bytecode |
| `data/battle_scripts_1.s` | 1,508 | bytecode |
| `data/battle_ai_scripts.s` | 1,222 | bytecode |
| `data/contest_ai_scripts.s` | 364 | bytecode |
| **bytecode subtotal** | **24,763** | |
| `sound/songs/**` (530 files) | 10,992 | struct |
| `data/maps.s` | 4,439 | struct |
| `data/map_events.s` | 4,054 | struct |
| `data/sound_data.s` | 3,774 | struct |
| **struct subtotal** | **23,259** | |

## Plan

### Struct data (23,259 slots) -- widen to 64-bit

These slots are fields of C structs. On arm64 the compiler already lays those
fields out as 8 bytes, so the assembly must match: `.4byte sym` becomes
`.xword sym`, with `.balign 8` where the struct's alignment now demands it.
The C side needs no changes; the risk is purely in getting padding to match
the arm64 C ABI.

The 10,992 song slots are the cheapest win by far, because they are emitted by
`tools/mid2agb`, so they are fixed in one generator rather than 530 files.
The map slots likewise come from `tools/mapjson`.

### Bytecode (24,763 slots) -- keep 4 bytes, store offsets

Widening here would be much worse: these pointers sit inside bytecode streams
that C interpreters walk byte by byte, so every argument offset in every script
command would shift.

Instead keep them four bytes and store a **link-time-constant offset** rather
than an address:

```
.4byte SomeScript - __script_base
```

A difference between two symbols in the same output section is resolved at link
time to a constant, so it produces **no dynamic relocation at all** and is legal
in a shared object. Sizes and every existing offset stay exactly as they are.

The cost is on the C side: each interpreter must add `__script_base` where it
currently dereferences a raw script pointer -- `script.c`'s `ScriptReadWord`
and the battle script, battle anim and AI command readers.

## Progress

| Step | Slots | State |
| --- | ---: | --- |
| map data (`mapjson`, `asm/macros/map.inc`) | 8,493 | done |
| map script tables (`map_script` macros) | 832 | done |
| sound data (`m4a.inc`, `music_voice.inc`) | 3,774 | done |
| song headers (`tools/mid2agb`) | 2,333 | done |
| in-track song pointers (`music_player.c`) | 8,659 | done |
| field effect scripts (`field_effect.c`) | 170 | done |
| mystery event command table | 17 | done |
| script engine (`event_scripts`, `scrcmd.c`) | 17,438 | done |
| battle scripts (`battle_scripts_1/2`, `battle_script_commands.c`) | 1,562 | done |
| battle AI scripts (`battle_ai_script_commands.c`) | 1,218 | done |
| battle anim scripts (`battle_anim.c`) | 4,231 | done |
| contest AI scripts | 364 | done |
| **converted** | **48,316 / 48,316** | **100%** |


Each step is verified three ways: the arm64 object has zero remaining ABS32,
the arm32 object is byte-for-byte unchanged in relocation count, and the
resulting field offsets are compared against what the aarch64 C compiler
actually produces rather than hand-computed.

Watch for hardcoded structure sizes, not just pointer emissions. `voice_group`
indexed backwards by a literal `0xC`, which is `sizeof(struct ToneData)` on a
32-bit target; on arm64 the compiler reports 24. Measured stride after the fix
is 12 on arm32 and 24 on arm64, with the sample pointer at offset 4 and 8
respectively -- matching `offsetof` exactly.

## Deriving instruction layouts, rather than guessing them

The battle interpreters hide the pointer width in three separate places
besides the emission: `gBattlescriptCurrInstr += N` advances, `... + N` read
offsets into the instruction, and helpers such as `JumpIfMoveFailed(N, ...)`
that take an instruction length as an argument.

Classifying fields by parameter name does not work. `tryfaintmon` emits
`.int NULL` into a pointer field, and shares its opcode with
`tryfaintmon_spikes`, which names the same field `ptr` -- widening one and not
the other would have produced two different layouts for one opcode.

What does work is deriving the truth from the handlers: every
`ReadStreamPtr(gBattlescriptCurrInstr + N)` names a pointer offset for that
opcode. Cross-checking those against the layouts parsed out of
`battle_script.inc` confirmed 112 pointer fields, with the only two
non-matches being 1-byte instructions that read no operands at all. Every
advance, offset and helper length is then recomputed from that layout and
emitted in terms of `sizeof(void *)`, so both ABIs are right by construction.

The same cross-check validated the derivation before any of it was applied:
142 instruction lengths computed from the macros reproduced the hardcoded
advances exactly, with zero mismatches.

## The link is all-or-nothing

Reaching 99% converted did not mean nearly linkable. A single remaining
R_AARCH64_ABS32 fails the whole shared link, so every last slot had to go --
including contest AI, which had been set aside.

With all 48,316 converted, the combined game data links:

```
aarch64-linux-gnu-ld -r    -> game_data.o, 0 ABS32
aarch64-linux-gnu-ld -shared -> 20.5 MB .so, succeeds
```

## Contest AI: how it was eventually derived

Contest AI does not follow the convention the other interpreters use. Its
dispatcher consumes the opcode before calling the handler, so `gAIScriptPtr`
points at the first operand rather than the instruction -- and worse, handlers
delegate to helpers (`ContestAICmd_get_condition` and friends) that themselves
consume a varying number of operands before the handler reads anything.

That makes the instruction layout not statically derivable from the handler
the way it is everywhere else. The cross-check refused it: with the
instruction as the base, 88 of 100 pointer offsets failed to land on a 4-byte
field; shifting one past the opcode still left 45 failing.

The missing piece was that each helper advances the pointer by a fixed,
discoverable amount -- `get_condition` by 2, `get_appeal_num` by 1 -- and
that advance *is* the base for the handler that calls it. Deriving the base
that way took the cross-check from 12 of 100 offsets confirmed to 99 of 100.

The single holdout turned out to be a pre-existing bug in the fork:
`if_most_jamming_move` emits `.4bye` instead of `.4byte`. gas only expands a
macro when it is used, and nothing uses this one, so the typo has never
surfaced. It is fixed here.

## Status

Implementation in progress; the 32-bit build stays green throughout.

The honest caveat: this has to be validated by running the game, and this
environment has no device or emulator (`dl.google.com` is blocked by the
network policy, so no emulator images). CI can prove it compiles, links and
packages; it cannot prove the data is laid out correctly. Wrong padding
produces a build that installs and then misbehaves in ways only play-testing
finds.

## C-side 32-bit assumptions

With every pointer slot in the game data widened, what fails next is ordinary C
code that assumed a 4-byte pointer. These are tracked here as they surface.

### Save block overflow (fixed)

`src/save.c` fails its own size check on a 64-bit build:

    src/save.c:80: error: 'SaveBlock1FreeSpace' declared as an array with a
    negative size

`SaveBlock1` embeds `objectEventTemplates[64]`, and `ObjectEventTemplate` grows
from 24 to 32 bytes on arm64 because of its `const u8 *script` field. That is
512 bytes more, taking `SaveBlock1` from 15,752 to 16,264 bytes against a
four-sector budget of 3968 x 4 = 15,872 -- an overflow of 392 bytes.

The field cannot simply be narrowed in the saved copy. Although
`LoadSaveblockObjEventScripts()` in `src/overworld.c` overwrites every saved
script pointer from the map header on load, so the *serialized* value is dead,
`LoadBattlePyramidFloorObjectEventScripts()` writes real function pointers into
the same array and the field system dereferences them at runtime. The field has
to be pointer-width in memory.

`SaveBlock1` is therefore given a fifth sector, but only on a 64-bit build:
`SAVEBLOCK1_EXTRA_SECTORS` in `include/save.h` is 1 there and 0 otherwise, and
every sector constant is expressed in terms of it. A 32-bit build keeps the
GBA's exact layout -- same four sectors for `SaveBlock1`, same 14-sector slot,
same 32-sector flash -- so the armeabi-v7a save format is untouched. A 64-bit
build uses a 15-sector slot and a 34-sector flash, which is only possible
because the port's "flash" is a plain file (`FLASH_BASE` in
`src/platform/bios.c`), not real 1 Mbit hardware.

Two static assertions in `src/save.c` keep the two halves honest: the sector
layout must match the emulated flash size, and the two save slots must still
fit below the Hall of Fame sectors.

Note that an arm64 save file can never be byte-compatible with an arm32 one
regardless of this change, since `SaveBlock1` serializes pointer-bearing
structs either way.

`SaveBlock2` and `PokemonStorage` contain no pointers and are unchanged.

### VRAM macro truncated addresses (fixed)

    src/tileset_anims.c:220: error: initializer element is not a compile-time
    constant

`include/gba/defines.h` defined the portable build's VRAM base as
`#define VRAM (u32)VRAM_`, where `VRAM_` is the emulated VRAM array. Static
initializers of the form `(u16 *)(BG_VRAM + TILE_OFFSET_4BPP(n))` are only
compile-time constants while the expression stays an *address constant*.
Truncating a 64-bit address to `u32` is an arithmetic conversion the compiler
cannot fold, so every such initializer fails on arm64. On arm32 the cast was a
no-op, which is why it went unnoticed.

Changed to `((__UINTPTR_TYPE__)VRAM_)` -- a compiler builtin, so the header does
not need `stdint.h`. `PLTT` and `OAM` are plain arrays with no cast and were
already fine; `VRAM` was the only macro of this shape.

## Status: both ABIs build

As of CI run 24 both `armeabi-v7a` and `arm64-v8a` compile, link and produce an
APK, so the arm64 job is no longer `continue-on-error`.

What is verified: all 48,316 pointer slots in the game data are widened, the
arm64 shared object links with zero `R_AARCH64_ABS32` relocations, the arm32
data output stays byte-identical to upstream, and both APKs build from a
pristine checkout plus this patch series.

What is NOT verified: that the game actually runs. There is no device or
emulator in the build environment, so nothing here has executed a single frame.
Runtime faults from a missed 32-bit assumption would look like corrupted
graphics, wrong text, or a crash on entering a map or a battle, and only
running the APK will find them.

## Runtime validation: the 64-bit native build

Everything above is a *build-time* result. A build that links is not a game that
runs, and there is no arm64 device in this environment, so until now nothing
had executed a single frame.

The fork is 32-bit on every platform it supports -- its own README says "Working
native 32-bit SDL2 build", 32-bit MinGW, ARMv7 -- so this port is the first
64-bit build of it anywhere. That also means a **native x86-64 Linux build
exercises exactly the same code as the Android arm64 build**: the same widened
game data, the same `sizeof(void *)` reader paths, the same struct layouts.
`Makefile_pc` therefore gets a `BITS` knob (`BITS=64` selects `--64`/`-m64` and
defines `PTR64`); `BITS=32` is the default and is byte-for-byte what it was.

    make -f Makefile_pc NATIVE_LINUX=1 BITS=64 -j$(nproc)
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./pokeemerald

Running it found four real bugs that no amount of building would have caught.
**Every one of them was present in the arm64 APK.**

### 1. gSongTable was not pointer-aligned

`sound/song_table.inc` opened with `.align 2` (4 bytes). `struct Song` begins
with a pointer, so on a 64-bit build `ptr`'s own `.balign 8` padded *after* the
label and skewed every entry by 4 bytes. The symptom was a `songHeader` of
`0x01539dc000000000` -- a valid 32-bit address sitting in the high half of the
word. Fixed with `palign`, likewise for `gMPlayTable`.

The general rule this establishes: **`ptr` aligns a pointer within a struct, but
a label that begins a pointer-bearing struct must itself be `palign`ed.**

### 2. Voice entries had no fixed stride

`struct MP2KInstrument` is 24 bytes on a 64-bit build. 24 is not a power of two,
so alignment alone cannot produce the stride -- a pointerless entry (square,
noise) ended at 16 bytes and the next entry's header leaked into its ADSR slot.
Each entry macro now records its start and pads to `VOICE_ENTRY_SIZE`.

Those same pointerless voices also needed *internal* padding: their 4-byte
config and ADSR fields sit in unions that are 8 bytes wide once a pointer is a
member, so `pad32` was added after the header and after the config.

### 3. SoundInfo and SoundMixerState disagreed by 16 bytes

`music_player.c` casts `SOUND_INFO_PTR` straight to `struct SoundMixerState`, so
the two declarations describe the same memory and must match. `SoundInfo` ended
its function-pointer block with `u8 gap2[16]` where `SoundMixerState` has four
reserved *pointers*. Four pointers are 16 bytes at 32-bit -- and 32 at 64-bit,
so everything from `chans` onward was skewed by 16 (`chans` at 120 vs 136,
sizes 40432 vs 40448). Changed to `void *gap2[4]`, which is identical at 32-bit
and correct at 64.

### 4. Pokemon cry songs truncated a pointer

`struct PokemonCrySong` is a song header and its track bytecode in one struct,
and it stored its GOTO target as `u32 gotoTarget`. `m4a.c` wrote
`(u32)&gPokemonCrySongs[i].cont`, truncating a 64-bit address, and
`MP2K_event_goto` read it back with `memcpy(..., sizeof(u8 *))` -- 8 bytes -- so
it got 4 bytes of address plus 4 bytes of whatever followed. It is now
`u8 gotoTarget[sizeof(void *)]`, written with `memcpy`: pointer-width, and
deliberately a byte array so no alignment padding is inserted into a bytecode
stream that the interpreter walks sequentially.

### Result

The 64-bit binary now runs indefinitely: verified on a clean clone of master
plus this patch series, 90 seconds without a fault, CPU time climbing steadily
across three threads with the main thread in SDL's frame-pacing sleep.

arm32 output is unaffected -- `data/sound_data.s` assembles to a byte-identical
7,506,592-byte blob before and after, with no assembler warnings.

### What is still unverified

Headless, nothing checks what is on screen. The game reaches and sustains its
main loop; it has not been shown to render correctly, accept input, battle, or
save. Those need a real device or a display.

### 5. Map group tables were not pointer-aligned (found by audit)

Bug 1 was found by luck -- the intro music happened to hit it. Since the same
mistake anywhere else would only surface later in the game, the class was swept
systematically: every label in the assembly that is immediately followed by a
pointer, cross-checked against its actual address in the linked 64-bit binary.

That found `gMapGroup_TownsAndRoutes` at an address 4 mod 8. It is the first of
the per-group map tables emitted by `tools/mapjson`, which emitted `palign`
before `gMapGroups` but not before each group table, so the first `ptr`'s own
`.balign` padded after the label and skewed the whole table. The later group
labels happened to be fine only because each is preceded by a `ptr`, which
aligns as a side effect.

This one would not have appeared during the intro. It is the table the game
walks to load a map, so it would have shown up as a crash or a wrong map on
entering the overworld -- the first thing anyone would do on a phone.

After the fix, all 570 symbols in the game data that begin a pointer table are
8-aligned. arm32 output is unchanged: `palign` is `.balign 4` there and the
labels were already 4-aligned, verified byte-identical on the generated
`groups.inc`.

## The remaining class: pointers truncated through 32-bit integers

A crash report from a real device -- "crashes when I get to the Pokemon screen"
-- turned out to be the visible tip of a class the compiler had been reporting
all along. `-Wpointer-to-int-cast` and `-Wint-to-pointer-cast` are on by
default, and a full 64-bit build emits **136** of them. Each one is a pointer
narrowed to 32 bits, and each is a latent crash the moment the value is used as
an address again.

Three were on the path to that screen and are fixed:

### GetWindowAttribute / SetWindowAttribute

The pair passed `WINDOW_TILE_DATA` -- `struct Window`'s `tileData` pointer --
through a `u32`, and all twelve callers cast the result straight back to
`u8 *`: drawing a Pokemon's picture (`trainer_pokemon_sprites.c`), the storage
system, the bag, the battle interface, the Pokedex cry screen. Now `uintptr_t`,
which is identical on a 32-bit build.

### SetTaskFuncWithFollowupFunc

This stored a **code pointer** as two `s16` halves in `data[14]`/`data[15]`, so
`SwitchTaskToFollowupFunc` jumped to a truncated address. `party_menu.c` uses
it for `Task_PartyMenuModifyHP`, which is reached by healing a Pokemon from the
party screen. On 64-bit the followup is now kept beside the task.

### SetWordTaskArg / GetWordTaskArg

Same packing, same problem, for data pointers: `menu.c` stored a `malloc`ed
tile buffer this way and then `Free()`d the truncated result -- that task backs
graphics loading for menus generally. Ten call sites across `menu.c`,
`easy_chat.c`, `pokemon_jump.c`, `pokenav.c` and `pokenav_menu_handler_gfx.c`
now use pointer-width accessors.

Widening these to four slots was not possible: `easy_chat` stores pointers at
slots 2 and 4, `pokenav_menu_handler_gfx` at 1 and 3, and `pokemon_jump` at
slot 14 of 16, so four-slot values would overlap each other or run off the end
of `data[]`. The pointers are kept in a side table keyed by task and slot,
leaving `data[]` exactly as it was. The 32-bit build keeps the original
packing, since some of these tasks are inspected through `data[]` elsewhere.

### The other 133

They are concentrated in `battle_factory_screen.c` (29), `m4a.c` (9),
`fldeff_misc.c` (6), `field_door.c` (6), `shop.c` (5), `pokemon_animation.c`
(5) and `pokedex.c` (5), and they are mostly the same idiom: a pointer stashed
in a `s16` sprite or task data slot. Each needs the same treatment and a look
at what else reads those slots, so they are being worked through rather than
bulk-edited.

The useful part is that the list is exact and free: `make -f Makefile_pc
NATIVE_LINUX=1 BITS=64` prints every one. No guessing about which screen breaks
next.

## All 136 truncations fixed

The count is now zero, and `android-build/build-native64.sh` fails the build if
it ever rises again. How they were handled, since they were not all the same
problem:

**A handle instead of the pointer (the bulk).** Most of these split a pointer
into two 16-bit halves and stored it in `s16` task or sprite data. Widening
those slots is not possible -- `easy_chat` stores pointers at slots 2 and 4,
`pokenav_menu_handler_gfx` at 1 and 3, `pokemon_jump` at slot 14 of 16, so
four-slot values would overlap or run off the end. `src/pointer_handle.c`
instead packs a pointer into a 32-bit *handle* indexing a side table. A handle
splits, masks, byte-swaps and reassembles exactly the way the old value did, so
every storage layout and every piece of caller arithmetic is untouched. On a
32-bit build `PackPtr`/`UnpackPtr` are identity casts.

This covered `battle_factory_screen.c` (29 sites), the field-move callbacks in
the `fldeff_*` files, `shop.c`, `field_door.c`, `pokeball.c`,
`pokemon_animation.c`, `apprentice.c`, `record_mixing.c`, `list_menu.c`,
`pokemon.c`'s task macros, and the `StorePointerInVars` / `StoreWordInTwoHalfwords`
helper pairs.

**Not pointers at all.** Three sites were arithmetic that a mechanical pass
would have broken, and the compiler warning did not distinguish them:
`battle_script_commands.c` takes a pointer *difference* to measure a string,
`field_control_avatar.c` reads a packed item/flag out of a union member that
only holds an address for other event types, and `mystery_event_script.c` uses
a base address for offset arithmetic. These became `uintptr_t` casts.

Two more went the other way: `battle_anim_effects_1.c` and `battle_anim_fight.c`
stored an *integer* (a palette mask, a 24.8 fixed-point accumulator) through the
*pointer* helper. A handle would have silently corrupted them, so they now use
the raw-word helper.

**Genuine pointer arithmetic through a narrow int.** `m4a.c` advanced channel
pointers with `(s32)chan + sizeof(...)`, which truncates. This one mattered:
the sound driver runs on this target, and it only appeared to work because the
native binary happens to load at a low address. Under a PIE on Android the
addresses are large and it would have broken.

**Map script tables.** `MapHeaderGetScriptTable` walks its table byte-wise with
a hardcoded stride of 5, and `MapHeaderCheckScriptTable` with 8. Both assumed a
4-byte pointer. Their labels are in hand-written `scripts.inc` files and carry
no alignment, so the `map_script` macros now emit `ptr_stream` (packed, like
bytecode) rather than `ptr` (aligning), which keeps the stride deterministic:
`1 + sizeof(void *)` and `sizeof(void *)`. `T2_READ_PTR` reads at the target's
width, byte-wise, so an unaligned table position is fine. At 32 bits
`ptr_stream` and `ptr` emit identical bytes, verified.

**Window tile data, task followups, task args.** Covered in the previous
section -- these were the three on the path to the party screen.

One trap worth recording: a `//` comment in `asm/macros/map.inc` silently
stopped the macro below it from being defined, with no error on the comment
line itself -- the failure showed up much later as "no such instruction:
map_script". These files take one-line `/* */` comments only.

## Diagnosing crashes on the device

The title-screen crash reported after the truncation work could not be
reproduced in the desktop 64-bit build, which runs indefinitely. The reason is
an address-layout difference: Android is always PIE and loads at a high
address, while the desktop build is `-no-pie` and loads low, so a pointer that
is *still* being truncated somewhere works locally and only fails on the phone.

Two attempts to reproduce that locally both hit toolchain walls, and are
recorded here so they are not tried again blind:

- `PIE=1` fails to link: `data/mystery_gift.s` contains a pre-existing
  `R_X86_64_16` relocation against a symbol, which cannot appear in a PIE.
- `HIGHADDR=1` (non-PIE, `-Ttext-segment` above 4 GB, `-mcmodel=large`) fails
  too, because the toolchain's own `crtstuff.o` is built small-model and its
  relocations truncate.

`Makefile_pc` keeps the `HIGHADDR` knob since it documents the intent, but it
does not currently link.

So the crash reports itself instead. `src/platform/sdl2.c` installs a handler
for SIGSEGV/SIGBUS/SIGILL/SIGFPE that shows a dialog on the phone with:

- which signal, and the faulting address (`si_addr`)
- the **faulting PC**, taken from `ucontext` (`uc_mcontext.pc` on aarch64) --
  this is the number that locates the bug; `si_addr` only says what was touched
- the top backtrace frames, each as an offset from `main()`

Offsets from `main()` are used rather than `dladdr`, which would need
`_GNU_SOURCE` before the first libc header -- something this file cannot
arrange. CI keeps the unstripped `libmain.so` as an artifact, so:

    aarch64-linux-gnu-addr2line -f -C -e libmain.so <main_file_offset + delta>

turns a number read off the screen into a source line. Find `main`'s own file
offset with `nm libmain.so | grep ' main$'`.

Verified locally that the handler fires and reports the right fault address,
and that installing it does not disturb a normal run.

## Reverted: the truncation batch goes back in pieces

Landing all 136 truncation fixes at once was a mistake. The build that came out
of it crashed at the *title* screen, earlier than the build before it, and with
no way to reproduce that locally there was no way to tell which of the 136 did
it. One large change that cannot be bisected is worse than the bug it fixes.

The patch is therefore back to the state at `0fe5044`:

- everything through the map-group alignment fix, which is the build that
  reached the overworld and the party menu
- plus the three fixes on the party-screen path (window tile data, pointer-
  width task args, the task followup function)
- plus the on-screen crash reporter, which is diagnostic only

That is 169 files, and the truncation count is back to 136 as expected.
`build-native64.sh` now treats that number as a **ratchet** read from
`android-build/truncation-baseline.txt`: it may fall, and lowering the file is
part of landing a piece, but it may never rise.

The batch goes back in as separate, individually testable commits. The exact
file split, so this is reproducible rather than approximate:

**Piece 1 -- field-move callbacks** (plus the handle infrastructure they need):
`src/pointer_handle.c`, the `PackPtr`/`UnpackPtr` declarations in
`include/global.h`, `src/braille_puzzles.c`, `src/fldeff_cut.c`,
`src/fldeff_dig.c`, `src/fldeff_misc.c`, `src/fldeff_rocksmash.c`,
`src/fldeff_strength.c`, `src/fldeff_sweetscent.c`, `src/fldeff_teleport.c`.
One uniform idiom, one reader, easy to reason about.

**Piece 2 -- battle factory**: `src/battle_factory_screen.c` alone. 29 sites,
entirely self-contained, and on a screen that is easy to avoid while testing.

**Piece 3 -- the shared helper pairs**: `src/battle_anim_mons.c` (which owns
`StorePointerInVars`), `include/util.h`, `src/battle_anim_effects_1.c`,
`src/battle_anim_fight.c`, `src/event_object_movement.c`, `src/field_effect.c`,
`src/slot_machine.c`, `src/trainer_see.c`. Note the last two of these store
*integers* through the pointer helper and had to move to the raw-word helper.

**Piece 4 -- assorted per-file**: `src/shop.c`, `src/field_door.c`,
`src/pokeball.c`, `src/pokemon_animation.c`, `src/apprentice.c`,
`src/record_mixing.c`, `src/list_menu.c`, `src/pokemon.c`.

**Piece 5 -- the odd ones out**: `src/m4a.c`, `src/pokedex.c`, `src/menu.c`,
`src/battle_controllers.c`, `src/battle_controller_player.c`,
`src/pokemon_icon.c`, `src/pokemon_storage_system.c`, `src/librfu_rfu.c`,
`src/dynamic_placeholder_text_util.c`, `src/party_menu.c`,
`src/platform/bios.c`, `src/agb_flash.c`, `src/battle_script_commands.c`,
`src/field_control_avatar.c`, `src/mystery_event_script.c`. These are not one
idiom -- they include the three arithmetic sites that a mechanical pass would
have broken, so this piece needs the closest reading.

**Piece 6 -- map script tables**: `asm/macros/map.inc`, `src/script.c`, and the
`T2_READ_PTR` change in `include/global.h`. Last, because it is the only piece
that alters emitted data rather than C code. Its layout was verified against
real aarch64 output (entry is a type byte then an unaligned 8-byte pointer,
stride 9) but never against a running device.

Two traps when landing these from the reference tree:

- `src/platform/sdl2.c` must never be copied across. The reference predates the
  crash reporter and copying it would silently remove it.
- `include/global.h` carries two unrelated changes -- the `PackPtr` declaration
  (piece 1) and the `T2_READ_PTR` widening (piece 6). It has to be split by
  hunk, not copied whole.

### "No dialog, the app just closes" is not evidence of no crash

The first crash reporter showed its report with `SDL_ShowSimpleMessageBox`.
On Android that has to reach the UI thread through JNI, which from a thread
that is already crashing will usually fail silently -- so the handler can fire,
correctly, and the user still sees nothing but the app disappearing. Absence of
the dialog says nothing about whether a signal was raised.

The report is therefore written to a file first, with `open`/`write` (usable
from a handler), next to the save file, and shown on the **next** launch from
the normal startup path where a message box works. It is deleted once shown.

Verified end to end on the desktop build: crash, report written, next launch
displays it, file removed.

## The crash, found: DMA destination reload

The on-screen crash reporter, a device report and the CI symbol window
together located this exactly, with no guessing:

    SIGSEGV
    fault address: 0x9c4218bc
    PC: main-7180

`0x789c4218bc` is a real address in that process, and `0x9c4218bc` is its low
32 bits -- so a pointer had been truncated. The symbol window placed the PC
between `RunDMAs` (main-7352) and `DmaSet` (main-6956): 172 bytes into
`RunDMAs`, in `src/platform/dma.c`.

`DmaSet` keeps the real pointers in `DMAList`, which is correct. It also
writes them into the emulated `REG_DMAxSAD`/`DAD` registers, which are 32 bits
wide because that is what they are on the hardware -- so those copies are
necessarily truncated. That was harmless until `RunDMAs` reloaded from one:

```c
if (((dma->control) & DMA_DEST_MASK) == DMA_DEST_RELOAD)
    dma->dst = (void *)(uintptr_t)((&REG_DMA0DAD)[dmaNum * 3]);
```

On a repeating DMA with `DMA_DEST_RELOAD`, the destination was rebuilt from
the 32-bit register, so after the first repeat it became a truncated address
and the next transfer wrote to it. Repeating DMAs drive the scanline and
screen effects, which is why it fired on a screen transition and not during
ordinary play.

The fix keeps the destination as originally programmed in the transfer record
and reloads from that. Equivalent to the hardware, which reloads from a
register that really does hold the whole address.

This one could never have been found from the compiler warnings: both sides of
the assignment are correctly typed, and the truncation happens in the emulated
hardware register in between.
