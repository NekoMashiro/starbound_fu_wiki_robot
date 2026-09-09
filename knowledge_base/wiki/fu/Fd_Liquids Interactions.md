# [FU] Fd:Liquids Interactions

**来源**: Frackin' Universe Wiki | **分类**: Imported | **链接**: https://frackinuniverse.miraheze.org/wiki/Fd:Liquids_Interactions

---

## **Introduction :**
Frackin Universe adds a lot of liquids and thus many interactions. Below is my attempt to show and classify all of these. Feel free to correct them if you think it is necessary, clarify some points if they are too unclear to you, and post new ones! Also be careful of chain interactions*** otherwise some subtle reactions may appear in the blink of an eye and you wouldn't see them because other interactions would have happened by then. 

Note that some interactions remained somewhat elusive to me because of their complexity, e.g. Black Tar with Mercury residues** (the notion of residues is important) which is a chain reaction. Well have fun figuring out what the hell is wrong with that one.

**Important Note : Keep in mind that all of the interactions mentioned below were tested in a personal state station and was on V.5.6.2.11. Content on this page is subject to change with updates.**

**Important Note 2 : It is worth mentioning that there are 2 types of liquid nodes: Core/sea and dynamic. Core/sea liquid nodes generate an infinite supply of that liquid and never run out. This is how cores/seas operate. Dynamic nodes will disappear once the liquid has been extracted. All tests were conducted on dynamic nodes and not on core/sea nodes.**

## **Types of Interactions : **
**a) Type 0 (or None) - "Both Parties Unaffected"** : The most obvious one which occurs when there are no reactions or barriers or other. However, when this interaction occurs and fluids are placed on top of each other, the lower one tends to absorb the residues of the upper one to get an integer area*, which might be worth mentioning I guess.

**b) Type 1 - "Dominant Reaction"** : It happens when a fluid directly reacts to an adjacent fluid in one way or another. I will call here "Dominant Reactions" reactions that result in one fluid or solid, and "Weak Reactions" reactions that result in two or more fluids and/or solids.

**1.1 -  "Dominant Fluid Reaction"** : The title says it all. Ex: Poison and Water returns Poison. (Must specify results)

**1.2 - "Dominant Solid Reaction"** : Same as the previous one but for blocks. I don't have any examples so it remains hypothetical. (Must specify results)

**c) Type 2 - "Barrier"** : In this case, fluids will react indirectly and create a barrier setting them apart (there may also be other indirect interactions). I will try here to distinguish as precisely as I can those different types of barriers.

**2.1 - "Fluid Barrier"** : These barriers are formed when two fluid touch and it will encase another fluid at the frontier. (Must specify which fluid)

**2.1.1 - "Fluid Residual Barrier"** : A barrier of fluid formed in the interaction and blocking both fluids from interacting, except it's only with one fluid's residues.

**2.1.2 - "Fluid Barrier with Dominant Fluid and/or Absorbed Fluid (with or without Residues)"** : Same case as 2.1.2 but with a fluid barrier (Of course MSW)

**2.2 - "Solid Barrier"** : A barrier of blocks will form and separate both fluids. This is just the general one and oftentimes more nuanced cases will appear. (Must specify which block)

**2.2.1 - "Solid Residual Barrier"** : Same case as 2.2 but fluid residues only react. (MSW)

**2.2.2 - "Solid Barrier with Dominant and/or Absorbed Fluid (with or without Residues)"** : The barrier will somehow consume more of one fluid than the other resulting in one fluid remaining after a certain amount or iterations. Dominant fluids will... well dominate in ther interaction if that makes sense while Absorbed Fluids will instead be more and more consumed each time but the point in mentioning them is that Absorption cases do not require one fluid's domination to happen. (I still don't think it makes enough sense but test it and see the difference)(Is best written that way : " and Dom. and Abs. " if not reacting with residual fluids AND " and Dom. and Abs. " if that's the case) (Of course MSW)

**2.3.1 - "Double Solid Barrier"** : A two-blocks-wide barrier. Simple enough.

**2.3.2 - "Double Fluid Barrier"** : Won't bother explaining. This case remains hypothetical yet it's still worth mentioning.  

**d) Type 3 - "Weak Reaction"**

**3.1.1 - "Single Weak Fluid Reaction"** : A fluid interaction where only one fluid will react independently from the other to form another fluid. (MSW)

**3.1.2 - "Double Weak Fluid Reaction"** : A fluid interaction where both fluids react yet independently from each other. (MSW)

**3.2.1 - "Single Weak Solid Reaction"** : Same as 3.1.1 but blocks are formed.

**3.2.2 - "Double Weak Solid Reaction"** : Same as 3.1.2 but blocks are formed.

- Integer Area : In general, a fluid area whose top matches the border of a block so that you can count the area in blocks or half-blocks if bordered by a slopy terrain.

 - Residues : A certain small amount of fluid placed on top of an integer or null fluid area which interacts differently from integer amounts. Requires more precision at the moment.

 - Chain Interactions: Not to be confused with Reactions which are specific types of interaction. Happens when one interactions implies at least another interaction.
## **Main Liquids Interactions Board**

| | Water | Lava | Poison | Bio-Ooze | Black Tar | Blue Grav-Liquid | Dark Water | Essentia Obscura | Liquified Crystal | Liquified Irradium | Sulphuric Acid | Liquid Protocite | Mercury | Orange Grav-Liquid | Organic Soup | Pus |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Water | None | Lava | 1.1 - Poison | Slime Glob | None | Blue Grav-Liquid | Umbral Dirt | None | Crystal Block | | Sulphuric Acid | | Mercury | Blue Grav-Liquid | Poisonas | Contaminated Water |
| Lava | 2.2 - Magmarock | None | Poison | | | | | | | | | | | | | |
| Poison | 1.1 - Poison | None | None | 2.2.2 - Slime Glob with Dominant Poison | | | | | | 2.2.2 - Rainbow Sand with Dominant Poison | | | | | | |
| Bio-Ooze | 2.2 - Slime Glob (To be verified) | None | 2.2.2 - Slime Glob with Dominant Poison | None | Black Tar | | | | | | | | | | | |
| Black Tar | None | 2.2.1 - Burning Volcanic Rock Barrier with Lava Residues | 2.2.2 - Tarry Stone with Dominant Poison | 2.2.2 - Tarry Stone with Dominant Bio-Ooze | None | Black Tar | | | | | | | | | | |
| Blue Grav-Liquid | 1.1 - Blue Grav-Liquid | None | 1.1 - Poison | 1.1 - Blue Grav-Liquid (TBV) | 1.1 Black Tar | None | None | | | | | | | | | |
| Dark Water | 2.2 - Umbral Dirt | None | None | 2.2.2 - Corruption with Dominant Bio-Ooze | 2.3.1 - Tarry Stone | None | None | Essentia Obscura | | | | | | | | |
| Essentia Obscura | None | 2.2.2 - Sulphuric Stone with Dominant Essentia Obscura | None | 2.2 - Rainbow Sand | None | 2.2.2 - Corruption with Dominant Essentia Obscura | None | None | Liquified Crystal | | | | | | | None |
| Liquified Crystal | 2.2 - Crystal Block (TBV) | None | 2.2.2 - Stellara Crystal with Dominant Poison | 2.2.2 - Stellara Crystal with Dominant Liquified Crystal | 2.2.2 - Crystal Block with Absorbed Liquified Crystal | None | None | 2.2.2 - Corruption with Absorbed Liquified Crystal and Dominant Essentia Obscura | None | Liquid Irradium | | | | | | |
| Liquid Irradium | 2.2 - Rainbow Sand | None | 2.2.2 - Rainbow Sand with Dominant Poison | 2.2.2 - Rainbow Sand with Dominant Liquified Crystal | 1.1 - Liquid Irradium | 2.3.1 - Aether Dust | None | 1.1 - Essentia Obscura | 2.2.2 - Aether Dust with Absorbed Liquified Crystal and Dominant Liquid Irradium | None | Sulphuric Acid | | | | | |
| Sulphuric Acid | 1.1 - Sulphuric Acid | 2.2.2 - Sulphuric Stone with Dominant Sulphuric Acid | None | 2.3.1 - Wastestone | 2.3.1 - Tarry Stone | 2.2.2 - Aether Dust with Absorbed Blue Grav-Liquid | None | None | 2.2.2 - Aether Dust with Absorbed Liquified Crystal and Dominant Sulphuric Acid | 3.2.1 - Liquid Irradium turns into Wastestone Block | None | Liquid Protocite | | | | |
| Liquid Protocite | 2.2 - Slime Glob (TBV) | None | 2.2.2 - Slime Glob with Dominant Poison | 2.1.2 - Liquid Irradium with Dominant Bio-Ooze | 1.1 - Liquid Protocite | 2.2.1 - Yellow Glow Rock Barrier, Umbral Dirt Residual Barrier with Liquid Protocite Residues | None | 1.1 - Essentia Obscura | 2.2.2 - Stellara Crystal with Dominant Liquid Protocite | 2.2.2 - Rainbow Sand with Dominant Liquid Protocite | 3.2.1 - Liquid Protocite turns into Wastestone Block | None | Mercury | | | |
| Mercury | 1.1 - Mercury | None | | 2.2 - Rainbow Sand | 1.1 - Mercury turns into Sulphuric Acid | None | None | None | None | None | 1.1 - Sulphuric Acid | 2.1.2 - Liquid Irradium with Dominant Protocite | None | Orange Grav-Liquid | | |
| Orange Grav-Liquid | 3.1.2 - Water and Orange Grav-Liquid turn into Blue Grav-Liquid | None | 1.1 - Poison | 3.1.2 - Bio-Ooze turns into Blue Grav-Liquid | 1.1 - Black Tar | None | None | 2.2.2 - Corruption with Absorbed Orange Grav-Liquid and Dominant Essentia Obscura | None | 2.2.2 - Aether Dust with Absorbed Orange Grav-Liquid | 2.2.2 - Aether Dust with Absorbed Orange Grav-Liquid and Dominant Sulphuric Acid | 2.2.1 - Yellow Glow Rock Barrier with Absorbed Orange Grav-Liquid, Umbral Dirt Residual Barrier with Lava Residues | None | None | Organic Soup | |
| Organic Soup | 3.1.1 - Water turns into Poison | 2.2.1 - Burning Volcanic Rock Barrier, Purple Crystal Block Residual Barrier with Lava Residues | 1.1 - Organic Soup | 2.2.1 - Gelatinous Stone Barrier, Slimey Soil Residual Barrier with Bio-Ooze Residues | 3.1.2 - Organic Soup turns into Tarry Stone | 1.1 - Organic Soup | None | 2.2.2 - Corruption block, dominant Essentia Obscura, no residues | 2.2 - Crystal Block | 1.1 - Organic Soup | 3.2.1 - Organic Soup turns into Tarry Stone | 1.1 - Organic Soup | 3.1.1 - Mercury turns into Sulphuric Acid | 1.1 - Organic Soup | None | Pus |
| Pus | 3.1.1 - Pus turns into Plasmic Fluid | None | 2.1 - Plasmic Fluid | 1.1 - Bio-Ooze | 1.1 - Black Tar | None | None | 1.1 - Essentia Obscura | None | 1.1 - Liquid Irradium | 1.1 - Sulphuric Acid | 1.1 - Liquid Protocite | None | None | 1.1 - Organic Soup | None |

## Trivial Liquid Interactions Boards
Some liquids barely have more than 4 interactions at the moment, so placing them in the main board would just be a waste of time.

**- Liquids with no interactions :** Liquid Erchius Fuel, Coconut Milk, Plasmic Fluid, Beer, Deuterium, Liquid Metallic Hydrogen

**- Liquids with only one interaction (and their interaction) :**

- Oil : Lava and Oil returns 3.2.1 - Oil turns into Asphalt (TBV)

- Helium-3 : Dark Water and Helium-3 returns 2.2.2 - Aether Dust with Dominant Helium-3

- Pure Honey : Water and Pure Honey returns 1.1 - Pure Honey

- Shadow Gas : Poison and Shaodw Gas returns 2.2.2 - Block of Darkness with Dominant Poison

**- 5-or-less-Interactions Liquids Board :**

| | Water | Bio-Ooze | Contamined Water | Dark Water | |
| --- | --- | --- | --- | --- | --- |
| Healing Water | 1.1 - Healing Water | 1.1 - Bio-Ooze | 1.1 - Healing Water | 2.2.1 - Gelatinous Stone Barrier, Umbral Stone Residual Barrier with Healing Water Residues, Jelly Block Residual Barrier with Dark Water Residues | |
| | Water | Lava | Poison | Liquid Iron | Liquid Nitrogen |
| Slime | 3.1.1 - Water turns into Poison | 1.1 - Lava | 2.2.2 - Slime Glob with Dominant Poison | 3.1.1 - Slime turns into Lava | 2.2.2 - Ice with Dominant Slime |
| | Water | Contamined Water | Liquified Crystal | Liquid Nitrogen | |
| Swamp Water | 1.1 - Swamp Water | 1.1 - Contamined Water | 2.2.2 - Crystal Block with Swamp Water Residues, Purple Crystal Block with Dominant Swamp Water (TBV) | 2.2.2 - Ice with Dominant Swamp Water | |
| | Lava | Essentia Obscura | Liquid Iron | | |
| Aether | 2.2 - Aether Dust | 2.2.2 - Elder Stone with Dominant Aether | 2.2 - Aether Dust | | |
| | Water | Lava | Poison | Liquid Irradium | Mercury |
| Blood | 1.1 - Blood | 2.2 - Blood Stone | 1.1 - Poison | 2.2.2 - Blood Crystal with Dominant Liquid Irradium | 2.2.2 - Blood Stone with Absorbed Blood |
| | Water | Poison | Healing Water | Swamp Water | |
| Contamined Water | 1.1 - Contamined Water | 2.2.2 - Clay with Dominant Poison | 1.1 - Healing Water | 1.1 - Contamined Water | |
| | Lava | Slime | Aether | Essentia Obscura | |
| Liquid Iron | 1.1 - Lava | 3.1.2 - Slime turns into Lava, Liquid Iron turns into Lava | 2.2 - Aether Dust | 2.2.2 - Corruption with Dominant Essentia Obscura | |
| | Water | Lava | Slime | | |
| Liquid Nitrogen | 2.2 - Ice | 2.2 - Cloud | 2.2.2 - Ice with Dominant Slime | | |

## Block Interactions with Fluids Board
Blocks interact with fluids so I guess they could get classified in a board too. Please add more info if you can.

**- Type 1 **: Fluid Unaffected and Block Reaction only

| | Dirt | Purple Crystal Block | Bony Flesh | Burning Volcano | Umbral Stone | Gelatinous Stone | Crystal Block | Sand |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Water | | | | | | | | |
| Lava | 1 - Cooled Volcanic Rock | | | 1 - Andesite (TBV) | | | | |
| Poison | 1 - Raw Sewage | | 1 - Rotting Flesh (TBV) | | | | | |
| Oil | 1 - Tar | | | | | | | |
| Liquid Erchius Fuel | | 1 - Erchius Crystal (TBV) | | | | | | |
| Coconut Milk | | | | | | | | |
| Healing Water | | | | | 1 - Gelatinous Stone | | | |
| Slime | 1 - Slimey Soil | | | | | | | |
| Swamp Water | | | | | | | | |
| Aether | | | | | | | | |
| Plasmic Fluid | 1 - Alien Soil | | | | | | | |
| Beer | | | | | | | | |
| Bio-Ooze | | | | | | 1 - Patak Crystal | | 1 - Proto Gravel |
| Black Tar | 1 - Tar | | | | | | | |
| Blood | | | | | | | | |
| Blue Grav-Liquid | 1 - Cloud (TBV) | | | | | | | |
| Contamined Water | 1 - Waste | | | | | | | |
| Dark Water | 1 - Umbral Dirt | | | | | 1 - Corruption | | |
| Deuterium | | | | | | | | |
| Essentia Obscura | | | | | | | | |
| Helium-3 | | | | | | | | |
| Liquified Crystal | 1 - Stellara Crystal | 1 - Crystal Block | | | | | | |
| Liquid Iron | 1 - Ash | | | | | | | |
| Liquid Irradium | 1 - Radiocative Soil | | | | | | | |
| Sulphuric Acid | 1 - Sulphruc Dirt | | | | | | | |
| Liquid Metallic Hydrogen | | | | | | | | |
| Liquid Nitrogen | 1 - Ice | | | | | | | |
| Liquid Protocite | | | | | | | | |
| Mercury | | | | | | | | |
| Orange Grav-Liquid | 1 - Cloud (TBV) | | | | | | | |
| Organic Soup | | | | | | | 1 - Purple Crystal Block | |
| Pure Honey | 1 - Honey Material | | | | | | | 1 - Golden Sand |
| Pus | 1 - Bonemeal | | | | | | | |
| Shadow Gas | | | | | | | | |

> Category:Liquid
> Category:Interaction
> Category:Infinite
> Category:Water
> Category:Needs Data
> Category:Needs Revision