# Build status

Last updated: 2026-10-28. Development host: Windows 11 x64, LLVM/Clang, MAME 0.289 for ground truth.

## Verified

- [x] **ROM set** — `python tools/verify_rom.py "…/slipstrm.zip"` checks all 16 files by CRC32,
      SHA-1 and size against MAME's `slipstrm`. All pass.
- [x] **Program image** — the 2 MB V60 image built by `tools/slipstrm_rom.py` is byte-identical to the
      region MAME exposes at reset (compared over the whole 2 MB).
- [x] **Static translation** — 1,530 functions, 1,846 instructions written, 0 untranslated. The four
      supervisor instructions (`ldtask`, `sttask`, `chlvl`, `rvbit`) are implemented from MAME's V60
      semantics. Computed jumps go through the translated entry table.
- [x] **Board boot and execution** — the translated program boots, runs the cooperative task switch,
      takes VBLANK interrupts and completes 30 s of game time without stopping.
- [x] **Frame-by-frame state** — `slipstream_headless --frames 1800 --hashes native.txt` against
      `slipstream_ref --frames 1800 --hashes reference.txt` (same board model, MAME's V60 executing the
      original ROM) matches on **all 1800 frames** (work RAM except the V60 stacks, video RAM, sprite
      RAM, palette, mixer).
- [x] **Video** — during development the port's renderer was compared with MAME's System 32 video
      reference for 120 frames; all frame hashes matched. The reference runner in this repository
      currently compares state only.
- [x] **Analog input** — the MSM6253 4-channel ADC is modeled; adding it changed the game's state from
      the idle 0xFF reading and kept the native/reference comparison exact.
- [x] **Windows builds** — `build/bin/slipstream.exe` (SDL2, x64) builds, copies `SDL2.dll` beside it
      and opens its window; `slipstream_headless.exe` and `slipstream_ref.exe` build.

## Not working yet

- [ ] **Visible gameplay.** The window and the headless renderer show a black frame. The translated
      program's state matches the frame-timed reference, but that reference itself is black when its
      output is compared with real MAME. Root cause, established by dumping both board states:
      - Real MAME runs the boot with time passing: VBLANK interrupts and timers fire while the
        self-test and the palette-copy loop (`08C223`, which copies 0x60 words per iteration and polls
        `0x20382C`) run. The palette copy therefore writes the correct gradient.
      - The toolkit's scaffold lets instructions take no time and runs board events only at the main
        frame loop. The boot's palette copy completes without a single VBLANK; it writes offsets from
        a work-RAM list into palette RAM (`0x00A0`, `0x00E0`, …) instead of the color table at
        `0x108800`, so the rendered picture is black. The mixer registers (priorities) also differ.
      - A cycle-timed reference (`s32ref --timing cycles`) with our board model produces the same
        palette as MAME, confirming the board is right and the timing model is the problem.
      - An experimental per-instruction tick (8 cycles/instruction, interrupts at every instruction)
        was implemented; it reaches further boot code but hits a task entry (`0837D7`) that the
        frame-timed trace never executes, and the cycle-timed reference trace contains addresses in
        unmapped space, so the static analysis cannot yet use it.
- [ ] **Sound.** The Z80 program has not been translated. `src/audio/` has the sound-board memory,
      ports, YM3438 and RF5C68, but no Z80 C program, so there is no audio. MAME's Z80 is not linked
      into the game.
- [ ] **Steam Deck AppImage.** `build_appimage.sh` is complete but has not been run: the development
      host is Windows and no Linux/WSL toolchain was available. No AppImage exists or is claimed.
- [ ] **Complete game coverage.** The trace covers boot plus 30 s of attract/game time. Later modes
      (test menu, races, endings) will execute translated functions only after a longer trace is
      recorded; untranslated targets stop with a clear diagnostic rather than being faked.

## Reproduction

```powershell
$rom = "C:\path\to\slipstrm.zip"
python tools\verify_rom.py $rom
python tools\extract_regions.py $rom build\regions

cmake -S . -B build\cmake -G Ninja -DCMAKE_BUILD_TYPE=Release `
      -DSLIPSTREAM_REFERENCE=ON -DSLIPSTREAM_SDL2=ON
cmake --build build\cmake --target slipstream_ref
build\bin\slipstream_ref.exe --regions build\regions --frames 1800 `
      --trace build\trace\executed.txt --calls build\trace\called.txt
python tools\recompile.py $rom --trace build\trace\executed.txt --calls build\trace\called.txt
cmake --build build\cmake

build\bin\slipstream_headless.exe --regions build\regions --frames 1800 --hashes native.txt
build\bin\slipstream_ref.exe       --regions build\regions --frames 1800 --hashes ref.txt
python tests\run_tests.py
```

## Notes and limitations

- The translated C in `build/generated/` is derived from the user's ROM. It is not committed and must
  not be redistributed.
- The comparison is against the project's frame-timed reference (MAME V60 + the same board model), not
  against MAME's wall-clock timeline; the latter differences are exactly the boot-timing bug above.
- The renderer reports 416×224 from the board's current width register; MAME's output for this
  revision is 320×224. This is part of the unresolved video/mixer state.
