/**
 *    Name:        main_sdl2.c
 *    Description: Slip Stream in a window: the translated program on the System 32 board model, SDL2
 *                 video and input, ROM regions loaded from beside the executable (or --regions)
 *
 *    No game data is in this executable. It reads the board regions the user's own ROM set builds
 *    (tools/extract_regions.py): program.bin, tiles.bin and sprites.bin.
 *
 *    Keys: arrows/WASD steer and accelerate/brake, Space changes gear, A/D also steer,
 *          5 coin, 1 start, 9 service, F2 test, F11 fullscreen, Esc quit.
 *    Gamepad (Xbox layout): left stick steers, right trigger accelerates, left trigger brakes,
 *          A changes gear, Start starts, Back inserts a coin.
 */
#include "s32/machine.h"
#include "s32/program.h"
#include "s32/video.h"
#include "s32sound.h"

#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static SDL_Window *window;
static SDL_Renderer *renderer;
static SDL_Texture *texture;
static int texture_width;
static int texture_height;
static int fullscreen;
static int gear;
static const Uint8 *keys;
static SDL_GameController *controller;
static uint32_t next_frame_ms;
static int running = 1;
static uint8_t *program_image, *tiles_image, *sprites_image, *sound_image;
static SDL_AudioDeviceID audio_device;
static uint32_t audio_rate;

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
		fprintf(stderr, "%s: cannot open (run tools/extract_regions.py)\n", path);
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

static void present(void)
{
	int width;
	const uint32_t *pixels = s32_video_frame(&width);

	if (width != texture_width || texture_height != S32_VIDEO_HEIGHT)
	{
		SDL_DestroyTexture(texture);
		texture_width = width;
		texture_height = S32_VIDEO_HEIGHT;
		texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING,
			width, S32_VIDEO_HEIGHT);
		SDL_RenderSetLogicalSize(renderer, width, S32_VIDEO_HEIGHT);
	}
	SDL_UpdateTexture(texture, NULL, pixels, (int)(S32_VIDEO_MAX_WIDTH * sizeof(uint32_t)));
	SDL_RenderClear(renderer);
	SDL_RenderCopy(renderer, texture, NULL, NULL);
	SDL_RenderPresent(renderer);
}

static int read_axis(SDL_GameControllerAxis axis)
{
	return controller ? SDL_GameControllerGetAxis(controller, axis) : 0;
}

static int read_button(SDL_GameControllerButton button)
{
	return controller ? SDL_GameControllerGetButton(controller, button) : 0;
}

static void pump_input(void)
{
	SDL_Event event;
	int up = 0, down = 0, left = 0, right = 0;
	int accelerate, brake, steer;

	while (SDL_PollEvent(&event))
	{
		if (event.type == SDL_QUIT)
			running = 0;
		if (event.type == SDL_KEYDOWN)
		{
			if (event.key.keysym.sym == SDLK_ESCAPE)
				running = 0;
			if (event.key.keysym.sym == SDLK_F11)
			{
				fullscreen = !fullscreen;
				SDL_SetWindowFullscreen(window, fullscreen ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);
			}
			if (event.key.keysym.sym == SDLK_SPACE)
				gear ^= 1;
		}
		if (event.type == SDL_CONTROLLERDEVICEADDED && !controller)
			controller = SDL_GameControllerOpen(event.cdevice.which);
		if (event.type == SDL_CONTROLLERDEVICEREMOVED && controller)
		{
			SDL_GameControllerClose(controller);
			controller = NULL;
		}
	}
	if (read_button(SDL_CONTROLLER_BUTTON_A) && !gear)
		gear = 1;
	keys = SDL_GetKeyboardState(NULL);
	up = keys[SDL_SCANCODE_UP] || keys[SDL_SCANCODE_W];
	down = keys[SDL_SCANCODE_DOWN] || keys[SDL_SCANCODE_S];
	left = keys[SDL_SCANCODE_LEFT] || keys[SDL_SCANCODE_A];
	right = keys[SDL_SCANCODE_RIGHT] || keys[SDL_SCANCODE_D];

	steer = 128 + (right - left) * 96;
	steer += read_axis(SDL_CONTROLLER_AXIS_LEFTX) / 400;
	if (steer < 0) steer = 0;
	if (steer > 255) steer = 255;
	accelerate = up ? 200 : 0;
	brake = down ? 200 : 0;
	accelerate = accelerate > read_axis(SDL_CONTROLLER_AXIS_TRIGGERRIGHT) * 255 / 32767
		? accelerate : read_axis(SDL_CONTROLLER_AXIS_TRIGGERRIGHT) * 255 / 32767;
	brake = brake > read_axis(SDL_CONTROLLER_AXIS_TRIGGERLEFT) * 255 / 32767
		? brake : read_axis(SDL_CONTROLLER_AXIS_TRIGGERLEFT) * 255 / 32767;

	s32_board.input.analog[0] = (uint8_t)steer;
	s32_board.input.analog[1] = (uint8_t)accelerate;
	s32_board.input.analog[2] = (uint8_t)brake;
	s32_board.input.analog[3] = 0x80;
	s32_board.input.port_a = (uint8_t)(gear ? 0xfe : 0xff);
	s32_board.input.port_b = 0xff;
	s32_board.input.port_c = 0xff;
	s32_board.input.port_e = 0xff;
	s32_board.input.port_f = 0xff;
	if (keys[SDL_SCANCODE_5] || read_button(SDL_CONTROLLER_BUTTON_BACK))
		s32_board.input.port_e &= (uint8_t)~0x04;      /* coin 1 */
	if (keys[SDL_SCANCODE_1] || read_button(SDL_CONTROLLER_BUTTON_START))
		s32_board.input.port_e &= (uint8_t)~0x10;      /* start 1 */
	if (keys[SDL_SCANCODE_9])
		s32_board.input.port_e &= (uint8_t)~0x01;      /* service */
	if (keys[SDL_SCANCODE_F2])
		s32_board.input.port_e &= (uint8_t)~0x02;      /* test */
}

static void on_controls_update(void)
{
	pump_input();
}

static void on_frame_done(void)
{
	uint32_t now;

	if (sound_image)
	{
		size_t frames = 0;
		const int16_t *mix;

		s32s_end_frame(s32_board.cycles);
		mix = s32s_frame_mix(&frames);
		if (audio_device && frames)
			SDL_QueueAudio(audio_device, mix, (Uint32)(frames * 2 * sizeof(int16_t)));
	}
	present();
	now = SDL_GetTicks();
	if (next_frame_ms > now)
		SDL_Delay(next_frame_ms - now);
	next_frame_ms += 1000 / S32_FRAME_RATE;
	if (next_frame_ms + 100 < SDL_GetTicks())
		next_frame_ms = SDL_GetTicks() + 1000 / S32_FRAME_RATE;
	if (!running)
		exit(0);
}

static void on_irq_changed(bool asserted)
{
	program_irq_line(asserted);
}

static void on_log(const char *message)
{
	fprintf(stderr, "[s32] %s\n", message);
}

int main(int argc, char **argv)
{
	const char *regions = "build/regions";
	char beside[1024];

	if (argc > 2 && strcmp(argv[1], "--regions") == 0)
		regions = argv[2];
	else
	{
		const char *slash = strrchr(argv[0], '/'), *backslash = strrchr(argv[0], '\\');
		const char *last = slash > backslash ? slash : backslash;
		snprintf(beside, sizeof(beside), "%.*sregions", last ? (int)(last - argv[0] + 1) : 0, argv[0]);
		{
			char probe[1100];
			FILE *file;

			snprintf(probe, sizeof(probe), "%s/program.bin", beside);
			file = fopen(probe, "rb");
			if (file)
			{
				fclose(file);
				regions = beside;
			}
		}
	}

	program_image = load_region(regions, "program.bin", S32_PROGRAM_SIZE);
	tiles_image = load_region(regions, "tiles.bin", 0x200000);
	sprites_image = load_region(regions, "sprites.bin", 0x400000);
	if (!program_image || !tiles_image || !sprites_image)
		return 1;
	sound_image = load_region(regions, "sound.bin", 0x400000);

	if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMECONTROLLER) != 0)
	{
		fprintf(stderr, "SDL: %s\n", SDL_GetError());
		return 1;
	}
	window = SDL_CreateWindow("Slip Stream", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
		832, 448, SDL_WINDOW_RESIZABLE);
	renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
	if (!renderer)
		renderer = SDL_CreateRenderer(window, -1, 0);
	if (!window || !renderer)
	{
		fprintf(stderr, "SDL: %s\n", SDL_GetError());
		return 1;
	}

	for (int index = 0; index < SDL_NumJoysticks(); index++)
		if (SDL_IsGameController(index))
		{
			controller = SDL_GameControllerOpen(index);
			break;
		}

	s32_video_init(tiles_image, 0x200000, sprites_image, 0x400000);
	if (sound_image)
	{
		SDL_AudioSpec want, have;

		s32_board.sound_rom = sound_image;
		s32s_attach();
		audio_rate = s32s_mix_rate();
		memset(&want, 0, sizeof(want));
		want.freq = (int)audio_rate;
		want.format = AUDIO_S16SYS;
		want.channels = 2;
		want.samples = 1024;
		audio_device = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
		if (audio_device)
			SDL_PauseAudioDevice(audio_device, 0);
		else
			fprintf(stderr, "SDL audio: %s\n", SDL_GetError());
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
	next_frame_ms = SDL_GetTicks() + 1000 / S32_FRAME_RATE;

	program_run();
	return 0;
}
