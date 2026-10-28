"""Build the board's regions from the user's ROM set into build/regions/.

These are raw bytes of the user's game, for local development and running the port. They are never
committed and never shipped: a release loads the player's own ROM set instead.

Usage: python tools/extract_regions.py [rom folder or .zip] [output folder]
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path[:0] = [str(TOOLS / "core"), str(TOOLS)]
import game_profile  # noqa: E402
import slipstrm_rom as rom  # noqa: E402


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else game_profile.ROOT / "rom"
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else game_profile.ROOT / "build" / "regions"
    output.mkdir(parents=True, exist_ok=True)
    files = rom.load_set(source)
    regions = {
        "program.bin": rom.build_program(files),
        "tiles.bin": rom.build_tiles(files),
        "sprites.bin": rom.build_sprites(files),
        "sound.bin": rom.build_sound(files),
    }
    for name, data in regions.items():
        (output / name).write_bytes(data)
        print(f"{name:14} {len(data):9} bytes")
    print(f"written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
