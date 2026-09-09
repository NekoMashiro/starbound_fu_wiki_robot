# [FU] Fission Reactor

**来源**: Frackin' Universe Wiki | **分类**: Crafting stations, Power, Imported | **链接**: https://frackinuniverse.miraheze.org/wiki/Fission_Reactor

---

**Fission Reactor** uses radioactive materials to generate power. It can generate from 10W up to a maximum of 360W with all four fuel slots used. Higher power will be highly radioactive.

## Mechanics
The Fission Reactor's interface has six slots. The first four slots on the top, labelled Fuel Slots, are where fuel for the Fission Reactor is inserted, while the other two slots below, labelled Waste, are where Toxic Waste and Tritium Rod produced by the reactor are stored.

While fuel is inside the reactor, each slot has a chance to decay every second with the chance depending on the fuel type. If a slot decays, then one fuel item in that slot is consumed, a piece of Toxic Waste appears in a Waste slot, and a rod of Tritium has a 50% chance of appearing in the other Waste slot (if Tritium is created, a second piece of Toxic Waste is generated).

The Fission Reactor accepts the following inputs:

| Fuels (s) | Power (W) | Average time per decay (s) |
| --- | --- | --- |
| Tritium Rod | 10 | 40 |
| Liquid Irradium | 12 | 30 |
| Deuterium Rod | 15 | 50 |
| Uranium Rod | 20 | 90 |
| Plutonium Rod | 30 | 90 |
| Neptunium Rod | 40 | 90 |
| Thorium Rod | 50 | 90 |
| Enriched Uranium Rod | 60 | 120 |
| Enriched Plutonium Rod | 70 | 180 |
| Solarium Star | 80 | 240 |
| Ultronium Rod | 90 | 300 |
| Purrpetual Energy | 120 | 500 |

Total reactor power is the sum of the power outputs of all fuel slots (for example, if one slot has Solarium Stars and another has Uranium Rods, then the total power is [80W + 20W =] 100W).

### Radiation
While the Fission Reactor is running, a hidden value called radiation, which always falls within the number range [0, 120], increases by 2*(total power - 4) units per second. If the stack of Toxic Waste in the Waste slot is 75 units or larger, radiation increases by another 5 units per second (regardless of whether the reactor is running). When a fuel item decays, radiation increases by another 5 units for each filled waste slot (10 if both slots are filled); in the case that the slot containing Toxic Waste cannot hold any more items, additional Toxic Waste items will drop onto the ground and raise radiation by another 5 units.

Radiation is reduced by 5 units per second if the Fission Reactor is turned off (by wiring Off signal to its left ) or contains no fuel.

If radiation is high enough, all entities close to the Fission Reactor will be hit by radiation projectiles every second. You will then get radiation sickness & get damage from it. Higher radiation increases the range at which you will get sick (maximum of 16 tiles around the placement point).

Presence of blocks between player and reactor is irrelevant: it doesn't protect from radiation.