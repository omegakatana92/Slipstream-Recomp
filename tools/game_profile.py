"""
Name:        game_profile.py
Description: what the shared arcade-decomp core needs to know about Slip Stream: where the game is,
             its ROM set, its hardware and the settings of its V60 program

The core (tools/core, a submodule) is shared by the Sega System 32 decompilations. This module gives it
Slip Stream's ROM set module (slipstrm_rom: the regions as the board has them), the names the generated
files carry, and the decompiler's settings for the program (work RAM base, the register that holds it,
the structures and the sound board). Nothing here is game data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

import slipstrm_rom as rom  # noqa: E402
from decompiler import constants
from decompiler import dataflow
from decompiler import function
from decompiler import memory
from decompiler import pointers
from decompiler import signatures

ROOT = Path(__file__).resolve().parents[1]
GAME = "Slip Stream (arcade, Sega System 32)"
ROM_SET_TITLE = "Slip Stream (slipstrm, Brazil 950515)"
CPU = "V60"
GUARD = "SLIPSTREAM"
BINARY = "slipstream"

# The V60 keeps work RAM's base in R15 (0x200000); the frame loop polls 0x20382C through it.
WORK_RAM = (0x200000, 0x210000)
VARIABLES = 0x200000
VIDEO_RAM = (0x300000, 0x320000)
SPRITE_RAM = (0x400000, 0x420000)
PALETTE_RAM = (0x600000, 0x610000)

pointers.STRUCTS = {}
pointers.VARIABLES = VARIABLES
pointers.PLAYERS = (0, 0, 0)
pointers.CONTEXT_KINDS = {}
pointers.OBJECT_REGISTERS = ()
pointers.OWN_REGISTERS = ()
pointers.WORK_RAM = WORK_RAM
memory.WORK_RAM = WORK_RAM
memory.VARIABLES = VARIABLES
memory.PLAYER_FIELDS = ()
memory.BUS_ONLY = []
memory.CANONICAL = rom.canonical_address
memory.NOTES = {
    "variables": ["/* the game's variables in work RAM, reached from R15 (0x200000) */"],
    "scoped": ["/* work RAM as one family of functions uses it (their scratch variables) */"],
    "tables": ["/* data in the program ROM the code reads */"],
    "hardware": ["/* the board's registers (read and written through the bus) */"],
}
signatures.CONTEXT = (15,)
signatures.INITIAL = {32: 0x20F780}
signatures.SCRATCH_CONTEXT = {15: 0x200000}
signatures.CONSTANT = {15: VARIABLES}
constants.GLOBALS_BASE = 15
constants.GLOBALS_VALUE = VARIABLES
dataflow.HANDLER_SLOTS = ()

# The board's I/O and interrupt controller are ordinary memory registers (s32/hardware notes).
function.INTERRUPTS_BEFORE_POLL = True
function.FRAME_COUNTER = "frame_ready"

# The sound board is System 32's: Z80, two YM3438s, an RF5C68.
SOUND_HARDWARE = [(0xA000, 0xC000, "SAMPLE_BANK"), (0xC000, 0xD000, "PCM"), (0xD000, 0xE000, "PCM_RAM")]
SOUND_NOTES = {
    "variables": ["/* the sound program's variables, in the RAM it shares with the V60 (E000-FFFF) */"],
    "scoped": ["/* shared RAM as one family of functions uses it */"],
    "tables": ["/* data in the program ROM the code reads */"],
    "hardware": ["/* the sample bank's window and the RF5C68 (read and written through the bus) */"],
}
