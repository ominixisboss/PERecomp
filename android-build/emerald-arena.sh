#!/usr/bin/env bash
# Adds Emerald Arena -- real-time battles inside Emerald -- to the
# pokeemerald-multiplatform checkout in the current directory.
#
#   https://github.com/GBurgardt/pokemon-emerald-arena  (new code: MIT)
#   Pokemon sprites: PMDCollab SpriteCollab, fetched at a pinned commit by the
#   mod's own importer (see its CREDITS.md for authorship and licence).
#
# The mod is an overlay of new files plus a patch against pret/pokeemerald.
# Its overlay (21MB, mostly art) is fetched at a pinned release here rather
# than committed; arena/0002-emerald-arena.patch is only what this port needs
# on top: the engine hooks rebased onto the fork, and the 64-bit fixes the
# GBA build never needed (see the patch and ARM64-PORT.md).
#
# Run after the arm64 port patch and `make tools`, before asset generation.
# EMERALD_ARENA=0 builds the plain game instead.
set -euo pipefail

ARENA_URL="${ARENA_URL:-https://github.com/GBurgardt/pokemon-emerald-arena.git}"
ARENA_REF="${ARENA_REF:-e1502f9f7ed46d969880d73adbf5ab23ef7b2a56}"   # v0.13.0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH="$SCRIPT_DIR/arena/0002-emerald-arena.patch"

[ "${EMERALD_ARENA:-1}" = 0 ] && { echo "Emerald Arena disabled (EMERALD_ARENA=0)"; exit 0; }

if [ -f src/realtime_arena.c ] && git apply -R --check "$PATCH" 2>/dev/null; then
    echo "Emerald Arena already applied"
else
    src=.emerald-arena-src
    if [ ! -d "$src/.git" ]; then
        git init -q "$src"
        git -C "$src" remote add origin "$ARENA_URL"
    fi
    git -C "$src" fetch -q --depth 1 origin "$ARENA_REF"
    git -C "$src" checkout -q FETCH_HEAD
    cp -R "$src/game/overlay/." .
    # The overlay ships some art already converted (e.g. psychic/hud.4bpp)
    # next to its PNG. A fresh checkout gives files arbitrary mtimes, so make
    # may decide the PNG is newer and regenerate -- and the fork's gbagfx
    # rejects some of those PNGs' colour types. The shipped binaries are the
    # mod's authoritative output: mark them current.
    git -C "$src" ls-files game/overlay/graphics \
        | grep -E '\.(4bpp|8bpp|gbapal|bin|lz)$' \
        | sed 's|^game/overlay/||' | xargs -r touch
    git apply "$PATCH"
    echo "Emerald Arena $(git -C "$src" rev-parse --short HEAD) applied"
fi

# Downloads the pinned sprite sets and packs the arena's art into GBA formats.
./tools/arena/dev.sh assets
