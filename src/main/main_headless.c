/**
 *    Name:        main_headless.c
 *    Description: runs the translated Slip Stream program with the System 32 board model, no window:
 *                 writes per-frame state and video hashes, and optional frames as BMP
 *
 *    It reads the board regions the user's ROM set builds (tools/extract_regions.py): program.bin,
 *    tiles.bin, sprites.bin and sound.bin. Nothing of the game is in the executable.
 */
#include "s32/machine.h"
#include "s32/program.h"
#include "s32/video.h"
#include "s32sound.h"

#include <inttypes.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define USAGE "Usage: slipstream_headless [--regions DIR] [--frames N] [--hashes FILE]" \
	" [--video-hashes FILE] [--video-dump N ... --video-dir DIR]\n"

static jmp_buf finished;
static uint64_t frames_wanted = 600;
static FILE *hashes;
static FILE *video_hashes;
static uint64_t video_dump = UINT64_MAX;
static const char *video_dir;
static uint64_t state_dump = UINT64_MAX;
static const char *dump_dir;
static FILE *sound_hashes;
static uint8_t *program_image;
static uint8_t *tiles_image;
static uint8_t *sprites_image;
static uint8_t *sound_image;

static uint8_t *load_region(const char *dir, const char *name, size_t expected)
{
	char path[1024];
	FILE *file;
	uint8_t *data;
	size_t got;

	snprintf(path, sizeof(path), "%s/%s", dir, name);
	file = fopen(path, "rb");
	if (!file)
	{
		fprintf(stderr, "%s: cannot open\n", path);
		return NULL;
	}
	data = (uint8_t *)malloc(expected);
	if (!data)
	{
		fclose(file);
		return NULL;
	}
	got = fread(data, 1, expected, file);
	fclose(file);
	if (got != expected)
	{
		fprintf(stderr, "%s: %zu bytes, expected %zu\n", path, got, expected);
		free(data);
		return NULL;
	}
	return data;
}

static void write_bmp(const char *path)
{
	int width = 0;
	const uint32_t *pixels = s32_video_frame(&width);
	const uint32_t row = ((uint32_t)width * 3 + 3) & ~3u;
	const uint32_t size = 54 + row * S32_VIDEO_HEIGHT;
	uint8_t *file = (uint8_t *)calloc(size, 1);
	FILE *output;

	if (!file)
		return;
	file[0] = 'B';
	file[1] = 'M';
	for (int byte = 0; byte < 4; byte++)
	{
		file[2 + byte] = (uint8_t)(size >> (8 * byte));
		file[18 + byte] = (uint8_t)((uint32_t)width >> (8 * byte));
		file[22 + byte] = (uint8_t)((uint32_t)S32_VIDEO_HEIGHT >> (8 * byte));
	}
	file[10] = 54;
	file[14] = 40;
	file[26] = 1;
	file[28] = 24;
	for (int y = 0; y < S32_VIDEO_HEIGHT; y++)
		for (int x = 0; x < width; x++)
		{
			const uint32_t pixel = pixels[y * S32_VIDEO_MAX_WIDTH + x];
			uint8_t *out = &file[54 + (uint32_t)(S32_VIDEO_HEIGHT - 1 - y) * row + (uint32_t)x * 3];

			out[0] = (uint8_t)pixel;
			out[1] = (uint8_t)(pixel >> 8);
			out[2] = (uint8_t)(pixel >> 16);
		}
	output = fopen(path, "wb");
	if (output)
	{
		fwrite(file, 1, size, output);
		fclose(output);
	}
	else
		fprintf(stderr, "%s: cannot write\n", path);
	free(file);
}

static void on_irq_changed(bool asserted)
{
	program_irq_line(asserted);
}

static void on_log(const char *message)
{
	fprintf(stderr, "[s32] %s\n", message);
}

/* Default cabinet state: no buttons, steering centered, both pedals released. The MSM6253 driver in
   game/io.c reads these. */
static void on_controls_update(void)
{
	s32_board.input.port_a = 0xff;
	s32_board.input.port_b = 0xff;
	s32_board.input.port_c = 0xff;
	s32_board.input.port_e = 0xff;
	s32_board.input.port_f = 0xff;
	s32_board.input.analog[0] = 0x80;
	s32_board.input.analog[1] = 0x00;
	s32_board.input.analog[2] = 0x00;
	s32_board.input.analog[3] = 0x80;
}

static void dump_state(void)
{
	char path[1024];
	struct { const char *name; const void *data; size_t size; } files[] = {
		{ "work_ram.bin", s32_board.work_ram, sizeof(s32_board.work_ram) },
		{ "video_ram.bin", s32_board.video_ram, sizeof(s32_board.video_ram) },
		{ "sprite_ram.bin", s32_board.sprite_ram, sizeof(s32_board.sprite_ram) },
		{ "palette.bin", s32_board.palette, sizeof(s32_board.palette) },
		{ "mixer.bin", s32_board.mixer, sizeof(s32_board.mixer) },
		{ "shared_ram.bin", s32_board.shared_ram, sizeof(s32_board.shared_ram) },
	};
	for (size_t index = 0; index < sizeof(files) / sizeof(files[0]); index++)
	{
		FILE *output;

		snprintf(path, sizeof(path), "%s/%s", dump_dir, files[index].name);
		output = fopen(path, "wb");
		if (output)
		{
			fwrite(files[index].data, 1, files[index].size, output);
			fclose(output);
		}
	}
}

static void on_frame_done(void)
{
	const uint64_t frame = program_frames() - 1;

	if (sound_image)
		s32s_end_frame(s32_board.cycles);

	if (hashes)
		fprintf(hashes, "%" PRIu64 " %016" PRIx64 "\n", frame, s32_state_hash());
	if (sound_hashes)
		fprintf(sound_hashes, "%" PRIu64 " %016" PRIx64 " %016" PRIx64 "\n", frame,
			s32s_frame_samples_hash(), s32s_state_hash());
	if (video_hashes)
		fprintf(video_hashes, "%" PRIu64 " %016" PRIx64 "\n", frame, s32_video_frame_hash());
	if (video_dir && frame == video_dump)
	{
		char path[1024];

		snprintf(path, sizeof(path), "%s/frame_%" PRIu64 ".bmp", video_dir, frame);
		write_bmp(path);
	}
	if (dump_dir && frame == state_dump)
		dump_state();
	if (program_frames() >= frames_wanted)
		longjmp(finished, 1);
}

int main(int argc, char **argv)
{
	const char *regions = "build/regions";
	const char *hashes_path = NULL;
	const char *video_hashes_path = NULL;
	const char *sound_hashes_path = NULL;

	for (int index = 1; index < argc; index++)
	{
		if (strcmp(argv[index], "--frames") == 0 && index + 1 < argc)
			frames_wanted = strtoull(argv[++index], NULL, 10);
		else if (strcmp(argv[index], "--regions") == 0 && index + 1 < argc)
			regions = argv[++index];
		else if (strcmp(argv[index], "--hashes") == 0 && index + 1 < argc)
			hashes_path = argv[++index];
		else if (strcmp(argv[index], "--video-hashes") == 0 && index + 1 < argc)
			video_hashes_path = argv[++index];
		else if (strcmp(argv[index], "--video-dump") == 0 && index + 1 < argc)
			video_dump = strtoull(argv[++index], NULL, 10);
		else if (strcmp(argv[index], "--video-dir") == 0 && index + 1 < argc)
			video_dir = argv[++index];
		else if (strcmp(argv[index], "--dump-frame") == 0 && index + 1 < argc)
			state_dump = strtoull(argv[++index], NULL, 10);
		else if (strcmp(argv[index], "--dump-dir") == 0 && index + 1 < argc)
			dump_dir = argv[++index];
		else if (strcmp(argv[index], "--sound-hashes") == 0 && index + 1 < argc)
			sound_hashes_path = argv[++index];
		else
		{
			fprintf(stderr, USAGE);
			return 1;
		}
	}

	program_image = load_region(regions, "program.bin", S32_PROGRAM_SIZE);
	tiles_image = load_region(regions, "tiles.bin", 0x200000);
	sprites_image = load_region(regions, "sprites.bin", 0x400000);
	sound_image = load_region(regions, "sound.bin", 0x400000);
	if (!program_image || !tiles_image || !sprites_image)
		return 1;
	if (!sound_image)
		fprintf(stderr, "sound.bin missing: running without the sound board\n");

	if (hashes_path)
		hashes = fopen(hashes_path, "w");
	if (sound_hashes_path)
		sound_hashes = fopen(sound_hashes_path, "w");

	s32_video_init(tiles_image, 0x200000, sprites_image, 0x400000);
	if (sound_image)
	{
		s32_board.sound_rom = sound_image;
		s32s_attach();
	}
	s32_board.irq_changed = on_irq_changed;
	s32_board.controls_update = on_controls_update;
	s32_board.frame_shown = s32_video_draw_frame;
	s32_board.sprites_due = s32_video_sprites;
	s32_board.log = on_log;
	s32_board.frame_timing = true;
	s32_init(program_image);
	program_reset();
	program_frame_done = on_frame_done;

	if (!setjmp(finished))
		program_run();

	if (hashes)
		fclose(hashes);
	if (video_hashes)
		fclose(video_hashes);
	if (sound_hashes)
		fclose(sound_hashes);
	printf("frames:            %" PRIu64 "\n", program_frames());
	printf("interrupts taken:  %u\n", program_interrupts());
	printf("sprite lists:      %u\n", s32_board.sprite_lists);
	printf("unmapped reads:    %u\n", s32_board.unmapped_reads);
	printf("unmapped writes:   %u\n", s32_board.unmapped_writes);
	free(program_image);
	free(tiles_image);
	free(sprites_image);
	return 0;
}
