# Third-party notices

This project is built on, and contains code from, the following projects. Their licenses apply to the
files named, not to the project as a whole.

## arcade-decomp

`tools/core/` is a git submodule of <https://github.com/cheviman/arcade-decomp>, BSD 3-Clause
License. It provides the V60 disassembler and lift, the static analysis and the translation scaffold.
Its license is in `tools/core/LICENSE`; its MAME-derived reference sources are under
`tools/core/system32/reference/mame/LICENSE`.

## segasonic-decomp runtime

The System 32 board model in `src/game/`, the video library in `src/graphics/`, the sound-board code
in `src/audio/`, the V60 runtime in `src/cpu/` and the headers in `include/` are adapted from
<https://github.com/cheviman/segasonic-decomp> (BSD 3-Clause License, Copyright Sebastian Toyos).
The files carry their original headers. Changes for Slip Stream: the analog MSM6253 input, the
palette/mixer observations above, the V60 task instructions, and the port's entry points.

Their behavior follows MAME's System 32 drivers and CPU cores (BSD 3-Clause, MAME contributors),
including `sega/segas32.cpp`, `sega/segas32_v.cpp`, `cpu/v60`, the Z80, the 315-5296 I/O chip, the
93C46 EEPROM, the MSM6253 ADC, the YM3438 and the RF5C68.

## MAME

The reference runner `tools/reference/slipstream_ref.cpp` is linked against MAME's V60 core from
`tools/core/system32/reference/mame/` (BSD 3-Clause, MAME contributors; see that directory's
LICENSE). It is a development tool, never part of the game.

## SDL2

The windowed port links SDL2 (<https://www.libsdl.org/>, zlib License). On Windows the build script
downloads the official VC development package; `SDL2.dll` is copied beside the executable.

## Capcom / Sega

Slip Stream, its program, graphics, music and sound effects are © Capcom. The System 32 hardware
design is Sega's. No ROM, BIOS, artwork, audio or translated program is distributed here.
