#!/usr/bin/env bash
# Builds the Steam Deck / Linux x86_64 AppImage of the Slip Stream recompilation.
#
# It builds the MAME reference, records the execution trace, translates the player's own ROM to C,
# builds the native game (SDL2), and packs an AppDir into an AppImage. No game data is in the
# AppImage: the first run reads the player's regions (tools/extract_regions.py) or ROM set.
#
# Requirements: Linux x86_64, cmake >= 3.20, gcc/clang, ninja or make, python3, git, SDL2 development
# files (libsdl2-dev), curl or wget. appimagetool is downloaded if missing.
#
# Usage: ./build_appimage.sh [ROM_SET]        (default ROM_SET=rom/)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

ROM="${1:-rom}"
BUILD="$ROOT/build/cmake-linux"
BIN="$ROOT/build/bin"
APP="$ROOT/build/appimage"
VERSION="0.1.0"

die() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }

need cmake
need python3
need git
need gcc
need pkg-config
[ "$(uname -m)" = "x86_64" ] || die "this script builds x86_64 only (Steam Deck is x86_64)"
pkg-config --exists sdl2 || die "SDL2 development files not found (install libsdl2-dev)"

echo "== Shared core =="
if [ ! -f tools/core/system32/reference/mame/v60.cpp ]; then
    git submodule update --init --recursive
fi

echo "== ROM set =="
[ -e "$ROM" ] || die "ROM set not found: $ROM"
python3 tools/verify_rom.py "$ROM"
python3 tools/extract_regions.py "$ROM" build/regions

echo "== Configure and build the reference =="
cmake -S . -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DSLIPSTREAM_REFERENCE=ON -DSLIPSTREAM_SDL2=ON
cmake --build "$BUILD" --target slipstream_ref -j"$(nproc)"

echo "== Trace =="
mkdir -p build/trace
"$BIN/slipstream_ref" --regions build/regions --frames 1800 \
    --trace build/trace/executed.txt --calls build/trace/called.txt

echo "== Translate =="
python3 tools/recompile.py "$ROM" --trace build/trace/executed.txt --calls build/trace/called.txt

echo "== Build the game =="
cmake -S . -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DSLIPSTREAM_REFERENCE=ON -DSLIPSTREAM_SDL2=ON
cmake --build "$BUILD" -j"$(nproc)"

echo "== AppDir =="
rm -rf "$APP"
mkdir -p "$APP/usr/bin" "$APP/usr/share/applications" "$APP/usr/share/icons/hicolor/256x256/apps"
cp "$BIN/slipstream" "$APP/usr/bin/slipstream"

# No ROM or extracted game data is shipped. The user's own set builds the regions on first run.
cp packaging/windows/standalone/extract_regions.py "$APP/usr/bin/extract_regions.py"
cp packaging/windows/standalone/slipstrm_rom.py "$APP/usr/bin/slipstrm_rom.py"
cp packaging/windows/standalone/README.txt "$APP/usr/bin/README.txt"
cp CREDITS.md "$APP/usr/bin/CREDITS.txt"
cp LICENSE "$APP/usr/bin/LICENSE.txt"
cp THIRD_PARTY_NOTICES.md "$APP/usr/bin/THIRD_PARTY_NOTICES.txt"

# A neutral icon drawn for this project (no game art): a wheel on a dark background.
python3 - "$APP/usr/share/icons/hicolor/256x256/apps/slipstream.png" <<'PY'
import struct, sys, zlib
w = h = 256
raw = bytearray()
for y in range(h):
    raw.append(0)
    for x in range(w):
        dx, dy = x - 128, y - 128
        r = (dx * dx + dy * dy) ** 0.5
        if 92 < r < 116:
            c = (230, 235, 240) if (int(r) // 4) % 2 else (40, 44, 60)
        elif r <= 92:
            c = (24, 28, 40)
        else:
            c = (10, 12, 20)
        raw.extend(c)
def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) \
    + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
open(sys.argv[1], "wb").write(png)
PY

cat > "$APP/slipstream.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Slip Stream
Comment=Native recompilation of the Sega System 32 arcade game
Exec=slipstream --regions regions
Icon=slipstream
Categories=Game;ArcadeGame;
Terminal=false
EOF
cp "$APP/slipstream.desktop" "$APP/usr/share/applications/slipstream.desktop"
cp "$APP/usr/share/icons/hicolor/256x256/apps/slipstream.png" "$APP/slipstream.png"

cat > "$APP/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/slipstream"
REGIONS="${SLIPSTREAM_REGIONS:-$DATA/regions}"

if [ ! -f "$REGIONS/program.bin" ]; then
    ROM="$DATA/slipstrm.zip"
    [ -f "$ROM" ] || ROM="$(dirname "$HERE")/slipstrm.zip"
    if [ ! -f "$ROM" ] && command -v zenity >/dev/null 2>&1; then
        ROM=$(zenity --file-selection --title="Select your MAME slipstrm.zip" 2>/dev/null) || ROM=""
    fi
    if [ -n "$ROM" ] && [ -f "$ROM" ] && command -v python3 >/dev/null 2>&1; then
        python3 "$HERE/usr/bin/extract_regions.py" "$ROM" "$REGIONS" || exit 1
    else
        MSG="Slip Stream needs the board regions from your own ROM set.
Put MAME's slipstrm.zip in $DATA/slipstrm.zip and run:
  python3 extract_regions.py slipstrm.zip $REGIONS
(or set SLIPSTREAM_REGIONS). No ROM data is included in this AppImage."
        command -v zenity >/dev/null 2>&1 && zenity --error --text="$MSG"
        echo "$MSG" >&2
        exit 1
    fi
fi
exec "$HERE/usr/bin/slipstream" --regions "$REGIONS" "$@"
EOF
chmod +x "$APP/AppRun" "$APP/usr/bin/slipstream" "$APP/usr/bin/extract_regions.py"

echo "== AppImage =="
TOOL="$ROOT/build/appimagetool-x86_64.AppImage"
if [ ! -x "$TOOL" ]; then
    curl -L -o "$TOOL" https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi
ARTIFACT="$ROOT/SlipStream-SteamDeck-x86_64.AppImage"
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APP" "$ARTIFACT"
chmod +x "$ARTIFACT"
echo "Built: $ARTIFACT"
echo "Smoke test: $ARTIFACT --regions build/regions"
