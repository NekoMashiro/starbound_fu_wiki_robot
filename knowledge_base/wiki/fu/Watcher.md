# [FU] Watcher

**来源**: Frackin' Universe Wiki | **分类**: Mechanics | **链接**: https://frackinuniverse.miraheze.org/wiki/Watcher

---

**Watcher** allows machinery like Growing Tray or Extraction Lab to work even if the player is very far away. Without it Starbound would "unload" some parts of the map if you haven't been nearby in the last 15 seconds (and that would stop the machines).

To use it, craft a Watcher and place it within 20 blocks of the machines that you want to keep "awake". Then interact (E) with Watcher to turn it on (it's not enabled by default).

## More details
- Things on another planet (and/or your ship) will NOT run if you are not on that planet/ship. This is the limitation of Starbound. There is nothing Watcher can do about it.
- Watcher turns off when you beam away. Next time you visit the planet, you need to Interact with it again to re-enable it.
- : If you have two Teleporters on the same planet, teleporting between them won't turn off the Watchers.
- You can wire Signal Emitter to Watcher. This will automatically turn the watcher ON if you approach the Signal Emitter. It's best to have this Signal Emitter within 20 blocks of the Watcher (so that Signal Emitter itself doesn't get "unloaded").
- If you place 100 Watchers all over the planet, you will cause immeasurable lag. Place them **only** when some station absolutely must run.
- There is **absolutely no need** to wire Watcher to stations (in fact, it might even disable the Watcher).
- Item Transference Device will automatically "awaken" the chests and/or stations when it moves items to/from them. Unless you throttle the ITD too harshly (to run more rarely than once every 14 seconds), you shouldn't need a Watcher near stations that are connected to that ITD. However, the ITD itself must be in the loaded area for this trick to work (you might need a Watcher near the ITD **if you rely on it to wake other stations**).
- Apiary, Colony Core, soil-grown crops and trees don't need a Watcher nearby (they take into account the time you were away). However, Growing Tray or colony buildings like Blood Drive are machinery and will need a Watcher.
- Quarry keeps itself "awake" and doesn't need a Watcher.

## How it works under the hood
Watcher tells the game "this area of the map is important to the player". This disqualifies the area from being "unloaded" in the next 15 seconds. Watcher does so every 10 seconds, so the game thinks that these areas can never be unloaded.

It's possible that Starbound will load more than 20 blocks around the Watcher (because it loads the map in large "chunks", not just this diameter 40 circle), but we can't rely on it (shape and dimensions of the loaded area can be very different). Only the radius 20 area centered around the Watcher is known to be loaded.