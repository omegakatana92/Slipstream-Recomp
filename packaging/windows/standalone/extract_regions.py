"""Extract the Slip Stream board regions from the player's own MAME 'slipstrm' set.

Usage: python extract_regions.py <slipstrm.zip or folder> [regions folder]
       (default regions folder: regions)

The files this writes are the user's game data. Keep them private; do not redistribute them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slipstrm_rom as rom


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("slipstrm.zip")
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("regions")
    output.mkdir(parents=True, exist_ok=True)
    files = rom.load_set(source)
    for name, data in (
        ("program.bin", rom.build_program(files)),
        ("tiles.bin", rom.build_tiles(files)),
        ("sprites.bin", rom.build_sprites(files)),
        ("sound.bin", rom.build_sound(files)),
    ):
        (output / name).write_bytes(data)
        print(f"{name:14} {len(data):9} bytes")
    print(f"written to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
