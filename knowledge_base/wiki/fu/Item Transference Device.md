# [FU] Item Transference Device

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/Item_Transference_Device

---

> You can't factorio in Starbound.
> — Popular misconception

**Item Transference Device** (ITD) is (not a joke!) the strongest device in the game. It can water/fertilize your crops, sort your items, move food into refrigerators, sands into Sifters, ores into Blast Furnace, and is a basis of complex factories. If you learn how to use it.

If you set it up correctly, it will save you the most important resource of all: your time. You can explore and build more, and do tedious things less.

When used improperly, it can also create a lot of lag. See Configurable 3-State Cycler for how to avoid it.

> -Note from Kherae, the device's creator: Please be careful with these on multiplayer servers, and be considerate of others. Avoid moving items into full containers (can be prevented with Capacity Sensor).

## How to use
Place the ITD onto the background wall. Switch your Matter Manipulator into Wiring mode (or equip Mechanic's Wrench). You will see three small circles (two at the bottom, and one at the top).

Suppose you want to move water from Well to Growing Tray.
1. Connect the of the ITD to the of the Well. 
1. Connect the of the ITD to the of the Growing Tray.

You can connect one ITD to several Wells and/or several Growing Trays simultaneously. You can also connect ITD to Repeater.

 and Growing Tray.]]

## Menu of the Item Transference Device
When standing near the Item Transference Device, you can interact (**[E]** button) with it. Here you can give specific orders to ITD: for example, if you want to automatically move harvested plants (but not seeds, liquid and fertilizer) from the Growing Tray, then you can order the following: "Do NOT take items from slots 1,2,3 of the Input container".

You can also limit "which items can/can't be moved", etc. See below for all options. Also see Item Network for more practical examples.

### Slots
**Input slots/Output slots** refers to the storage connected to the corresponding Input/Output (Blue/Red) circle, i.e., adding slot "1", will cause the ITD to only look at the 1st inventory slot in a connected storage. Enter the slot number in the text box and then click the **+** to add it to the list. To remove, click the entry and then the **-** button. Clicking the "I" under the slots will cause the ITD to ignore those slots. For example, if input slots 1, 2, and 3 are added to the ITD and the "I" is marked green, the ITD will look for items in every slot except for 1, 2, or 3.

*Example*: You want to feed a whole storage container's worth of items into an extraction device. Let's say blocks into a powder sifter. Set the ITD connecting the storage box to the sifter to ONLY fill the sifter's first two slots, as the rest are what it will be generating and if filled there won't be room left for your sifting results. In other words, specify that you want only **output** slots 1 and 2 to move over. Then, when you want to take whatever the sifter is producing and move it out to some other storage container, you'll need a second ITD, and you'll have to set it to **ignore input** slots 1 and 2. If you don't do that, you'll pull out the things you're intending to sift, and you'll empty your initial block storage container real fast without having sifted a thing!

### Item filter
To create filters that work with specific items, place an item in the **Item slots** to the right of the input/output slots list.

The amount of item placed inside the **Item slots** will caused only the multiple of the amount set to be transported (i.e putting 2 ore in the **Item slots** will cause a multiple of 2 of the ores to be transported [2,4,6,8,...] leaving a remainder of 1 ore in first storage (if any) ). This is particularly useful for transferring an even amount of ore into the furnace.

Below the Input/output slots there is a set of lists with a corresponding **Item slot #** (i.e. Item 1, Item 2..). Here you can specify how the ITD is to handle a certain item.
- **Exact** means that the ITD will only process that exact item.
- **Type** means that the ITD will only process that type of item, indicated by an items gray text under the items name, i.e *Crafting Material, Light Source, Shortspear, Legwear*.
- **Category** means that the ITD will only process that broad category of item, e.g. "All tools", "All weapons", "All buildings" (this is much more broad than Type). See [GitHub](https://github.com/sayterdarkwynd/FrackinUniverse/blob/master/scripts/kheAA/transferconfig.config) for complete list.
- : Note: when automating various machinery, you almost always want Type filter (more precise), not Category (too broad to be useful). Category filter is mostly used to sort items in long-term storage (reagents in one chest, weapons in another, etc.).
- **Inv. Logic** (Inverted Logic) is an additional rule to the above rule-set. If selected, the ITD will ignore the item/type/category in the corresponding slot.

### Splitting
- **Even Split** (if enabled) will divide items between several chests. For example, if 400 Water is moved into 4 Growing Trays with "Even Split" on, then each Tray will receive 100 Water.
- : If Even Split is NOT enabled, then one Tray will receive all the water until there is no longer any space for Water (then the second tray would start receiving it, then the third, etc.).
- **Slot Split** (if enabled) will divide items between several slots of the target chest. For example, you can equally split Organic Soup between slots 2 and 3 of Trays (both liquid and fertilizer). You can also use this to place fuel into Fission Reactor (which has 4 slots for fuel) and possibly in other situations.

### Limiting options
- **Leave One** (if enabled) will cause operations like "move Water from chest 1 to chest 2" to leave 1 Water in chest 1 (e.g. if chest 1 had 400 Water, then chest 2 will receive 399 Water).
- **Stack Only** (if enabled) will prohibit the ITD from moving items into empty slots: they can only be moved into existing stacks. For example, if chest 1 has 50 Algae and 10 Methanol, and chest 2 has 30 Methanol, and ITD is doing "move items from chest 1 to chest 2" operation, then chest 2 will have 40 Methanol (it was moved successfully), but all 50 Algae will be left in chest 1 (because there was no Algae stack in chest 2).

## Troubleshooting
- If ITD is beeping, it means that you are often trying to move items into a chest that is already completely full.

## See also
- Storage Bridge - if you place it near a chest, ITD can use it to move items from/to this chest.
- Repeater - relay for ITDs (you can make long connections like "ITD -> Repeater -> Repeater -> ... -> Repeater -> Target").
- Item Network Terminal - shows contents of several chests.