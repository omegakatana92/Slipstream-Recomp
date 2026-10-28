# Slip Stream - native recompilation of the Sega System 32 arcade game
#
# The game's program is translated from the user's own ROM into build/generated (tools/recompile.py);
# the board model (src/game, src/graphics, src/audio) and the V60 runtime (src/cpu) are ordinary C.
cmake_minimum_required(VERSION 3.20)
project(slipstream C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(SLIPSTREAM_BIN_DIR ${CMAKE_SOURCE_DIR}/build/bin CACHE PATH "Where the executables go")
foreach(config IN ITEMS "" _DEBUG _RELEASE _RELWITHDEBINFO _MINSIZEREL)
	set(CMAKE_RUNTIME_OUTPUT_DIRECTORY${config} ${SLIPSTREAM_BIN_DIR})
endforeach()

if(MSVC)
	add_compile_options(/W3 /utf-8)
	add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
endif()

# System 32 board model: memory map, interrupts and timers, I/O chip, EEPROM, palette and mixer,
# video, and the sound board's Z80 side and chips (MAME-compatible behavior; BSD-3-Clause files
# from segasonic-decomp, see THIRD_PARTY_NOTICES.md).
add_library(s32runtime STATIC
	src/game/machine.c
	src/game/io.c
	src/game/script.c
	src/graphics/video.c
	src/audio/sound.c
	src/audio/sound_chips.c
	src/audio/rf5c68.c
	src/audio/ym3438.c
)
target_include_directories(s32runtime PUBLIC include)
if(UNIX AND NOT APPLE)
	target_link_libraries(s32runtime PUBLIC m)
endif()

# (v60.c and the translated program are one library: the runtime calls the generated entry table)
# Sound board: the original Z80 program on MAME's Z80 core, with MAME's RF5C68 and ymfm's YM3438
# (BSD-3-Clause; reference sources from tools/core). The main CPU stays translated; this gives the
# sound board correct behavior until its Z80 program is translated too.
find_package(Python3 COMPONENTS Interpreter)
set(SLIPSTREAM_Z80_STEPS ${CMAKE_BINARY_DIR}/generated/cpu/z80/z80.hxx)
add_custom_command(OUTPUT ${SLIPSTREAM_Z80_STEPS}
	COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/generated/cpu/z80
	COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/tools/core/system32/reference/mame/z80/z80make.py z80
		${CMAKE_SOURCE_DIR}/tools/core/system32/reference/mame/z80/z80.lst ${SLIPSTREAM_Z80_STEPS}
	DEPENDS ${CMAKE_SOURCE_DIR}/tools/core/system32/reference/mame/z80/z80make.py
		${CMAKE_SOURCE_DIR}/tools/core/system32/reference/mame/z80/z80.lst
	VERBATIM)
add_library(s32sound STATIC
	third_party/s32sound/s32sound.cpp
	tools/core/system32/reference/ymfm/ymfm_opn.cpp
	tools/core/system32/reference/ymfm/ymfm_adpcm.cpp
	tools/core/system32/reference/ymfm/ymfm_ssg.cpp
	${SLIPSTREAM_Z80_STEPS}
)
target_include_directories(s32sound PUBLIC
	third_party/s32sound
	tools/core/system32/reference
	tools/core/system32/reference/ymfm
	${CMAKE_BINARY_DIR}/generated
	include)
if(MSVC)
	target_compile_options(s32sound PRIVATE /wd4244 /wd4267 /wd4100 /wd4146 /wd4127 /bigobj)
endif()

# The translated program (the user's ROM as C). It is generated, never committed, never shipped.
file(GLOB SLIPSTREAM_GENERATED CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/build/generated/*.c)
if(SLIPSTREAM_GENERATED)
	add_library(slipstream_program STATIC ${SLIPSTREAM_GENERATED} src/cpu/v60.c)
	target_include_directories(slipstream_program PUBLIC build/generated include)
	target_link_libraries(slipstream_program PUBLIC s32runtime)
	if(MSVC)
		target_compile_options(slipstream_program PRIVATE /bigobj)
	else()
		target_compile_options(slipstream_program PRIVATE -fno-strict-aliasing)
	endif()

	add_executable(slipstream_headless src/main/main_headless.c)
	target_link_libraries(slipstream_headless PRIVATE slipstream_program s32sound)

	option(SLIPSTREAM_SDL2 "Build the windowed port (needs SDL2)" ON)
	if(SLIPSTREAM_SDL2)
		if(WIN32)
			file(GLOB SLIPSTREAM_SDL2_UNPACKED ${CMAKE_SOURCE_DIR}/build/downloads/sdl2/SDL2-*/cmake)
		endif()
		find_package(SDL2 CONFIG QUIET HINTS ${SLIPSTREAM_SDL2_UNPACKED})
		if(SDL2_FOUND)
			add_executable(slipstream src/main/main_sdl2.c)
			if(TARGET SDL2::SDL2)
				target_link_libraries(slipstream PRIVATE slipstream_program s32sound SDL2::SDL2)
			else()
				target_include_directories(slipstream PRIVATE ${SDL2_INCLUDE_DIRS})
				target_link_libraries(slipstream PRIVATE slipstream_program s32sound ${SDL2_LIBRARIES})
			endif()
			if(TARGET SDL2::SDL2main)
				target_link_libraries(slipstream PRIVATE SDL2::SDL2main)
			endif()
			if(WIN32 AND TARGET SDL2::SDL2)
				add_custom_command(TARGET slipstream POST_BUILD
					COMMAND ${CMAKE_COMMAND} -E copy_if_different $<TARGET_FILE:SDL2::SDL2> $<TARGET_FILE_DIR:slipstream>)
			endif()
		else()
			message(STATUS "No SDL2 development files: slipstream_headless is built, the windowed port is not")
		endif()
	endif()
else()
	message(STATUS "No translated program yet: run tools/recompile.py with a reference trace")
endif()

# Development reference: MAME's V60 core against the same board model, from the shared core's
# system32/reference. Not part of the game and never linked into it.
option(SLIPSTREAM_REFERENCE "Build the MAME-based reference runner" OFF)
if(SLIPSTREAM_REFERENCE)
	add_executable(slipstream_ref tools/reference/slipstream_ref.cpp
		tools/core/system32/reference/mame/v60.cpp
		tools/core/system32/reference/mame/v60d.cpp)
	target_include_directories(slipstream_ref PRIVATE
		tools/core/system32/reference/stub
		tools/core/system32/reference/mame
		include)
	target_link_libraries(slipstream_ref PRIVATE s32runtime)
	if(MSVC)
		target_compile_options(slipstream_ref PRIVATE /wd4244 /wd4267 /wd4100 /wd4146 /wd4646)
	else()
		# MAME's op2.hxx uses roundf/floorf/ceilf/truncf without including <cmath>
		target_compile_options(slipstream_ref PRIVATE -include cmath)
	endif()
endif()
