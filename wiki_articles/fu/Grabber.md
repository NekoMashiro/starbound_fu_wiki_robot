# [FU] Grabber

**来源**: Frackin' Universe Wiki | **分类**: Mechanics | **链接**: https://frackinuniverse.miraheze.org/wiki/Grabber

---

**Grabber** is a 4/8/16-slot storage. It automatically "steals" any nearby item that is lying on the ground (e.g. was just dropped by a defeated monster). That item is stored inside the Grabber (player can retrieve it at any time).

Grabbers are often used with Harvester Turret, Farmbeast Harvester Turret or Bug Harvester Turret to collect the dropped materials.

## List of grabbers
- Grabber v1 - 4 slots, range 4.
- Grabber v2 - 8 slots, range 8.
- Grabber v3 - 16 slots, range 12.
- Grabber (Ship) - for shipworld only, drags items to the player instead of storing them.

## Performance impact
Grabbers frequently scan their surroundings, which may decrease performance if you have many of them.

To avoid lag, you can throttle the Grabber (see Configurable 3-State Cycler for an example) the same way as you would throttle an Item Transference Device.

## See also
- Item Dropper - drops items on the ground.
- Item Sensor - sends "ON" signal if there is some item nearby.