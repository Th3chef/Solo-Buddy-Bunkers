# Solo Buddy Bunkers - source

A Bingus Shared Loader Lua mod: one addon, `lua/solo_buddy_bunkers.lua`.

    lua/solo_buddy_bunkers.lua
                    the addon (plain Lua; Bingus Shared Loader finds it by its first line)
    build.py        builds the mod zip (Python 3 + Pillow):
                      python3 build.py out              -> out/Solo-Buddy-Bunkers-<ver>.zip (the release)
                      python3 build.py out --tester     -> the Tester build (extra details in the log)
    patch_writer.py writes the patch archive
    fonts/          Anton (SIL Open Font License), for the icon of numbered test builds
    artwork/        the release art:
                      scene.py        the 3D scene (Blender as a Python module: pip install bpy), rendered with
                                      Cycles by render_all.sh into renders/ (square, wide, social, header; about
                                      an hour on 2 CPU cores)
                      cards.py        the thumbnail, gallery, header and GitHub social picture from the renders
                                      (python3 cards.py <out dir> 1.0; needs Playwright Chromium)
                      thumbnail.png   the Arsenal icon build.py uses; fonts/ (SIL Open Font License)

Run them from this folder. The release build is deterministic apart from the zip's file dates: the files inside match
the release byte for byte.
