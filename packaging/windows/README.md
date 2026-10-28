# Windows packaging

The executable contains the translated program, which is derived from the player's ROM. For that
reason no prebuilt Windows zip is published with this repository: each user builds from their own
`slipstrm.zip` with `build_windows.ps1`.

To make a local, private folder that runs on the same machine:

1. `.\build_windows.ps1 -Rom C:\path\to\slipstrm.zip`
2. Copy `build\bin\slipstream.exe`, `build\bin\SDL2.dll` and the `build\regions` folder into one
   directory (keep the folder name `regions`).
3. Run `slipstream.exe --regions regions`.

Do not redistribute that folder: it carries the game's translated program and extracted region data.
