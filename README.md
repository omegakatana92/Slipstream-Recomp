# Slip Stream — native recompilation (Sega System 32)

A source-level reconstruction of Capcom's 1995 arcade racer **Slip Stream** (Brazil 950515) from its
Sega System 32 hardware. The program is translated from the player's own ROM into C, the board is
modeled in C, and the result builds as a native Windows executable and (on Linux) an AppImage.

This is a **work in progress**. See [BUILD_STATUS.md](BUILD_STATUS.md) for what is verified and what
is not. Do not treat it as a finished, playable port yet.

## What is here

| Path | Contents |
|---|---|
| `src/cpu/v60.c` | runtime for the translated V60 program: status, interrupts, task instructions, frame loop |
| `src/game/` | System 32 board model: memory map, 315-5296 I/O, EEPROM, interrupts, timers, MSM6253 ADC |
| `src/graphics/video.c` | System 32 video: four tilemaps, text, bitmap, sprite buffers, mixer |
| `src/audio/` | sound-board memory/ports, YM3438, RF5C68, and the original Z80 program on MAME's Z80 core |
| `src/main/` | headless test runner and SDL2 window |
| `include/` | board, V60 and sound headers |
| `tools/` | ROM verification, region extraction, translation driver, reference runner |
| `tools/core/` | [arcade-decomp](https://github.com/cheviman/arcade-decomp) (BSD-3-Clause, git submodule) |
| `tests/` | automated ROM, translation and reference-comparison tests |
| `docs/` | design notes |
| `build_windows.ps1`, `build_appimage.sh` | end-to-end builds |

`ROM_ANALYSIS.md` documents the ROM set and hardware. No ROM, BIOS, extracted art, audio or
translated program is in this repository.

## Requirements

- Python 3.10+, CMake 3.20+, Git, a C11/C++17 compiler (Visual Studio Build Tools on Windows)
- SDL2 development files for the windowed port (Windows: `SDL2-devel-2.32.x-VC.zip`; Linux:
  `libsdl2-dev`). Without SDL2 the headless build is still made.
- The player's own MAME `slipstrm.zip` (CRC/SHA checked), placed in `rom/` or passed to the scripts.

## Build (Windows)

```powershell
# put MAME's slipstrm.zip in rom\slipstrm.zip
.\build_windows.ps1
```

The script verifies the ROM, builds the MAME reference, records a 30-second execution trace,
translates the program into `build/generated/`, and builds:

```
build\bin\slipstream.exe           windowed (SDL2.dll beside it)
build\bin\slipstream_headless.exe  state/video hashes
build\bin\slipstream_ref.exe       MAME V60 reference
```

Run:

```powershell
.\build\bin\slipstream.exe --regions build\regions
```

## Build (Linux / Steam Deck)

```bash
sudo apt install build-essential cmake ninja-build python3 libsdl2-dev
cp ~/roms/slipstrm.zip rom/
./build_appimage.sh
```

This produces `SlipStream-SteamDeck-x86_64.AppImage`. It contains no game data; on first run it looks
for `~/.local/share/slipstream/slipstrm.zip` (or `SLIPSTREAM_REGIONS`), extracts the regions from your
own ROM with the bundled `extract_regions.py`, and starts the game.

## Controls

| Control | Keyboard | Xbox controller |
|---|---|---|
| Steering | Left/Right or A/D | left stick |
| Accelerator | Up or W | right trigger |
| Brake | Down or S | left trigger |
| Gear change | Space | A |
| Coin | 5 | Back |
| Start | 1 | Start |
| Service / test | 9 / F2 | — |
| Fullscreen | F11 | — |
| Quit | Esc | — |

## How the translation works

`tools/recompile.py` drives the shared core's static analysis and C emitter. It reads the V60 program
image, follows the code the reference executed, and writes one C function per translated function.
Calls through registers and jump tables become calls through the translated entry table. The four
supervisor instructions the scaffold does not lift (`ldtask`, `sttask`, `chlvl`, `rvbit`) are
translated to runtime helpers that follow MAME's V60 core.

The board runtime is the System 32 model from `segasonic-decomp` (BSD-3-Clause), adapted here for
Slip Stream's analog cabinet, its 16-bit data ROM pair, palette/mixer and 4 MB sprite region.

## Credits

This project is built on **[arcade-decomp](https://github.com/cheviman/arcade-decomp)** by
**Sebastian Toyos ([@cheviman](https://github.com/cheviman))** — the V60/V70 frontend, static analysis,
decompiler/translation scaffold, Z80 frontend and System 32 reference tools — and on his
[segasonic-decomp](https://github.com/cheviman/segasonic-decomp) System 32 runtime. See
[CREDITS.md](CREDITS.md). Please preserve his BSD-3-Clause notices.

## Legal

Original project code is offered under the **PolyForm Noncommercial License 1.0.0** where legally
applicable. Reused BSD-3-Clause code (arcade-decomp, segasonic-decomp runtime, MAME cores) keeps its
own license and notices; see `LICENSE` and `THIRD_PARTY_NOTICES.md`.

Slip Stream, its ROMs and artwork are © Capcom. This project ships none of them. You must own the
arcade board or a licensed copy of its ROMs to use it. The translated C is generated from your ROM
and must not be redistributed.
