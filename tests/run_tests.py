"""Automated checks for the Slip Stream recompilation.

Usage: python tests/run_tests.py [--rom PATH] [--frames N]

Checks, in order:
  1. the ROM set matches MAME's 'slipstrm' (CRC32/SHA-1);
  2. the board regions exist (or builds them);
  3. the translated program and the native/reference executables exist;
  4. the translated program and the MAME reference agree frame by frame;
  5. the program reaches the requested frame count and reports no unmapped reads;
  6. (Windows) the windowed executable starts and stays alive.
Exit status 0 only when every check passes.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]

import slipstrm_rom as rom  # noqa: E402


def run(command, **kwargs):
    print("+", " ".join(str(part) for part in command), flush=True)
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", default=str(ROOT / "rom"), help="ROM set (.zip or folder)")
    parser.add_argument("--frames", type=int, default=300)
    arguments = parser.parse_args()
    failures = []

    print("== 1. ROM set ==")
    result = run([sys.executable, "tools/verify_rom.py", arguments.rom])
    print(result.stdout.strip().splitlines()[-1] if result.stdout else result.stderr)
    if result.returncode != 0:
        failures.append("ROM verification")

    print("== 2. Board regions ==")
    regions = ROOT / "build" / "regions"
    if not (regions / "program.bin").exists():
        result = run([sys.executable, "tools/extract_regions.py", arguments.rom])
        if result.returncode != 0:
            failures.append("region extraction")
    for name in ("program.bin", "tiles.bin", "sprites.bin"):
        path = regions / name
        print(f"  {name}: {'ok' if path.exists() else 'missing'}")
        if not path.exists():
            failures.append(name)

    print("== 3. Executables and translation ==")
    generated = list((ROOT / "build" / "generated").glob("program_*.c"))
    print(f"  translated program files: {len(generated)}")
    if len(generated) < 5:
        failures.append("translated C")
    headless = ROOT / "build" / "bin" / "slipstream_headless.exe"
    if not headless.exists():
        headless = ROOT / "build" / "bin" / "slipstream_headless"
    reference = ROOT / "build" / "bin" / "slipstream_ref.exe"
    if not reference.exists():
        reference = ROOT / "build" / "bin" / "slipstream_ref"
    for path in (headless, reference):
        print(f"  {path.name}: {'ok' if path.exists() else 'missing'}")
        if not path.exists():
            failures.append(path.name)

    if not failures:
        print(f"== 4. {arguments.frames} frames, translated vs reference ==")
        native_file = ROOT / "build" / "native_hashes.txt"
        reference_file = ROOT / "build" / "reference_hashes.txt"
        native = run([str(headless), "--regions", str(regions), "--frames", str(arguments.frames),
                      "--hashes", str(native_file)])
        for line in native.stdout.splitlines():
            print("  " + line)
        if "unmapped reads:    0" not in native.stdout and "unmapped reads: 0" not in native.stdout:
            failures.append("unmapped reads")
        ref = run([str(reference), "--regions", str(regions), "--frames", str(arguments.frames),
                   "--hashes", str(reference_file)])
        if ref.returncode != 0:
            failures.append("reference run")

        if native_file.exists() and reference_file.exists():
            a = native_file.read_text().splitlines()
            b = reference_file.read_text().splitlines()
            matches = sum(1 for x, y in zip(a, b) if x == y)
            print(f"  frames compared: {len(a)}  matching: {matches}")
            if len(a) != arguments.frames or matches != len(a):
                failures.append("frame mismatch")

    bin_dir = ROOT / "build" / "bin"
    windowed = bin_dir / ("slipstream.exe" if sys.platform == "win32" else "slipstream")
    if windowed.exists() and sys.platform == "win32":
        print("== 5. Windowed executable starts ==")
        process = subprocess.Popen([str(windowed), "--regions", str(regions)],
                                   cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            process.wait(timeout=3)
            alive = False
        except subprocess.TimeoutExpired:
            alive = True
            process.kill()
        print(f"  alive after 3 s: {alive}")
        if not alive:
            failures.append("windowed startup")

    print()
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
