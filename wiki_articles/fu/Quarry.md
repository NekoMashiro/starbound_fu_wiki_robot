# [FU] Quarry

**来源**: Frackin' Universe Wiki | **分类**: Mechanics | **链接**: https://frackinuniverse.miraheze.org/wiki/Quarry

---

**Quarry** is a machine that automatically mines blocks **to the bottom-right** from where it's placed. It will also collect anything it encounters while mining, including vines, chests, etc. It acts as a 16-slots storage and stores everything inside. It doesn't require any Power.

Normally the Quarry will only mine foreground blocks. To make it mine background blocks too, wire its second to something that provides "ON" signal (for example, Signal Emitter or Iron Lever).

At the very beginning of its work (when the Quarry is just placed) it extends its "hand" to the right, up to the maximum reachable horizontal distance (for example, 36 blocks for Iron Quarry). The Quarry can only mine directly below its arm. If there were solid blocks in the way that prevented the arm to be extended, then Quarry will have less horizontal reach than it otherwise would.

## List of Quarries

| Item | Mined area (Horizontal x Vertical) | Movement speed | Strength (damage to block hitpoints) | Maximum mined blocks (foreground only) | Maximum mined blocks (with background) |
| --- | --- | --- | --- | --- | --- |
| Copper Quarry | 24x36 | 1 | 8 | 864 | 1728 |
| Iron Quarry | 36x54 | 3 | 12 | 1944 | 3888 |
| Titanium Quarry | 64x72 | 6 | 24 | 4608 | 9216 |
| Densinium Quarry | 128x128 | 12 | 36 | 16384 | 32768 |

## Possible uses
*These are examples, there may be other uses.*

- After you arrive to a new planet, you can place a Quarry and then go exploring. By the time you return, some free blocks will be waiting for you.
- Quarry can clean a large rectangular area when you want to build something large underground.
- To clean unwanted background walls (leftovers after mining in this area with Mining Laser?).
- To mine very hard blocks, such as Magmarock or Obsidian, because a Quarry deals significantly more **block damage** than pickaxes and Matter Manipulators. Beware that Quarry will mine blocks one at a time (not in 2x2 area or larger, as MM or pickaxes do).
- : It takes 60 seconds for a Copper Quarry to mine a single Dead Core block. Densinium Quarry does this in 7 seconds.
- To remove Ash Pile blocks that often rain from the sky on planets like Infernus. It's much less practical than using a Field Generator (tile protection solves the problem better: when the Ash Pile blocks fall on tile-protected area, they won't be placed on top of it - instead the Ash Pile will drop as items).
- For in-world liquid mixing that produces blocks, e.g. to remove Clay from a lake with Contaminated Water and Poison. This is much slower than Liquid Mixer (which does 6 mixings per second), but it might have its uses (e.g. when one liquid comes from a Rain-like weather).

## Limiting the area
- Limiting the horizontal reach (when you want the Quarry to NOT mine further than N blocks to the right) is easy: before placing a Quarry, place a block that will be in the way of Quarry arm's attempt to extend to the right.
- To limit the vertical reach (how deep can Quarry mine), you will need to use Field Generator to apply **tile protection** to the bottom of intended pit. Quarry mines from top to bottom, and it won't be able to remove tile-protected blocks, so it will stop at the depth where it encounters them.
- : Alternatively, when mining near the surface, you can place Quarry high in the air (for example, if you want to dig a pit of depth 20 using a Copper Quarry, which normally digs to depth 36, you can place that Quarry 16 blocks above the surface).

## See also
- Pump - machine for mining liquids.