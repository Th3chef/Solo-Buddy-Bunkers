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
                      hero.py         the scene, a flat illustration (Python 3 + NumPy, SciPy, Pillow)
                      cards.py        the thumbnail, gallery, header, GitHub social picture and AyakaMods cover: the scene from
                                      hero.py with the title and text as HTML rendered with Playwright Chromium
                                      (python3 cards.py <out dir> 1.0)
                      thumbnail.png   the page art (square); fonts/ (SIL Open Font License)
                      icon.png        the Arsenal icon build.py puts in the zip (the 1.0.0 art)

Run them from this folder. The release build is deterministic apart from the zip's file dates: the files inside match
the release byte for byte.
