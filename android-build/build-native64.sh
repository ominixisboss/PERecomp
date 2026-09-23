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
RUN_SECONDS="${RUN_SECONDS:-110}"
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
# Map data is laid out by hand in asm macros, not by the compiler, so a table
# whose label is not pointer-aligned compiles cleanly and reads as garbage. That
# class broke every coord event, every NPC after the first and every outdoor
# map's connections -- none of it visible to any compiler warning. Check it.
log "Checking assembled data for misaligned pointer tables"
python3 "$SCRIPT_DIR/aligncheck.py" $(find build/linux/data build/linux/sound -name '*.o' | grep -v /songs/) \
    | grep -v "(1 aligned" | grep -vE "^(battle_anim_scripts|field_effect_scripts|event_scripts)\.o" > aligncheck.log || true
tail -1 aligncheck.log
if grep -q "at +0x" aligncheck.log; then
    echo "ERROR: pointer tables start misaligned:" >&2
    grep "at +0x" aligncheck.log >&2
    exit 1
fi

# Bytecode command handlers read operands at fixed offsets, and every pointer
# operand is 4 bytes wider on 64-bit. A handler that still reads the byte after
# a pointer at its GBA offset reads a byte of the pointer instead: that is how
# `setbyte sMOVEEND_STATE, 0` stored garbage and hung every battle after the
# first move. Check each engine's handlers against the macros that encode them.
log "Cross-checking bytecode handlers against their macros"
for spec in "battle_script:battle_script_commands:gBattleScriptingCommandsTable:gBattlescriptCurrInstr" \
            "battle_ai_script:battle_ai_script_commands:sBattleAICmdTable:gAIScriptPtr" \
            "contest_ai_script:contest_ai:sContestAICmdTable:gAIScriptPtr" \
            "battle_anim_script:battle_anim:sScriptCmdTable:sBattleAnimScriptPtr"; do
    IFS=: read -r inc c table ip <<< "$spec"
    out=$(python3 "$SCRIPT_DIR/cmdcheck.py" "asm/macros/$inc.inc" "src/$c.c" "$table" "$ip")
    echo "$out" | tail -1
    if echo "$out" | grep -q "^op "; then
        echo "$out" >&2
        echo "ERROR: handlers disagree with their macros' operand layout" >&2
        exit 1
    fi
done

# The run is driven, and at 20x speed (POKE_TIMESCALE): at real speed the old
# 150s run was ~9000 frames, never out of the moving truck. The route: through
# the intro and name entry, out of the truck (the crash a user hit), into
# Littleroot and the house. Then random play (POKE_FUZZ) under several seeds,
# which is what found the Bag crash -- no fixed route opens the Bag.
ROUTE="600=START 900=A"
for f in $(seq 1000 40 6000); do ROUTE="$ROUTE $f=A"; done
for f in $(seq 6000 8 8000); do ROUTE="$ROUTE $f=RIGHT"; done
for f in $(seq 8000 30 9500); do ROUTE="$ROUTE $f=A"; done
AUTOKEYS="${POKE_AUTOKEYS:-$ROUTE}"
SEEDS="${FUZZ_SEEDS:-1 2 3 4}"

run_one() {  # run_one <seed> -- 0 means the fixed route with no fuzzing
    local seed=$1 dir="run-$1"
    rm -rf "$dir"; mkdir -p "$dir"
    # `|| st=$?`: a surviving run ends in timeout's 124, and under set -e a
    # bare nonzero status would abort here before recording it.
    # Fuzz seeds also get POKE_TEST_BATTLES: a wild battle against a random
    # species whenever the player is free, which is how battle scripts,
    # controllers and move animations get exercised this early in the story.
    local st=0 battles=""
    [ "$seed" != 0 ] && battles="POKE_TEST_BATTLES=1"
    ( cd "$dir" && env $battles SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy POKE_TIMESCALE=20 \
        POKE_FUZZ="$seed" POKE_AUTOKEYS="$AUTOKEYS" \
        timeout "$RUN_SECONDS" ../pokeemerald > run.log 2>&1 ) || st=$?
    echo "$st" > "$dir/status"
}

log "Running route + fuzz seeds ($SEEDS) for ${RUN_SECONDS}s each at 20x"
for seed in 0 $SEEDS; do run_one "$seed" & done
wait

fail=0
for seed in 0 $SEEDS; do
    dir="run-$seed"; status=$(cat "$dir/status")
    reached=$(grep -a "autokeys frame" "$dir/run.log" | tail -1 | sed 's/.*autokeys //')
    if [ "$status" -eq 124 ]; then
        echo "PASS seed $seed: survived, last: $reached"
    else
        echo "FAIL seed $seed: exit $status, last: $reached"
        [ -f "$dir/pokeemerald-crash.txt" ] && cat "$dir/pokeemerald-crash.txt"
        # Resolve the crash against this binary's symbols right here, so the
        # log names the function instead of leaving an offset to look up.
        if [ -f "$dir/pokeemerald-crash.txt" ]; then
            M=$(nm pokeemerald | awk '$3=="main"{print $1}')
            for d in $(sed -n 's/^PC: .*(main+\([0-9]*\)).*/\1/p' "$dir/pokeemerald-crash.txt") \
                     $(sed -n 's/^[0-9]*: main+\([0-9]\{1,8\}\)$/\1/p' "$dir/pokeemerald-crash.txt" | head -8); do
                addr2line -f -e pokeemerald "$(printf '0x%x' $((16#$M + d)))" | head -1
            done | sed 's/^/    at /'
        fi
        fail=1
    fi
done
[ "$fail" -eq 0 ] || { log "FAIL: see above"; exit 1; }
log "PASS: route and all fuzz seeds survived"
