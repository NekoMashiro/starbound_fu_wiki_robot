# [FU] Performance

**来源**: Frackin' Universe Wiki | **分类**: Everything | **链接**: https://frackinuniverse.miraheze.org/wiki/Performance

---

> What can I do to improve my game's FPS? It's incredibly laggy. But my computer is great, so what gives?

How do I improve Starbound's performance? This question is asked frequently, and **this page contains 100% of what we know**.

## Why does Starbound lag
Starbound (by itself, even without any mods) is very poorly optimized. It only uses 1 CPU core for server (in singleplayer too), and only 1 CPU core for client. It also doesn't use the GPU (all graphics are calculated by CPU). So regardless of how good your computer is, you might still run into problems.

However, things like ITDs can also contribute to the lag. See #Self-inflicted lag below.

## Methods that work
These methods are **known** to improve game speed:
- **Turn off vsync**
- : How: find the file storage/starbound.config within your Starbound directory. Edit it, replacing the line "vsync" : true, (which is slow) with "vsync" : false, (which is faster).
- : Why it helps: 99% of games don't suffer from vsync being enabled (in fact, it's better for them), because vsync is normally done by GPU. But Starbound doesn't use GPU, so having vsync means "your CPU needs to do more work".
- :  *Details on what "doesn't use GPU" means:*When we say that game "doesn't use GPU", we mean that it uses CPU (central processor) to calculate the color of all pixels that need to be displayed, and then feeds that result to GPU (which shows it on the screen). So GPU is still used, but it doesn't do anything smart. It just shows the result.

Optimized games (that "use GPU") will instead give instructions like "draw triangle here" to GPU (instead of throwing a huge array of pixels at the GPU). Also, their CPU is not busy with calculating how to color, light, etc. these pixels, as this is done by GPU, and much more efficiently.
- **More zoom**
- : How: in game options, dial it down 2x to 3x, etc.
- : Why it helps: Less things for game to draw.
- **Use 32-bit Starbound instead of 64-bit Starbound** (Windows-only)
- : How: When opening the game through Steam, choose "Play Starbound (32-bit)"
- : Why it helps: 64-bit Starbound has a known memory leak. It slowly gets worse every time some Lua script adds/removes items in chests, etc. For some reason 32-bit Starbound doesn't have this memory leak.
- : Possible issues: if some SAIL mission doesn't load in 32-bit Starbound (very rarely happens on very large mission maps like Verdant Ruins), you can complete this mission in 64-bit Starbound, and then continue using 32-bit version.
- **If you have Linux, run Starbound on Linux**
- : Why it helps: Starbound was originally developed on Linux, and apparently it was optimized for Linux more than it was optimized for Windows. It is known to run better on Linux with the same hardware.

## Methods that might work
**Disclaimer**: these methods are only theoretically helpful. It's not proven that they help. Their impact may be negligible or non-existent.

- Mods that decrease the complexity of graphics/animations (not giving any links to them).
- : Why they *might* work: if something animated was replaced by something non-animated, the game has less to draw.
- : Negative impact: less pretty.
- Mods that decrease rendering distance (e.g. turn off torches, etc. outside the player's view).
- : Why they *might* work: Every light source requires extra calculations. Less rendering distance = less light sources.
- : Negative impact: can *reduce* performance when you are actively moving (less rendering distance = things need to be rendered more often). Also you might actually *need* the light from out-of-screen sources (to see on your home base, in tile-protected dungeons, etc.). These mods can cause "non-rendered area" to be sometimes seen by player ("I sit in the captain's chair, and half of my ship visually disappears" kinds of problems).
- Mods that optimize quests by making them check "Has item N been obtained?" less frequently.
- : Why they *might* work: this is checked too often (several times per second), and when you have many dozens of unfinished quests (which you should avoid anyway, see #Self-inflicted lag below), this can reduce performance.
- : Negative impact: potential issues with "defeat monsters" quests. Also every time you obtain the necessary quest item, there will be a 1-3 seconds delay before the quest counts as completed.

## Methods that absolutely never work
- **Any "fps improver" and "thread increaser" mods** - these are placebo. **They don't work.**
- : Why they can't work: Starbound mods simply don't have the engine access that would allow them to "increase threads", etc. Any mod that claims to do so is **lying/fraudulent**. It doesn't matter how plausible it sounds: **they are incorrect or lying**.
- :  *Info for modders: about workerPoolThreads variable:*While there is a configuration setting that makes Starbound **spawn** more threads, **the game will NOT use them for any useful computations**. The true problem is, Starbound doesn't know how to distribute its tasks between threads (which is why it doesn't spawn them). You can make it spawn 100 threads, but Starbound will keep computing everything in one of them.
Numerous mods that change this variable are 100% placebo.
- **Image optimization mods** (parallax compressors, etc.): we have thoroughly tested this approach, and there was no impact on performance whatsoever.

## Self-inflicted lag
99% of "Starbound is slow" problems are Starbound's fault, but here are some situations when the player makes the game slower:
- **Using non-throttled Item Transference Devices**
- : Why is this slow: Because ITDs try to move items several times per second. Every time they need to check ALL slots of ALL input/output chests.
- : Impact: very, very high. Having even 5-10 **non-throttled** ITDs will decrease performance of the game. With 20 your game will lag to a halt.
- : **How to fix**: Use a Configurable 3-State Cycler (its page explains how) with your ITDs. It will drastically (by more than 10 times) reduce CPU usage by each ITD, since most ITDs don't need to run multiple times per second.
- **Using too many Watchers**
- : Why is this slow: Starbound needs to run calculations in every loaded part of the map, and Watchers keep more of the map loaded. Having several necessary Watchers is ok, but if you place a ton of them, it will slow down the game.
- **Lots of tethered pets, NPCs, farm beasts nearby**
- : Why is this slow: Each of them needs some calculations. It's probably ok for 10 Mooshi cows, but 100 of them will lag.
- **Nearby chests with many weapons, saplings, mech parts, etc.** (especially bad on player's ship)
- : Why is this slow: Each time such chest appears in the loaded area of the map, Starbound runs "buildscripts" (Lua scripts that run when some item "appears" in the game) for every single item in that chest. Because weapons, saplings, etc. all have buildscripts, having a chest with 128 weapons is not something that you want on your base/ship. Basic resources (crafting materials, liquids, blocks) don't cause this problem, because they don't have complex buildscripts.
- : **How to fix**: Move chests with weapons, mech parts, saplings, etc. to some far away area (ideally onto another planet).
- **Accepting too many quests and not completing them** (except SAIL missions like Verdant Ruins, they are okay to accept and keep unfinished)
- : Why is this slow: For every quest like "obtain Hydrogen" or "find Ferozium Cleaver", the game frequently checks "does the player have this item". For every quest like "save NPC from bandits", the game checks "is NPC still alive, is player near the NPC, are bandits defeated", etc. This is insignificant for 5-10 quests, but if you accept 20+ quests at the same time, then slowdown will start building up.
- **Broken mods, or far too many mods**
- : Why is this slow: Errors require your game to process and attempt to resolve them. More mods adds more chance for incompatibilities, and adds more scripts for the game to keep track of.
- : **How to fix**: Read Incompatible, and check your mods. If you're using 200+ mods, consider whether you need them all (races you're not playing, etc.). Try to avoid mods which haven't been updated prior to the current version of Starbound (1.4.4, released 7th August 2019), and those which are especially script-heavy.

## Other best practices
- Avoid functional machinery on the player's ship. If one planet lags because of many extractors/sifters/centrifuges, then it's just that one planet. If your ship lags, it's a much bigger problem. If the shipworld's file is too large, servers may register it as corrupt and reset it.
- Keep storage on player's ship to a minimum (because all buildscripts run every time you beam up, and because every stored item increases the size of your shipworld). Having a locker with EPPs and EPP Augments is ok, but don't have 20 chests with everything up there.
- If you build large automated factories, have them on different planets (not on the same planet as your main base, so that it won't lag because of those factories).
- If you use rails (vanilla Starbound feature), know that the Rail Tram, Rusty Rail Platform and Composite Rail Platform are badly affected by lag, while the FU-added Solid Rail Platform suffers less from this (tradeoff: you can't jump or drop through it). You can also use a Powered Rail Hook, which is much less affected by lag.

## If Starbound takes 5+ minutes to start
You probably have unpacked mods (e.g. if you have installed FU from GitHub). Mods load significantly faster from .pak file (see [Starbounder: Modding Basics](https://starbounder.org/Modding:Basics) for how to pack/unpack mods), especially with HDD. With SSD this is less relevant (the game loads very quickly even with unpacked FU).
- Mods from Steam Workshop are already packed (you don't need to worry about them).
- Each [release of Frackin' Universe](https://github.com/sayterdarkwynd/FrackinUniverse/releases) comes with a .pak file already prepared.