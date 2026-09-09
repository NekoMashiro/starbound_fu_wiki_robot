# [FU] Duplicator

**来源**: Frackin' Universe Wiki | **分类**: Precursor, Wiring, Imported | **链接**: https://frackinuniverse.miraheze.org/wiki/Duplicator

---

**Duplicator** is a Precursor machine for duplicating specific materials. In order to function, it needs:
- 200W of power;
- One Neutronium Rod and Anti-Neutronium Rod in their specific slots;
- The item to duplicate.
It has two input (blue) wiring slots: the upper slot is an On/Off Switch, the lower slot is the energy receiver.

The Neutronium and Anti-Neutronium aren't consumed once the process begins - they only serve to start it, as if some sort of key or catalyst.

The Duplicator can be found in Precursor mini-biomes and in the Precursor Ruins mission.

The material in the "item" slot does not get consumed or altered - instead, the resulting duplicated items are placed in the "output" slot.

The highest value item that it can duplicate is Superior Fertilizer, which costs 1068 pixels.

 The Duplicator placed on the world.

## Items
Below is a list of items accepted by the machine for duplication. Any of them takes 3 seconds to duplicate.
- Biofuel Canister
- Erithian Biofuel Canister
- Protocite Fuel Canister
- Lasombrium Seed
- Fertilizer
- Advanced Fertilizer
- Superior Fertilizer
- Glass
- Putrid Slime
- Mulch
- Morphite
- Unstable Particles
- Uranium Rod
- Neptunium Rod
- Plutonium Rod
- Thorium Rod
- Solarium Star
- Copper Bar
- Silver Bar
- Iron Bar
- Titanium Bar
- Durasteel Bar
- Gold Bar
- Tungsten Bar
- Densinium Bar
- Quietus Bar
- Effigium Bar
- Amber Chunk
- Irradium Bar
- Isogen Bar
- Telebrium Bar
- Penumbrite Shard
- Prisilite Star
- Protocite Bar
- Pyreite Bar
- Lunari Crystal
- Trianglium Pyramid
- Xithricite
- Zerchesium Bar
- Refined Violium
- Refined Ferozium
- Refined Aegisalt

## Fuel
The Duplicator will accept any valid ship fuels as fuel.
The formula for fuel consumption is target item's pixel value divided by the fuel amount, rounded up.
If this amount is under 1 prior to rounding, it is inverted and becomes the amount produced, rounded down.
In either case, 'excess' fuel consumption is retained as a proportionate chance to provide additional output.

As example: D-hydrogen cores have a fuel value of 8000. Densinium bars have a price of 840. Thus, cores per bar is under 1 (at 0.105). inverted this becomes 9.52380952. Thus, you produce 9 bars with a 52% chance to produce a 10th.

## See also
- Duplicator automation