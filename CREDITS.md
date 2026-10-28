# Credits

## arcade-decomp — Sebastian Toyos ([@cheviman](https://github.com/cheviman))

The core of this project is **[arcade-decomp](https://github.com/cheviman/arcade-decomp)**, created by
**Sebastian Toyos**. It provides:

- the NEC V60/V70 decoder, disassembler and lift to the decompiler IR;
- the static analysis that follows branches, calls, jump tables and stored code pointers;
- the decompiler / translation scaffold and its C writer;
- the System 32 reference tools (MAME's V60 core, the video and sound references);
- the Z80 frontend used by the shared System 32 tooling.

The same author's **[segasonic-decomp](https://github.com/cheviman/segasonic-decomp)** is the source of
the System 32 board runtime, video library, sound-board code, EEPROM/I-O models and V60 runtime that
this port adapts for Slip Stream.

Without his work this recompilation would not exist. Please keep the BSD-3-Clause notices in
`tools/core/LICENSE` and in the adapted runtime files, and credit him in derivative projects.

## MAME

The reference runner uses MAME's V60 core, and the board/video/sound behavior follows MAME's System 32
drivers. Thanks to the MAME contributors (BSD-3-Clause); see
`tools/core/system32/reference/mame/LICENSE`.

## SDL2

The windowed port uses [SDL2](https://www.libsdl.org/) (zlib License).

## Game and hardware

*Slip Stream* is © Capcom. Sega System 32 is Sega's hardware. No ROM, BIOS, artwork or audio is
distributed with this project.
