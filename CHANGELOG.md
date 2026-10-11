# Changelog

## 1.0.1

- Fixed: when something else in the mission went away right before a press, the press for you could go to a switch record the game had just removed. Both switches are now checked against the game's current records before the press.
- Fixed: a press that had to wait because the switches moved in memory was left alone for good (the bunker didn't open). It is now tried again while the press is still fresh.
- The mod no longer treats its own press of the other switch as a new press.
- Joined games: the whole entity table is read (its size is found in the game's code), not only its first 2048 rows.
- The units lookup both parts share is found once, with its own log line, and the log says once if the unit layout moved after a game update.
- When only the joined-game part is found, the status no longer calls every game a joined game.
- Build: the zip is reproducible byte for byte, and the build checks the addon's first line, that the Lua compiles and that nothing personal is in the patch or manifest.

## 1.0.0

First release.

- Press one switch of a two-person (buddy) bunker and the other switch of the same bunker is pressed for you.
- Works solo, when you host (for a press by anyone in your game) and when you join someone else's game (your game sends the host the press of the other switch; the host doesn't need the mod).
- On/off toggle in game with Mod Options Menu.
- Finds what it needs in the game's code by itself (patch-proof); the solo/host and joined-game parts are found separately.
