#!/usr/bin/env bash
# Builds the fork as a native 64-bit binary and runs it headless.
#
# This exists because the arm64-v8a APK cannot be executed in CI, and building
# it proves almost nothing: all four pointer-width bugs found so far compiled
# and linked without a diagnostic and only showed up as a crash at runtime. The
# desktop 64-bit build runs the same widened data and the same readers, so it
# catches them. See android-build/ARM64-PORT.md.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/gradenGnostic/pokeemerald-multiplatform.git}"
REPO_REF="${REPO_REF:-master}"
WORK_DIR="${WORK_DIR:-$PWD/.pokeemerald-native64}"
# 30s only ever reached the title screen. The intro, the main menu and Birch's
# speech -- where the one crash a user actually hit lived -- need minutes.
RUN_SECONDS="${RUN_SECONDS:-150}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '\n==> %s\n' "$*"; }

[ -d "$WORK_DIR/.git" ] || git clone --branch "$REPO_REF" "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"

log "Applying arm64 port patches"
for patch in "$SCRIPT_DIR"/patches/0001-*.patch; do
    [ -e "$patch" ] || continue
    if git apply -R --check "$patch" 2>/dev/null; then
        echo "  $(basename "$patch") already applied"
    else
        git apply "$patch" || { echo "ERROR: $(basename "$patch") failed to apply" >&2; exit 1; }
    fi
done

log "Building host tools and generated sources"
make -j"$(nproc)" tools >/dev/null
make -j"$(nproc)" generated >/dev/null

log "Generating binary assets"
TARGETS="$WORK_DIR/.assets"
grep -rhoE '"(graphics|data|sound)/[^"]*\.[a-z0-9.]+"' src include data sound \
    | tr -d '"' | sort -u > "$TARGETS"
grep -rhoE '\.incbin[[:space:]]+"[^"]+"' data sound \
    | sed -E 's/.*"([^"]+)"/\1/' >> "$TARGETS"
grep -vE '\.(h|c|inc|json|txt|mk|s)$' "$TARGETS" | sort -u -o "$TARGETS"
xargs -a "$TARGETS" make -j"$(nproc)" >/dev/null

log "Generating song assembly from MIDI"
ls sound/songs/midi/*.mid | sed 's/\.mid$/.s/' > "$WORK_DIR/.songs"
xargs -a "$WORK_DIR/.songs" make -j"$(nproc)" >/dev/null

# PIE=1 is the point of this job, not a detail. Linked -no-pie the binary
# loads below 4GB, so a pointer truncated to 32 bits still round-trips and the
# build happily runs through bugs that kill the APK -- every pointer-width bug
# so far was found on a phone rather than here. Linked PIE the loader places
# the image above 4GB, the same as Android, and those bugs fault here instead.
log "Building 64-bit native binary (PIE, so it loads above 4GB like Android)"
make -f Makefile_pc NATIVE_LINUX=1 BITS=64 PIE=1 -j"$(nproc)" 2>&1 | tee build64.log

# Every pointer narrowed to 32 bits is a latent crash on a 64-bit target, and
# the compiler reports each one. These are being fixed in reviewable pieces
# rather than one sweep, so the check is a ratchet: the count may fall, and
# lowering the baseline is part of landing a piece, but it may never rise.
log "Checking for pointer truncation"
BASELINE=$(cat "$SCRIPT_DIR/truncation-baseline.txt")
# `|| true` matters: with `set -o pipefail` a grep that matches nothing exits
# 1 and would kill the script exactly when there is nothing wrong.
COUNT=$(grep -E "warning: cast (to pointer from|from pointer to) integer of different size" build64.log \
        | sed -E 's#^.*/([^/]+\.c):([0-9]+):.*#\1:\2#' | sort -u | wc -l || true)
echo "pointer truncation sites: $COUNT (baseline $BASELINE)"
if [ "$COUNT" -gt "$BASELINE" ]; then
    echo "ERROR: truncation count rose from $BASELINE to $COUNT" >&2
    grep -E "warning: cast (to pointer from|from pointer to) integer of different size" build64.log \
        | sed -E 's#^.*/([^/]+\.c):([0-9]+):.*#\1:\2#' | sort -u >&2
    exit 1
fi
if [ "$COUNT" -lt "$BASELINE" ]; then
    echo "NOTE: count is below the baseline -- lower truncation-baseline.txt to $COUNT"
fi
file pokeemerald | grep -q 'ELF 64-bit' || { echo "ERROR: not a 64-bit binary" >&2; exit 1; }
# A non-PIE binary here would silently turn this whole job back into the weak
# check it used to be, so fail rather than run something that proves less.
file pokeemerald | grep -q 'pie executable' \
    || { echo "ERROR: not linked PIE -- it would load low and hide truncation" >&2; exit 1; }

# A pointer-width bug shows up as SIGSEGV/SIGBUS within the first few seconds,
# during the intro and its music. Surviving the window is the pass condition;
# `timeout` returning 124 means it was still running when we stopped it.
# Drive it with synthetic input rather than watching it sit on the title
# screen. Without this every menu and every screen transition is untested, and
# a crash on "press Start" would not be caught here at all. The frame numbers
# just spread presses across the intro and the menus that follow.
# Past the title screen the intro needs a long run of A presses: through the
# main menu, Birch's speech, the Lotad that appears during it, and the name
# entry. The crash that got as far as "This is what we call a POKeMON" was in
# the mon animation task, which nothing shorter than this ever reached.
AUTOKEYS="${POKE_AUTOKEYS:-$(printf '600=START 900=A'; for f in $(seq 1000 40 20000); do printf ' %d=A' "$f"; done)}"

log "Running headless for ${RUN_SECONDS}s (input: $AUTOKEYS)"
rm -f pokeemerald.sav
set +e
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy POKE_AUTOKEYS="$AUTOKEYS" \
    timeout "$RUN_SECONDS" ./pokeemerald > run.log 2>&1
status=$?
set -e

if [ "$status" -eq 124 ]; then
    log "PASS: survived ${RUN_SECONDS}s without crashing"
    tail -5 run.log
else
    log "FAIL: exited with status $status before the timeout"
    echo "--- last 30 lines ---"
    tail -30 run.log
    case $status in
        139) echo "SIGSEGV -- almost certainly a pointer read at the wrong width or offset" ;;
        135) echo "SIGBUS  -- almost certainly a misaligned pointer-width access" ;;
    esac
    exit 1
fi
