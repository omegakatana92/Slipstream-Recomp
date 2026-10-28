"""MAME 'slipstrm' ROM set (Slip Stream, Brazil 950515) and Sega System 32 region builders."""
import hashlib
import zipfile
import zlib
from pathlib import Path

# MAME name -> (crc32, sha1, size)
ROM_FILES = {
    "s32b_prg01.ic6": ("7d066307", "d87e04167263b435b77830db02ed58651ccc020c", 0x080000),
    "s32_dat00.ic14": ("c3ff6309", "dcc857736fe0f15aa7909c3ee88a7e239c8f0228", 0x080000),
    "s32_dat01.ic7":  ("0e605c81", "47c64195cab9a07b234d5a375d26168e53ffaa17", 0x080000),
    "s32_obj00.ic36": ("cffe9e0d", "5272d54ff142de927a9abd61f3646e963c7d22c4", 0x080000),
    "s32_obj01.ic32": ("4ebd1383", "ce35f4d15e7904bfde55e58cdde925cba8002763", 0x080000),
    "s32_obj02.ic27": ("b3cf4fe2", "e13199522e1e3e8b9cfe72cc29b33f25dad542ef", 0x080000),
    "s32_obj03.ic23": ("c6345391", "155758097911ffca0c5c0b2a24a8033339dcfcbb", 0x080000),
    "s32_obj04.ic37": ("2de4288e", "8e794f79f506293edb7609187a7908516ce76849", 0x080000),
    "s32_obj05.ic33": ("6cfb74fb", "b74c886959910cd069427418525b23300a9b7b18", 0x080000),
    "s32_obj06.ic28": ("53234bf4", "1eca538dcb86e44c31310ab1ab42a2b66b69c8fe", 0x080000),
    "s32_obj07.ic24": ("22c129cf", "0f64680511a357038f6a556253c13fbb5417dd1a", 0x080000),
    "s32_scr00.ic38": ("3cbb2d0b", "b94006347b72cd60a889b0e279f62f677cedfd2e", 0x080000),
    "s32_scr01.ic34": ("4167be55", "96b34d311b318c00c3fad917e341589a70ba0a15", 0x080000),
    "s32_scr02.ic29": ("52c4bb85", "4fbee1072a19c75c25b5fd269acc75640923d69c", 0x080000),
    "s32_scr03.ic25": ("4948604a", "d5a1b9781fef7976a59a0af9b755a04fcacf9381", 0x080000),
    "s32_snd00.ic35": ("0fee2278", "7533a03c3fc46d65dfdd07bddf1e6e0bbc368752", 0x020000),
    "s32_snd01.ic31": ("ae7be5f2", "ba089355e64864435bcc3b0c208e4bce1ea66295", 0x080000),
}

# The V60 program region as MAME's ROM_START(slipstrm) lays it out:
#   000000-07FFFF  s32b_prg01.ic6
#   080000-0FFFFF  the same chip again (ROM_LOAD_x2)
#   100000-1FFFFF  s32_dat00.ic14 + s32_dat01.ic7 interleaved (ROM_LOAD16_BYTE)
# The CPU runs from the 080000-0FFFFF copy: its reset vector at FFFFF0 jumps to 081000
# and its vector table (SBR = 080000) starts at 080000. Both copies stay distinct.
PROGRAM_AREAS = [(0x000000, 0x100000)]


def read_files(source):
    source = Path(source)
    contents = {}
    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            for entry in archive.infolist():
                if not entry.is_dir():
                    contents[Path(entry.filename).name] = archive.read(entry)
        return contents
    for path in sorted(source.iterdir()):
        if path.is_file():
            contents[path.name] = path.read_bytes()
    return contents


def identify_set(source):
    by_crc = {crc: name for name, (crc, _, _) in ROM_FILES.items()}
    found = {}
    report = []
    for original_name, data in read_files(source).items():
        crc = format(zlib.crc32(data) & 0xFFFFFFFF, "08x")
        mame_name = by_crc.get(crc)
        if mame_name and ROM_FILES[mame_name][1] == hashlib.sha1(data).hexdigest() \
                and len(data) == ROM_FILES[mame_name][2]:
            found[mame_name] = data
            report.append(f"OK      {original_name:20} = {mame_name}")
        else:
            report.append(f"--      {original_name:20} not part of the set (crc {crc})")
    for mame_name in sorted(set(ROM_FILES) - set(found)):
        report.append(f"MISSING {mame_name}")
    return found, report


def load_set(source):
    found, _ = identify_set(source)
    missing = sorted(set(ROM_FILES) - set(found))
    if missing:
        raise SystemExit("The 'slipstrm' ROM set is incomplete. Missing: " + ", ".join(missing))
    return found


def interleave16(even, odd):
    result = bytearray(len(even) * 2)
    result[0::2] = even
    result[1::2] = odd
    return result


def build_program(rom):
    image = bytearray(0x200000)
    image[0x000000:0x080000] = rom["s32b_prg01.ic6"]
    image[0x080000:0x100000] = rom["s32b_prg01.ic6"]
    image[0x100000:0x200000] = interleave16(rom["s32_dat00.ic14"], rom["s32_dat01.ic7"])
    return bytes(image)


def build_tiles(rom):
    """mainpcb:tiles (2 MB): ROM_LOAD32_BYTE lanes 0-3 = scr00, scr02, scr01, scr03."""
    image = bytearray(0x200000)
    for lane, name in enumerate(["s32_scr00.ic38", "s32_scr02.ic29", "s32_scr01.ic34", "s32_scr03.ic25"]):
        image[lane::4] = rom[name]
    return bytes(image)


def build_sprites(rom):
    """mainpcb:sprites (4 MB, 32-bit words big endian): ROM_LOAD64_BYTE lanes 0-7."""
    image = bytearray(0x400000)
    names = ["s32_obj00.ic36", "s32_obj01.ic32", "s32_obj02.ic27", "s32_obj03.ic23",
             "s32_obj04.ic37", "s32_obj05.ic33", "s32_obj06.ic28", "s32_obj07.ic24"]
    for lane, name in enumerate(names):
        image[lane::8] = rom[name]
    return bytes(image)


def build_sound(rom):
    """mainpcb:soundcpu: Z80 program (x8) then the 1 MB PCM bank (x2)."""
    image = bytearray(0x400000)
    image[0x000000:0x100000] = rom["s32_snd00.ic35"] * 8
    image[0x100000:0x200000] = rom["s32_snd01.ic31"] * 2
    return bytes(image)


def canonical_address(address):
    """24-bit bus: F00000-FFFFFF mirrors 000000-0FFFFF; everything under 2 MB is the program region."""
    address &= 0xFFFFFF
    if address >= 0xF00000:
        address -= 0xF00000
    if address < 0x200000:
        return address
    return None


class ProgramMemory:
    def __init__(self, image):
        self.image = image

    def r8(self, address):
        offset = canonical_address(address)
        return self.image[offset] if offset is not None else 0xFF

    def r16(self, address):
        return self.r8(address) | (self.r8(address + 1) << 8)

    def r32(self, address):
        return self.r16(address) | (self.r16(address + 2) << 16)
