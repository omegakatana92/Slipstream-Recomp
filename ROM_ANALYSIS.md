# ROM analysis — Slip Stream

## Identification

| | |
|---|---|
| Title | Slip Stream (Brazil, 950515) |
| MAME set | `slipstrm` (parent; `slipstrmh` is the Hispanic revision) |
| Publisher | Capcom |
| Hardware | Sega System 32, analog cabinet ("A/D BD NO. 837-7536") |
| Sound board | System 32 sound PCB: Z80, two YM3438, RF5C68 |
| Main CPU | NEC V60, 16.10795 MHz (32.2159 MHz crystal / 2) |
| Sound CPU | Zilog Z80, 8.053975 MHz (32.2159 MHz / 4) |
| Video | 320×224 (MAME output; the board's 416-pixel mode exists), 4 tilemaps + text + bitmap + sprite layers |
| Protection | None specific to this game (MAME's `init_slipstrm` is the common System 32 init). No FD1149/317-0213. |
| Parent/BIOS | None. The set is self-contained; the sound program and PCM data are in its own sound ROMs. |

Verified against MAME 0.289's `src/mame/sega/segas32.cpp`, `ROM_START(slipstrm)`, and the local
System 32 driver copy. Every file was checked by CRC32 and SHA-1.

## ROM files

| File | Size | CRC32 | SHA-1 | Board region |
|---|---:|---|---|---|
| `s32b_prg01.ic6` | 0x80000 | `7d066307` | `d87e04167263b435b77830db02ed58651ccc020c` | V60 program (loaded twice: 000000 and 080000) |
| `s32_dat00.ic14` | 0x80000 | `c3ff6309` | `dcc857736fe0f15aa7909c3ee88a7e239c8f0228` | data ROM, even bytes at 100000 |
| `s32_dat01.ic7` | 0x80000 | `0e605c81` | `47c64195cab9a07b234d5a375d26168e53ffaa17` | data ROM, odd bytes at 100001 |
| `s32_scr00.ic38` | 0x80000 | `3cbb2d0b` | `b94006347b72cd60a889b0e279f62f677cedfd2e` | tiles, 32-bit lane 0 |
| `s32_scr01.ic34` | 0x80000 | `4167be55` | `96b34d311b318c00c3fad917e341589a70ba0a15` | tiles, lane 2 |
| `s32_scr02.ic29` | 0x80000 | `52c4bb85` | `4fbee1072a19c75c25b5fd269acc75640923d69c` | tiles, lane 1 |
| `s32_scr03.ic25` | 0x80000 | `4948604a` | `d5a1b9781fef7976a59a0af9b755a04fcacf9381` | tiles, lane 3 |
| `s32_obj00.ic36` | 0x80000 | `cffe9e0d` | `5272d54ff142de927a9abd61f3646e963c7d22c4` | sprites, byte lane 0 |
| `s32_obj01.ic32` | 0x80000 | `4ebd1383` | `ce35f4d15e7904bfde55e58cdde925cba8002763` | sprites, lane 1 |
| `s32_obj02.ic27` | 0x80000 | `b3cf4fe2` | `e13199522e1e3e8b9cfe72cc29b33f25dad542ef` | sprites, lane 2 |
| `s32_obj03.ic23` | 0x80000 | `c6345391` | `155758097911ffca0c5c0b2a24a8033339dcfcbb` | sprites, lane 3 |
| `s32_obj04.ic37` | 0x80000 | `2de4288e` | `8e794f79f506293edb7609187a7908516ce76849` | sprites, lane 4 |
| `s32_obj05.ic33` | 0x80000 | `6cfb74fb` | `b74c886959910cd069427418525b23300a9b7b18` | sprites, lane 5 |
| `s32_obj06.ic28` | 0x80000 | `53234bf4` | `1eca538dcb86e44c31310ab1ab42a2b66b69c8fe` | sprites, lane 6 |
| `s32_obj07.ic24` | 0x80000 | `22c129cf` | `0f64680511a357038f6a556253c13fbb5417dd1a` | sprites, lane 7 |
| `s32_snd00.ic35` | 0x20000 | `0fee2278` | `7533a03c3fc46d65dfdd07bddf1e6e0bbc368752` | Z80 program (loaded 8×) |
| `s32_snd01.ic31` | 0x80000 | `ae7be5f2` | `ba089355e64864435bcc3b0c208e4bce1ea66295` | PCM bank (loaded 2× at 100000) |

Total 2,529,576 bytes. Checksums were read from the supplied archive and matched MAME's
`ROM_START(slipstrm)`.

## Program image

The V60 sees a 2 MB region:

```
000000-07FFFF  s32b_prg01.ic6
080000-0FFFFF  s32b_prg01.ic6 again (ROM_LOAD_x2)
100000-1FFFFF  s32_dat00.ic14 (even) + s32_dat01.ic7 (odd), 16-bit interleaved
```

The reset vector lives at `0FFFF0` (the bus mirrors `000000-0FFFFF` at `F00000-FFFFFF`). It is
`jmp 081000`. The boot sets `SP=20F780`, `SBR=080000`, `L0SP=210000`, `SYCW=0970`, then builds the
initial task from the descriptor at `081C24` and enters the game. The vector table is at `080000`;
vector 0x40 is VBLANK start, 0x41 VBLANK end, 0x43 the sound interrupt, 0x18 the level-change
exception used by the cooperative task switch.

The game keeps work RAM's base in **R15 = 0x200000** and the frame-ready byte at **0x20382C**
(the frame loop is `081B3A`).

## Memory map (V60)

| Address | Contents |
|---|---|
| `000000-1FFFFF` | program/data ROM |
| `200000-20FFFF` | work RAM (mirrored through 2FFFFF) |
| `300000-31FFFF` | video RAM |
| `400000-41FFFF` | sprite RAM |
| `500000-50000F` | sprite control |
| `600000-60FFFF` | palette RAM (`xBBBBBGGGGGRRRRR`; upper window in alternate format) |
| `610000-61007F` | mixer/priority registers |
| `700000-701FFF` | shared RAM with the Z80 |
| `800000-801002` | System 32 communication board |
| `C00000-C0001F` | 315-5296 I/O chip |
| `C00050-C00057` | MSM6253 4-channel A/D converter |
| `D00000-D0000F` | interrupt controller |
| `D80000-DFFFFF` | random number generator |
| `F00000-FFFFFF` | mirror of `000000-0FFFFF` |

## Interrupts and timing

One frame is 262 lines at 60 Hz. VBLANK starts at line 224 and ends with the frame; the sprite list is
processed 50 µs after VBLANK. Timer 0/1 come from the V60's internal counters, controlled through
`D00000`. The VBLANK handler increments a frame counter at `0x203838`, drives the sprite list, and
sets the frame-ready byte.

## Controls

The cabinet is analog: a steering wheel (IN0, centered at 0x80), accelerator (IN1), brake (IN2), and an
unused fourth channel. The gear change is a toggle on player 1 button 1. Coin/start/service/test are on
the 315-5296 ports. There is no trackball.

## Dependencies and limitations

- No BIOS, parent set or CHD is required.
- The program ROM is the Brazil revision (`s32b_prg01.ic6`); the Hispanic revision differs only in
  that chip.
- The sound program and PCM samples are present; the port does not yet run them (see BUILD_STATUS).
