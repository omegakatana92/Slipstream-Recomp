"""Verify a Slip Stream ROM set file by file (CRC32 + SHA-1), as MAME's 'slipstrm' set.

Usage: python tools/verify_rom.py [rom folder or .zip]   (default: rom/)
Exit status 0 when every file of the set is present and correct.
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
import slipstrm_rom as rom  # noqa: E402


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else game_profile.ROOT / "rom"
    found, report = rom.identify_set(source)
    for line in report:
        print(line)
    missing = sorted(set(rom.ROM_FILES) - set(found))
    print()
    print(f"{len(found)}/{len(rom.ROM_FILES)} files verified from {source}")
    if missing:
        print("The set is incomplete; a complete MAME 'slipstrm' set is required.")
        return 1
    print("The ROM set matches MAME's 'slipstrm' (Slip Stream, Brazil 950515).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
