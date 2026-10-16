#!/usr/bin/env bash
# Compiles the pure-Java controls code (no Android needed) and runs its tests,
# then checks the screen-background themes against the real layout.
# usage: run.sh <pokeemerald-multiplatform checkout>
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$1/android/app/src/main/java/com/pokeemerald/experimental/controls"
out="${CONTROLS_TEST_OUT:-$(mktemp -d)}"
javac -sourcepath "" -d "$out" "$src"/*.java "$here"/*.java
java -Djava.awt.headless=true -cp "$out" ControlsTest
# Every theme background, measured under the real layout at several phone
# shapes: calm enough behind each control, labels readable.
java -Djava.awt.headless=true -cp "$out" ThemeCheck "$1"
echo "$out"
