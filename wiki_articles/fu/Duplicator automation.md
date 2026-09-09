# [FU] Duplicator automation

**来源**: Frackin' Universe Wiki | **分类**: Tutorials, Precursor, Wiring | **链接**: https://frackinuniverse.miraheze.org/wiki/Duplicator_automation

---

Since the Precursor Duplicator is a rather rare find and some processes require a lot of duplication to be comfortably automated, it is a good idea to automate a single duplicator to produce several materials (at least until more duplicators can be procured).

## Required Items
Appart from power and duplicator fuel the following items are needed only once:
- 1x Duplicator (and of course Neutronium Rod and Anti-Neutronium Rod)
- 1x NOT Gate (the compact versions were used in the pictures)
The following items are needed per material to be duplicated:
- 2x Single-Slot Storage
- 2x Capacity Sensor
- 4x Item Transference Device
- 1x NOT Gate (the compact versions were used in the pictures)
- 3x Material to be duplicated

## Automation Phases
Each material is processed in four phases: Duplication, Buffering, Prototype-Switch and Output. Once all phases have been completed for one material, the process starts with the next. The setup/wiring will be explained along with the four phases.
The example duplicates three different materials but can of course be extended at will, though each additional material will also increase the duration of one entire production cycle. To increase throughput additional duplicators can be installed.

## Phase 1: Duplication
At this point the prototype storages on the left each contain one of the respective materials to be duplicated, except for one, which is already in the duplicator's first slot. The duplicator will create one/multiple copies in its fifth slot.

## Phase 2: Buffering
Each material has a dedicated ITD to pull the duplicator's result into a dedicated buffer (the storages on the right of the duplicator). Once any of the buffers contains a material, its Capacity Sensor turns off the duplicator (via a central NOT Gate).

## Phase 3: Prototype-Switch
Once a buffer contains a duplicated material, it triggers the current prototype to be pulled from the duplicator (left column of ITDs) and the prototype of the next material to be put into the duplicator (right column). In case of multiple duplicators the ITDs need to split the prototypes evenly.

## Phase 4: Output
Now that the previous prototype is back in its storage and the next one is in the duplicator, the material from the buffer can be pulled wherever needed (the example simply stores it in a crate). Once all buffers are empty the duplicator is turned back on (see Phase 2) and Phase 1 starts for the next material.

## Additional Remarks
In theory (with some tweaking) it should be possible to have the same material twice (if a different duplication ratio is desired) but I haven't tested it yet ;)