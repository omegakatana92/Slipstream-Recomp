# Architecture

```
ROM set (user's slipstrm.zip)
        │  tools/slipstrm_rom.py: CRC/SHA check, regions as the board lays them
        ▼
build/regions/{program,tiles,sprites,sound}.bin
        │
        ├── tools/reference/slipstream_ref.cpp  (MAME V60 + board model)
        │        └── execution trace (addresses executed/called)
        │
        └── tools/recompile.py  (arcade-decomp core)
                 └── build/generated/*.c  (one C function per translated function)
                          │
        ┌─────────────────┴──────────────────┐
        ▼                                    ▼
slipstream_headless                 slipstream (SDL2)
state/video hashes                  window, input, 60 Hz presentation
```

## Layers

- **Translated program** (`build/generated/`): the V60 program as C. Registers are globals; memory is
  read and written through the board bus. Calls through registers go through the translated entry
  table; four supervisor instructions call runtime helpers.
- **CPU runtime** (`src/cpu/v60.c`): PSW and flags, interrupt entry/return, task load/save and level
  change, division/string/bit-string helpers, the frame loop hooks.
- **Board** (`src/game/`): memory map, 315-5296 I/O and EEPROM, interrupt controller and timers,
  random register, MSM6253 ADC, palette and mixer. Frame timing is the scaffold's: board events run
  while the program waits for its frame.
- **Video** (`src/graphics/video.c`): draws each frame from video/sprite/palette/mixer RAM into
  320/416×224 RGB. It is the System 32 renderer from `segasonic-decomp`, byte-compatible with MAME's
  `segas32_v.cpp` in the reference comparison.
- **Audio** (`src/audio/`): sound-board memory/ports and the YM3438/RF5C68. The Z80 program is not
  translated yet; there is no sound CPU in the runtime.
- **Ports**: `src/main/main_headless.c` for deterministic tests, `src/main/main_sdl2.c` for play.

## Determinism

Instructions take no time. Board events and interrupts run at the frame wait (`v60_frame_wait` /
`v60_take_interrupts`), one event per poll, exactly as `tools/reference/slipstream_ref.cpp` runs them
with MAME's V60. Both write the same FNV-1a hash of work RAM (except the V60 stacks), video RAM,
sprite RAM, palette and mixer after every frame. This is the property the tests check.

The model is deliberately not MAME's wall-clock timeline. Slip Stream's boot copies palette data in a
loop that waits for VBLANK; running the boot with no time makes that copy read the wrong data. See
`BUILD_STATUS.md`; this is the open boot-timing issue.
