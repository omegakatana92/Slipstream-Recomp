<#
.SYNOPSIS
    Builds the native Windows x64 Slip Stream recompilation.

.DESCRIPTION
    Verifies the toolchain and the player's own ROM set, extracts the board regions, builds the MAME
    reference, records the execution trace the translator needs, translates the V600 program to C,
    and builds the game (headless and SDL2 windowed).

    No ROM or translated program is stored in this repository. The generated C in build/generated
    comes from the ROM given with -Rom and must not be redistributed.

.PARAMETER Rom
    MAME 'slipstrm' set: a .zip or a folder of its files. Default: rom/ (rom/slipstrm.zip works).

.PARAMETER BuildDir
    CMake build directory. Default: build/cmake.

.PARAMETER Frames
    Frames the reference traces for the translator. Default: 1800 (30 s of game time).
#>
[CmdletBinding()]
param(
    [string]$Rom = "rom",
    [string]$BuildDir = "build/cmake",
    [int]$Frames = 1800
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Fail($message) {
    Write-Host "ERROR: $message" -ForegroundColor Red
    exit 1
}

function Require($command, $name) {
    $found = Get-Command $command -ErrorAction SilentlyContinue
    if (-not $found) { Fail "$name is required but was not found (install it and retry)" }
}

Write-Host "== Checking the toolchain ==" -ForegroundColor Cyan
Require cmake "CMake 3.20+"
Require python "Python 3.10+"
Require git "Git"
$cmakeVersion = (cmake --version | Select-Object -First 1)
$pythonVersion = (python --version 2>&1)
Write-Host "  $cmakeVersion"
Write-Host "  $pythonVersion"

if (-not (Test-Path "tools/core/system32/reference/mame/v60.cpp")) {
    Write-Host "== Fetching the shared core (git submodule) ==" -ForegroundColor Cyan
    git submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { Fail "the tools/core submodule could not be initialized" }
}

Write-Host "== Verifying the ROM set ==" -ForegroundColor Cyan
if (-not (Test-Path $Rom)) { Fail "ROM set not found: $Rom (copy MAME's slipstrm.zip to rom/ or pass -Rom)" }
python tools/verify_rom.py $Rom
if ($LASTEXITCODE -ne 0) { Fail "the ROM set does not match MAME's 'slipstrm'" }

Write-Host "== Extracting the board regions ==" -ForegroundColor Cyan
python tools/extract_regions.py $Rom build/regions
if ($LASTEXITCODE -ne 0) { Fail "the ROM regions could not be built" }

# SDL2: the VC development package, only for the windowed port. The headless build works without it.
$sdlDir = Get-ChildItem "build/downloads/sdl2" -Directory -Filter "SDL2-*" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $sdlDir) {
    Write-Host "== Fetching SDL2 (VC development package) ==" -ForegroundColor Cyan
    $zip = "build/downloads/sdl2.zip"
    New-Item -ItemType Directory -Force -Path "build/downloads/sdl2" | Out-Null
    try {
        Invoke-WebRequest -Uri "https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/SDL2-devel-2.32.10-VC.zip" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath "build/downloads/sdl2" -Force
    } catch {
        Write-Warning "SDL2 could not be downloaded; the headless build will still be made"
    }
}

Write-Host "== Configuring (reference first) ==" -ForegroundColor Cyan
cmake -S . -B $BuildDir -DSLIPSTREAM_REFERENCE=ON -DSLIPSTREAM_SDL2=ON
if ($LASTEXITCODE -ne 0) { Fail "CMake configuration failed" }

Write-Host "== Building the MAME reference ==" -ForegroundColor Cyan
cmake --build $BuildDir --config Release --target slipstream_ref
if ($LASTEXITCODE -ne 0) { Fail "the reference could not be built" }

Write-Host "== Recording the execution trace ($Frames frames) ==" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "build/trace" | Out-Null
& "build/bin/slipstream_ref.exe" --regions build/regions --frames $Frames `
    --trace build/trace/executed.txt --calls build/trace/called.txt
if ($LASTEXITCODE -ne 0) { Fail "the reference run failed" }

Write-Host "== Translating the program to C ==" -ForegroundColor Cyan
python tools/recompile.py $Rom --trace build/trace/executed.txt --calls build/trace/called.txt
if ($LASTEXITCODE -ne 0) { Fail "translation reported untranslated functions (see above)" }

Write-Host "== Building the game ==" -ForegroundColor Cyan
cmake -S . -B $BuildDir -DSLIPSTREAM_REFERENCE=ON -DSLIPSTREAM_SDL2=ON
cmake --build $BuildDir --config Release
if ($LASTEXITCODE -ne 0) { Fail "the build failed" }

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  build/bin/slipstream.exe           (windowed, needs SDL2.dll beside it)"
Write-Host "  build/bin/slipstream_headless.exe  (state/video hashes)"
Write-Host "  build/bin/slipstream_ref.exe       (MAME reference)"
Write-Host ""
Write-Host "Run: build/bin/slipstream.exe --regions build/regions"
