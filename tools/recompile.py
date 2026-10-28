"""
Name:        recompile.py
Description: translates Slip Stream's V60 program into C with the shared arcade-decomp core

The core's scaffold does the translation one instruction at a time. This driver adds what this game
needs and the core does not know yet:

  * unused interrupt vectors (the table holds 0 in many entries) are not code entry points;
  * the frame wait polls a 0/1 byte through R15 (the base of work RAM), not an absolute address;
  * four supervisor instructions (ldtask, sttask, chlvl, rvbit) are translated into calls to
    runtime helpers that follow MAME's V60 core.

Nothing this writes may be redistributed: it is the game's code, translated from the user's own ROM.
"""
import sys
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
ROOT = game_profile.ROOT
import disassemble  # noqa: E402
import recompile as core  # noqa: E402  (the shared scaffold)
from v60 import codegen  # noqa: E402
from v60 import disassembler as dis  # noqa: E402

FUNCTIONS_PER_FILE = 120
RESET_ADDRESS = 0xFFFFFFF0
FRAME_READY = 0x20382C          # the byte the frame loop polls (0, then 1 when VBLANK starts)


class Program(core.Program):
    """The core's program with this game's entry points and frame loop."""

    def __init__(self, image, symbols, executed, called):
        self.image = image
        self.mem = game_profile.rom.ProgramMemory(image)
        self.symbols = symbols

        entries = [(RESET_ADDRESS, "func")]
        table = next(address for address, symbol in symbols.items() if symbol.name == "vector_table")
        vector_targets = [self.mem.r32(table + vector * 4) for vector in range(256)]
        used = [target for target in vector_targets if target]
        default_handler = Counter(used).most_common(1)[0][0]
        # VBLANK start/end, the sound interrupt, and the level-change handler the game uses (24)
        for vector in (2, 0x18, 0x40, 0x41, 0x42, 0x43, 0x44):
            if vector_targets[vector]:
                entries.append((vector_targets[vector], "func"))
        entries.append((default_handler, "func"))
        entries += [(address, "func") for address in sorted(called)]
        # Task switches resume at a saved PC inside another routine. The scaffold makes every
        # executed instruction start a callable entry, so RETIS can land on any of them.
        entries += [(address, "func") for address in sorted(executed)]
        entries += [(address, "func") for address, symbol in sorted(symbols.items())
                    if symbol.kind == "func" and address in executed]

        self.analysis = disassemble.Analysis(image, symbols, executed, fold_mirrors=False, entries=entries)
        self.analysis.run()
        problems = self.analysis.invalid + self.analysis.overlaps + self.analysis.trace_conflicts
        if problems:
            raise SystemExit(f"The analysis is not clean: {problems[:5]}")

        instructions = self.analysis.instructions
        self.entries = {address for address, kind in self.analysis.labels.items()
                        if kind == "func" and address in instructions}
        self.entries.add(core.key(RESET_ADDRESS))
        for table_entries in self.analysis.call_tables.values():
            self.entries.update(table_entries)
        for origin, targets in self.analysis.pointer_tables.items():
            if instructions[origin].flow == dis.FLOW_CALL:
                self.entries.update(targets)

        self.bodies = {}
        for entry in sorted(self.entries):
            self.bodies[entry] = self.walk(entry)
        covered = set().union(*self.bodies.values())
        self.orphans = sorted(address for address in instructions if address not in covered)
        while True:
            covered = set().union(*self.bodies.values())
            starts = [address for address in self.orphans if address not in covered]
            if not starts:
                break
            self.entries.add(starts[0])
            self.bodies[starts[0]] = self.walk(starts[0])
        self.split_shared_code()

        self.names = self.choose_names()
        self.frame_hooks = self.frame_loop_hooks()

    def frame_loop_hooks(self):
        named = {symbol.name: address for address, symbol in self.symbols.items()}
        loop = self.analysis.instructions.get(named["frame_wait_loop"])
        if loop is None or not loop.operands:
            raise SystemExit("symbols.txt: frame_wait_loop is not an instruction that reads the frame counter")
        counter = loop.operands[0]
        if counter.reg != 15 or counter.mode not in ("disp", "direct"):
            raise SystemExit(f"frame_wait_loop reads {counter.mode} R{counter.reg}, not R15 + 0x382C")
        address = game_profile.constants.GLOBALS_VALUE + counter.disp
        if address != FRAME_READY:
            raise SystemExit(f"frame_wait_loop polls {address:06X}, expected {FRAME_READY:06X}")
        # the board's VBLANK events (and their interrupts) run while the game waits, before the poll
        wait = [f"v60_frame_wait({codegen.const(address)});",
                f"if (v60_take_interrupts({codegen.const(loop.address)}))",
                f"\tv60_frame_wait({codegen.const(address)});"]
        return {
            loop.address: ["{"] + [f"\t{line}" for line in wait] + ["}"],
            named["frame_wait_done"]: ["v60_frame_end();"],
        }


class FunctionWriter(core.FunctionWriter):
    """The core's writer, plus the V60's task and bit-reverse instructions."""

    def jump(self, block, instruction):
        # A computed jump without a table the analysis could describe goes through the translated
        # entry table at run time: task code and dispatch tables reach addresses a static switch
        # cannot list completely.
        if instruction.target is not None:
            return [self.transfer(instruction.target)]
        location = block.address_of(instruction.operands[0], 0, "target")
        if location.register is not None:
            raise codegen.Unsupported("jmp to a register")
        return ["{"] + [f"\t{line}" for line in block.lines] + [
            f"\tv60_jump_from({location.address}, {codegen.const(instruction.address)});",
            f"\t{self.resume()}",
            "}"]

    def instruction_lines(self, instruction):
        return self._instruction_lines(instruction)

    def _instruction_lines(self, instruction):
        mnemonic = instruction.mnemonic
        if mnemonic not in ("ldtask", "sttask", "chlvl", "rvbit"):
            return super().instruction_lines(instruction)

        address = instruction.address
        next_address = address + instruction.length
        block = codegen.Block(self.program.mem)
        if mnemonic == "ldtask":
            mask = block.read_value(instruction.operands[0], 2, "mask")
            location = block.address_of(instruction.operands[1], 2, "task_address")
            if location.register is not None:
                raise codegen.Unsupported("ldtask from a register")
            # the instruction's second operand holds a pointer to the task descriptor
            task = block.temp("const uint32_t", "task", f"mem_read32({location.address})")
            block.emit(f"v60_ldtask({mask}, {task});")
            return ["{"] + [f"\t{line}" for line in block.lines] + ["}"]
        if mnemonic == "sttask":
            mask = block.read_value(instruction.operands[0], 2, "mask")
            block.emit(f"v60_sttask({mask});")
        elif mnemonic == "chlvl":
            level = block.read_value(instruction.operands[0], 2, "level")
            value = block.read_value(instruction.operands[1], 2, "value")
            block.emit(f"v60_chlvl({level}, {value}, {codegen.const(next_address)});")
            return ["{"] + [f"\t{line}" for line in block.lines] + ["}"] + [
                f"if (!v60_returned_to({codegen.const(next_address)}, {codegen.const(address)})) {{ {self.resume()} }}"]
        else:   # rvbit
            value = block.read_value(instruction.operands[0], 0, "value")
            dest = block.address_of(instruction.operands[1], 0, "dest")
            if dest.register is not None:
                block.emit(f"reg_write8({dest.register}, v60_rvbit({value}));")
            else:
                block.emit(f"mem_write8({dest.address}, (uint8_t)v60_rvbit({value}));")
        return ["{"] + [f"\t{line}" for line in block.lines] + ["}"]


def main():
    arguments = sys.argv[1:]
    options = {"--trace": [], "--calls": []}
    for option in options:
        while option in arguments:
            position = arguments.index(option)
            end = position + 1
            while end < len(arguments) and not arguments[end].startswith("--"):
                end += 1
            options[option] += arguments[position + 1:end]
            del arguments[position:end]
    source = Path(arguments[0]) if arguments else ROOT / "rom"

    image = game_profile.rom.build_program(game_profile.rom.load_set(source))
    symbols = disassemble.load_symbols(ROOT / "symbols.txt")
    executed, _ = disassemble.load_trace(options["--trace"], fold_mirrors=False)
    called, _ = disassemble.load_trace(options["--calls"], fold_mirrors=False)
    program = Program(image, symbols, executed, called)

    out_dir = ROOT / "build" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("program_*.c"):
        old.unlink()

    entries = sorted(program.entries)
    prototypes = [f"void {program.names[entry]}(void);" for entry in entries]
    (out_dir / "program.h").write_text(
        core.HEADER + f"#ifndef {game_profile.GUARD}_PROGRAM_H\n#define {game_profile.GUARD}_PROGRAM_H\n\n"
        + "\n".join(prototypes) + "\n\n#endif\n", encoding="ascii")

    failures = []
    for number, first in enumerate(range(0, len(entries), FUNCTIONS_PER_FILE)):
        functions = []
        for entry in entries[first:first + FUNCTIONS_PER_FILE]:
            try:
                functions.append(FunctionWriter(program, entry).write())
            except codegen.Unsupported as problem:
                failures.append((entry, str(problem)))
        text = core.HEADER + '#include "v60/registers.h"\n#include "v60/ops.h"\n#include "v60/arith.h"\n#include "program.h"\n\n'
        (out_dir / f"program_{number:02}.c").write_text(text + "\n\n".join(functions) + "\n", encoding="ascii")

    table = [f"\t{{ {codegen.const(entry)}, {program.names[entry]} }}," for entry in entries]
    (out_dir / "entries.c").write_text(
        core.HEADER + '#include "v60/code.h"\n#include "program.h"\n\nconst v60_code_entry v60_code_entries[] =\n{\n'
        + "\n".join(table) + f"\n}};\n\nconst size_t v60_code_entry_count = {len(entries)};\n", encoding="ascii")

    instructions = sum(len(body) for body in program.bodies.values())
    print(f"functions:      {len(entries)}")
    print(f"instructions:   {instructions} written ({len(program.analysis.instructions)} distinct)")
    print(f"orphan starts:  {len(program.orphans)}")
    print(f"not translated: {len(failures)}")
    for entry, problem in failures[:20]:
        print(f"  {entry:06X}  {problem}")
    print(f"Output: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
