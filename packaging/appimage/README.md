# AppImage packaging

`build_appimage.sh` builds the Linux game, lays out an AppDir with the executable, an icon and a
desktop file, and packages it with appimagetool. The regions are included **inside** the AppDir only
because they were generated from the builder's own ROM; this is a private artifact, not a release.

A ROM-free public AppImage would need a first-run flow that reads the player's own set and extracts
the regions (the extraction code already exists in `tools/extract_regions.py`); that flow is not
implemented in the SDL2 port yet.

The script has not been run on a Linux host. SteamOS validation (glibc, SDL2 present, controller in
Gaming Mode) remains to be done.
