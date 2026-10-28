/**
 *    Name:        slipstream_ref.cpp
 *    Description: development reference: runs the original V60 program on MAME's V60 core against the
 *                 same System 32 board model as the port, one frame at a time
 *
 *    It reads the board regions the user's ROM set builds (tools/extract_regions.py). It is not part of
 *    the game and is never linked into it. The translated program is compared with this:
 *      slipstream_ref --regions build/regions --frames 1800 --hashes reference.txt
 *      slipstream_headless --regions build/regions --frames 1800 --hashes native.txt
 *
 *    Instructions take no time, exactly as the translated program's do: board events and interrupts run
 *    only while the game waits for its frame at 081B3A. This is the frame-timing reference of the
 *    scaffold (not MAME's wall-clock timeline); tools/core/system32/reference/s32ref.cpp is the
 *    cycle-timed reference of the toolkit.
 */
#include "emu.h"
#include "v60.h"
#include "s32/machine.h"

#include <cinttypes>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

constexpr uint32_t kFrameWaitLoop = 0x081B3A;   // test.b 382C[R15]
constexpr uint32_t kFrameWaitDone = 0x081B42;
constexpr uint32_t kFramesToWait = 0x20382C;
constexpr uint64_t kInstructionsPerFrameLimit = 200000000;

v60_device *g_cpu = nullptr;
bool g_line_wanted = false;
bool g_line_applied = false;
bool g_frame_timing = true;
uint64_t g_instructions = 0;
uint64_t g_interrupts = 0;
uint64_t g_frames_wanted = 600;
uint64_t g_frames_done = 0;
uint64_t g_instructions_at_frame = 0;
bool g_stop = false;
std::vector<uint8_t> g_executed(1 << 21);
std::vector<uint8_t> g_called(1 << 21);
bool g_call_pending = false;
std::ofstream g_hashes;
std::vector<uint8_t> g_program, g_tiles, g_sprites;

bool load_region(const std::string &dir, const char *name, std::vector<uint8_t> &out, size_t expected)
{
	std::ifstream in(dir + "/" + name, std::ios::binary);
	if (!in)
	{
		std::cerr << "cannot read " << dir << "/" << name << "\n";
		return false;
	}
	out.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
	if (out.size() != expected)
	{
		std::cerr << name << ": " << out.size() << " bytes, expected " << expected << "\n";
		return false;
	}
	return true;
}

u8 read8(offs_t a) { return s32_read8(a & 0xffffff); }
u16 read16(offs_t a) { return s32_read16(a & 0xffffff); }
u32 read32(offs_t a) { return s32_read32(a & 0xffffff); }
void write8(offs_t a, u8 d) { s32_write8(a & 0xffffff, d); }
void write16(offs_t a, u16 d) { s32_write16(a & 0xffffff, d); }
void write32(offs_t a, u32 d) { s32_write32(a & 0xffffff, d); }

void end_of_frame()
{
	if (g_hashes.is_open())
	{
		char line[64];
		std::snprintf(line, sizeof(line), "%" PRIu64 " %016" PRIx64 "\n", g_frames_done, s32_state_hash());
		g_hashes << line;
	}
	g_frames_done++;
	g_instructions_at_frame = g_instructions;
	if (g_frames_done >= g_frames_wanted)
		g_stop = true;
}

void on_irq_changed(bool asserted) { g_line_wanted = asserted; }

void on_instruction(offs_t pc)
{
	pc &= 0xffffff;
	s32_board.pc = pc;
	g_executed[pc >> 3] |= uint8_t(1u << (pc & 7));
	g_instructions++;
	if (g_call_pending)
		g_called[pc >> 3] |= uint8_t(1u << (pc & 7));
	const uint8_t opcode = s32_read8(pc);
	g_call_pending = opcode == 0x48 || opcode == 0x49 || opcode == 0xe8 || opcode == 0xe9;

	if (pc == kFrameWaitLoop && int8_t(s32_read8(kFramesToWait)) >= 0)
		s32_wait();
	else if (pc == kFrameWaitDone && !g_stop)
		end_of_frame();
	else if (g_instructions - g_instructions_at_frame > kInstructionsPerFrameLimit)
		throw std::runtime_error("the program no longer reaches its frame loop");

	if (g_line_wanted != g_line_applied)
	{
		g_line_applied = g_line_wanted;
		g_cpu->set_input_line(0, g_line_applied ? ASSERT_LINE : CLEAR_LINE);
	}
}

void write_addresses(const std::string &path, const std::vector<uint8_t> &bits)
{
	std::ofstream out(path);
	out << "# V60 addresses executed, one per line\n";
	for (uint32_t address = 0; address < (1u << 24); address++)
		if (bits[address >> 3] & (1u << (address & 7)))
		{
			char line[16];
			std::snprintf(line, sizeof(line), "%06X\n", address);
			out << line;
		}
}

} // namespace

int main(int argc, char **argv)
{
	std::string regions = "build/regions", trace_path, calls_path, hashes_path;
	for (int i = 1; i < argc; i++)
	{
		const std::string a = argv[i];
		if (a == "--frames" && i + 1 < argc) g_frames_wanted = std::stoull(argv[++i]);
		else if (a == "--regions" && i + 1 < argc) regions = argv[++i];
		else if (a == "--trace" && i + 1 < argc) trace_path = argv[++i];
		else if (a == "--calls" && i + 1 < argc) calls_path = argv[++i];
		else if (a == "--hashes" && i + 1 < argc) hashes_path = argv[++i];
		else
		{
			std::cerr << "usage: slipstream_ref [--regions DIR] [--frames N] [--hashes FILE]"
				" [--trace FILE] [--calls FILE]\n";
			return 1;
		}
	}

	if (!load_region(regions, "program.bin", g_program, 0x200000)
		|| !load_region(regions, "tiles.bin", g_tiles, 0x200000)
		|| !load_region(regions, "sprites.bin", g_sprites, 0x400000))
		return 1;

	s32_board.irq_changed = on_irq_changed;
	s32_board.controls_update = [] {
		s32_board.input.port_a = 0xff;
		s32_board.input.port_b = 0xff;
		s32_board.input.port_c = 0xff;
		s32_board.input.port_e = 0xff;
		s32_board.input.port_f = 0xff;
		s32_board.input.analog[0] = 0x80;
		s32_board.input.analog[1] = 0x00;
		s32_board.input.analog[2] = 0x00;
		s32_board.input.analog[3] = 0x80;
	};
	s32_board.frame_timing = true;
	s32_init(g_program.data());
	if (!hashes_path.empty())
		g_hashes.open(hashes_path);

	machine_config config;
	v60_device cpu(config, "maincpu", nullptr, S32_CPU_CLOCK);
	g_cpu = &cpu;
	for (int index : { AS_PROGRAM, AS_IO })
	{
		address_space &space = cpu.space(index);
		space.r8 = read8;
		space.r16 = read16;
		space.r32 = read32;
		space.w8 = write8;
		space.w16 = write16;
		space.w32 = write32;
	}
	cpu.irq_cycle_callback().set([] { g_interrupts++; return int(s32_irq_acknowledge()); });
	cpu.instruction_hook = on_instruction;
	cpu.start();
	cpu.reset();

	int status = 0;
	try
	{
		while (!g_stop)
			g_cpu->run(4096);
	}
	catch (const std::exception &error)
	{
		std::cerr << "V60 stopped at PC " << std::hex << s32_board.pc << std::dec
			<< " in frame " << g_frames_done << ": " << error.what() << "\n";
		status = 2;
	}

	std::cout << "frames: " << g_frames_done << "\ninstructions: " << g_instructions
		<< "\ninterrupts: " << g_interrupts << "\nunmapped reads: " << s32_board.unmapped_reads
		<< "\nunmapped writes: " << s32_board.unmapped_writes << "\n";
	if (!trace_path.empty())
		write_addresses(trace_path, g_executed);
	if (!calls_path.empty())
		write_addresses(calls_path, g_called);
	return status;
}
