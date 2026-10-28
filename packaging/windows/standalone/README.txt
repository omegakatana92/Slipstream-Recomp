Slip Stream - Windows x64 development build
==========================================

STATUS: development snapshot. The main CPU program is translated and frame-accurate against the
MAME reference, but the game currently renders a black screen because of an unresolved boot-timing
issue. It is not yet playable. See BUILD_STATUS.md in the source repository.

This package contains NO ROM, BIOS, graphics, audio or region data. You must own the arcade board or
a licensed copy of the ROMs.

Requirements
------------
- Windows x64
- Python 3.10+ (only to extract the regions from your own ROM set)
- MAME's slipstrm.zip (Slip Stream, Brazil 950515)

First run
---------
1. Put slipstrm.zip beside this file.
2. Open a terminal in this folder and run:
       python extract_regions.py slipstrm.zip regions
3. Run:
       slipstream.exe --regions regions

The extractor verifies every ROM file by CRC32/SHA-1 before writing the regions. The regions folder
is your game data; do not share it.

Controls
--------
Steering: Left/Right or A/D (or left stick)
Accelerator: Up/W (or right trigger)      Brake: Down/S (or left trigger)
Gear: Space (or A)                        Coin: 5 (or Back)      Start: 1 (or Start)
Service/Test: 9/F2                         Fullscreen: F11        Quit: Esc

Files
-----
slipstream.exe           windowed game (needs SDL2.dll and a regions folder)
slipstream_headless.exe  deterministic state/video hash runner (for tests)
SDL2.dll                 SDL2 2.32.10 runtime (zlib license)
extract_regions.py       builds the board regions from your ROM set
slipstrm_rom.py          ROM checks and region layout used by the extractor
LICENSE.txt              PolyForm Noncommercial 1.0.0
THIRD_PARTY_NOTICES.txt  BSD-3-Clause and other notices

The executable contains C translated from the ROM by the user's own build; do not redistribute this
package as a game. Slip Stream is (c) Capcom. Sega System 32 is Sega's hardware.
