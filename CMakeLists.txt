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

add_library(slipstream_v60 STATIC src/cpu/v60.c)
target_link_libraries(slipstream_v60 PUBLIC s32runtime)

# The translated program (the user's ROM as C). It is generated, never committed, never shipped.
file(GLOB SLIPSTREAM_GENERATED CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/build/generated/*.c)
if(SLIPSTREAM_GENERATED)
	add_library(slipstream_program STATIC ${SLIPSTREAM_GENERATED})
	target_include_directories(slipstream_program PUBLIC build/generated include)
	target_link_libraries(slipstream_program PUBLIC slipstream_v60)
	if(MSVC)
		target_compile_options(slipstream_program PRIVATE /bigobj)
	else()
		target_compile_options(slipstream_program PRIVATE -fno-strict-aliasing)
	endif()

	add_executable(slipstream_headless src/main/main_headless.c)
	target_link_libraries(slipstream_headless PRIVATE slipstream_program)

	option(SLIPSTREAM_SDL2 "Build the windowed port (needs SDL2)" ON)
	if(SLIPSTREAM_SDL2)
		if(WIN32)
			file(GLOB SLIPSTREAM_SDL2_UNPACKED ${CMAKE_SOURCE_DIR}/build/downloads/sdl2/SDL2-*/cmake)
		endif()
		find_package(SDL2 CONFIG QUIET HINTS ${SLIPSTREAM_SDL2_UNPACKED})
		if(SDL2_FOUND)
			add_executable(slipstream src/main/main_sdl2.c)
			if(TARGET SDL2::SDL2)
				target_link_libraries(slipstream PRIVATE slipstream_program SDL2::SDL2)
			else()
				target_include_directories(slipstream PRIVATE ${SDL2_INCLUDE_DIRS})
				target_link_libraries(slipstream PRIVATE slipstream_program ${SDL2_LIBRARIES})
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
	endif()
endif()
