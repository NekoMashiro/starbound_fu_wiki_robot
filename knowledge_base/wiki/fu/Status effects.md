# [FU] Status effects

**来源**: Frackin' Universe Wiki | **分类**: Mechanics | **链接**: https://frackinuniverse.miraheze.org/wiki/Status_effects

---

A **Status effect** is a static or dynamic modification of one or more statistical properties of an entity, such as a monster or the player. Status effects apply for some time duration, which may be indefinite, and they may change over time. If an entity is affected by a status effect, it will be subject to the effect until it either wears off, or some event removes it. Entities can gain immunity to certain effects. Status effects range from beneficial to detrimental and come in five types: buff (statistical increase), debuff (statistical decrease), resistance, immunity, and ability. adds well over 700 unique status effects in order to implement various mechanics; this page lists only the logical effects that are communicated via an icon in the game interface.

## Buffs
When there is a range in the table below, the sources are sorted in increasing order of benefit.

| Effect | Description | Default Duration | Sources |
| --- | --- | --- | --- |
| Energy Uptick | Regenerates energy. Dark Roast Coffee confers immunity to various drugs. | 120 | Blonde Coffee, Chunky Meat Coffee, Espresso, Dark Roast Coffee |
| Energy Boost | Increases maximum energy by +6-145. Same effect as the vanilla [Energy Augments](https://starbounder.org/Energy_I_Augment). | 120 | Biscorn (180s), Telk Death-Stick (220s), Little Rascal Herb (180s), Teltik Vison Worm (220s), Bigraxian Hellpowder (220s), Melodistar, Battery Stem Charge, Protovex (60s), VX Special Blend (90s), Fletchweed Stem (60s) |
| Percent Energy Boost | Increases maximum energy by 15-35%. Same effect as the vanilla [Bonus Energy](https://starbounder.org/Bonus_Energy) (+20%). | 120 | Yellow-foot Mushroom, Pinkloom Herb (60s), Refined Kadavan Spices (60s), Organic Energy Stim, Silverleaf Herb (60s) |
| Energy Regen | Increases energy regeneration by 2.5-37.5%. Energy block time reduced by 1.25-18.75%. | 120 | Acutaque (20s), Battery Stem Charge, Star Mint, Blex Cactus Sap (60s), Liquid Protocite, Erithian Energy Pack (augment), Goldenglow Petal (60s), Energiflower, Greenleaf Herb (60s), Cappa (220s), Protocite Energy Pack (augment), Hale Flower Petal (60s), Hooded Survival Mask (armor), Elder Crown (armor), Antimatter Energy Pack (augment), Protheon Shard (artifact), Quantum Energy Pack (augment) |
| Health Boost | Increases Max Health by +5-120 | 180 | Biscorn, Heartroot (300s), Little Rascal Herb, Melodistar (120s), Helkat Nut, Ambrosia (60s), Strong Honey Jar, Tenebrhaeic Kilvrat (120s) |
| Percent Health Boost | Increases Max Health by 25% | 30s | Earthen Honeycomb (60s), Porphis Blossom (60s), Blood Serum Stim (120s) |
| Jump Boost | Increases jump height by 15-35%. Includes the Vanilla [Jump Boost](https://starbounder.org/Jump_Boost) effect (+20%). | 1 | Drug Specialist Contract (30s), Gelatinous Stone (tile), Plasmango (40s), Uberdinner (100s), Violiroot Plate (100s), Jump Scout Visor (armor), Jump Block (tile), Weeeeeeeee! (augment) |
| No Stick | Confers immunity to movement effects of Mud, Slime, Ice and Snow. | 120 | Tenebrhaeic Kilvrat (90s), Corvex Putty |

- Full Belly: Your character is well fed; this buff lasts until your Hunger starts dropping again. While under the effect, you gain limited HP regeneration.
- Spider's Silk: Specific to the Arachne Race; Arachne generate Spider's Silk every 30-60 seconds, which can be used to craft unique Arachne equipment, or be used in making Silk.
- Undead Properties: Specific to the Zombie Race; Zombies do not Breathe or sustain Poison damage.

## Debuffs

| Effect | Description | Default Duration | Resistance | Immunity |
| --- | --- | --- | --- | --- |
| Aetheric Atmosphere | Weather that drains 5-7 health and 3 energy per second. Every 5-3.5 seconds, reduces Max Energy by 7-11 and reduces Energy Regeneration (%) Rate by 0.04, down to 0.1. The effect is increased by 30-50% at night. Levels: Mild, Moderate and Extreme. | 5 | Cosmic | Aether, Cosmic Resistance >= 40/60/90%. |
| Bio-Ooze | Reduces all resistances except poison and shadow by 30-60% (source dependent). Increases Hunger rate. | 5, 20 | Bio-Ooze | Poison Resistance >= 40% |
| Bleeding | Applies 0.75-5% of health as damage over time | 3-15 | | Bleeding (monsters only) |
| Burning | Applies fire damage over time | 5 | Fire | Being in liquid, Fire |
| Cold | Climate that drains 1-20 health and 0.2-0.7 hunger per second, and reduces movement speed by 10/50/60/70/75%. Effect is increased by 10-50% at night or when wet, or by 20% when windy. Levels: Chilled (Snow), Mild (Tundra), Moderate (Arctic, Frozen Volcanic, Nitrogen Sea), Extreme (Ice Waste) and Lethal (randomly on Unknown planets). | 5 | Ice | Cold (up to Moderate), Extreme Cold (up to Extreme). Ice Resistance >= 15/20/40/60/80%. |
| Chill | Weather that drains 3-4 health and 0.3-0.4 hunger every second, and reduces movement speed 40/50/60%. Effect is increased by 20-50% at night or when wet, or by 20% when windy. Levels: Sudden, Severe, Extreme. Encountered on Frozen Volcanic, Ice Waste, Frozen Moon, Aether World and Strange Sea planets. | 5 | Ice | Cold, Extreme Cold. Ice Resistance >= 25/45/65%. |
| Dark Water Poison | Reduces Shadow, Fire and Ice Resistances by 25%, and movement speed and jump height by 20%. | 5 | Poison | Antidote, Poison Resistance >= 50% |
| Def - | Reduces Protection and all resistances by 10-50% | 1-5 | | |
| Electrical Storm | Damages player at random intervals. Damage is 20% higher if the player is in liquid or the weather is windy. Energy regenerates 30% more slowly. | 5 | Electric | Electric Resistance >= 20% |
| Heat | Climate that drains 4-6 health and 0.5-0.7 hunger every second. Reduces movement speed 50-70%. Effect is reduced by 20% at night and 30% when wet. Effect is increased 10-40% underground. Levels: Mild (Tarball), Moderate (Volcanic), Extreme (Infernus, Magma). | 5 | Fire | Heat (up to Moderate), Extreme Heat. Fire Resistance >= 20/40/60%. |
| Desert Heat | Climate that drains 0.3 health per second. Can be deadly in Red Deserts, which drain 6 health and reduce movement speed by 30%. The effect is 25/75% worse when it is bright. | 5 | Fire | Sandstorm, Heat, Fire Resistance >= 20%. Deadly: Extreme Heat, Fire Resistance >= 60%. |
| Heat Wave | Weather that drains 0.4-3.5 health per second. Levels: Normal, Severe, Extreme. Encountered on Desert, Red Desert, Aether World, Strange Sea and Sulphuric planets. | 5 | Fire | Sandstorm (normal), Heat (severe), Extreme Heat (extreme). Fire Resistance >= 30/40/60%. |
| Honey | Reduces movement speed by 40%. | 5 | | Honey |
| Intoxicated | 75/85% movement speed, 65/82% jump height for player. 65/55% speed for monsters. | 5, 60 | | Booze |
| Less HP | Reduces Max Health by 5-15%. | 30 | | |
| Mercury Poison | Eliminates Knockback Resistance. Reduces Fall Damage Resistance by 50%, and Cosmic Resistance by 25%. Encountered on some Gas Giants. | 60 | | Poison Resistance >= 50% **and** Radioactive Resistance >= 25% |
| Poison (Gas) | Drains 1-3 Health per second. Once health drops below 60%, reduces movement speed and jump height by 70-80%. Reduces Power Multiplier by 0.05-0.07 every 4 seconds, down to a minimum of 0.05. Levels: Mild (Gelatinous), Moderate (Toxic Moon), Severe (Strange Sea) and Extreme (randomly on Unknown planets). | 20 | Poison | Poison (up to Severe), Poison Gas, Gas. Poison Resistance >= 20-60% |
| Pressure | Drains 25-40 Health every 4 seconds, increasing the damage by 10-20 each time it is applied. Reduces movement speed by 40-60% and jump height by 90%. The effect is 50-100% as worse at night, and 20% worse when windy. Levels: High (Toxic Giant), Extreme (Proto Giant, Ice Giant), and Deadly (Flame Giant) | 5 | Physical | Pressure; Physical Resistance >= 80-99% |
| Quicksand | Reduces movement speed by 90% and jump height by 85%. | 1 | | |
| Radiation | Climate that reduces 2-5 health per second, and reduces Max Health and Max Energy by 3-7 every 5-3 seconds. The effect is 20% worse when windy. Levels: Mild ([Mutated](https://starbounder.org/Mutated), Jungle, Toxic, Liquid Irradium), Moderate (Irradiated), Extreme (Chromatic). | 20 | Radiation | Radiation (up to Extreme); Extreme Radiation, Radiation Resistance >= 20/40/60% |
| Radiation Burn | Reduces Physical Resistance by 10/20% per second until it reaches zero, when it begins to reduce health by 2/3% per second. Levels: Normal, Extreme. | 7 | | Radiation; Radiation Resistance >= 40% |
| Shadow Taint | Drains health, energy and hunger proportionally to the player's maximum health and inversely proportional to the light level. Disabled if the light level is over 70, it is daytime and the player is on the surface. | 30 | | Shadow |
| Sticky Webs | Reduces movement speed by 90% on ground, 70% during jump | 0.3 | | Race-specific |
| Sulphuric Acid | Applies corrosive damage over time | 3 | Physical | Physical Resistance >= 90%, Sulphuric Acid |
| Unbreachable Darkness | Shrouds the scene in darkness, ignoring light sources. Encountered on Dark Atropus, Lightless, Dark Ice Waste and the particularly dark Shadow Moon worlds. | 60 | | Darkness |

- Electrified: Your body is currently conducting electricity and will sustain damage from other nearby Electrified sources.
- Helium: Usually encountered on Moons; Helium affects you much like Low Gravity, allowing higher, slower jumping.
- High Gravity: An increase in gravity draws you quicker towards the planet core; jumping is reduced, and is much quicker.
- Low Gravity: A decrease in gravity slows your descent towards the planet core; jumping is higher, and much slower.
- Melting: You are in Lava and are melting! You will take rising fire damage until you leave the Lava. (Swaps to Burning after leaving Lava.)
- Oil (Slow): You are covered in Oil; the slippery, oily substance makes it harder for you to move and jump.
- Pus: 50% poison resistance penalty, 100% mental resistance penalty; resisted with Physical resistance.
- Sandstorm: A raging sandstorm slows your movements and reduces your jump height.
- Slime: You are covered in Slime; you are unable to jump very high, or move very fast until you leave the source of the Slime.
- Sticky Slime: You are standing on Slime, which has covered your body and has temporarily made your impact with other objects more bouncy.

## Resistances and Immunities
These status effects grant resistance to a particular damage type and/or grant immunity to a particular status. An immunity status effect immediately removes the effect(s) to which it confers immunity. Even when an effect grants immunity, the resistance may still be useful, because some negative effects respect resistance but not immunity. For example, the Antidote effect below helps grant immunity to Bio-Ooze through its 10% Poison resistance, while Antidote's Poison status immunity is not effective against Bio-Ooze.

When there is a range of resistance in the table below, the sources are listed in increasing order of intensity.

| Effect | Resistance | Immune to Status | Default Duration | Sources |
| --- | --- | --- | --- | --- |
| Antidote | 10% Poison | Poison | 90 | Immunity Field (augment), Gaze Lemon, Crystal Plant, Spongeweed Slice (240s) |
| Caliginous Gas | | Caliginous Gas | 120 | Umbral Stalk, Elder Crown |
| Cosmic Resistance | 10-30% Cosmic | | 120 | Cosmic Barrier (augment), Cosmic Resist I (augment), Corvexxor (30s), Jikjik Tofu (300s), Cosmitea (60s), Aether Soda, Aetherade, Zathi Node (180s), Cosmic Cola (300s), Mythical Honey Jar (300s) |
| Darkness Immunity | | Unbreachable Darkness | 180 | Darkness Shield (augment), Aether Donut (90s), Darklight Blossom (90s) |
| Electric Resistance | 0-30% Electric | Shocked | 120 | Electric Barrier (augment), Honeysilk Bandage (2s), [Medical Kit](https://starbounder.org/Medical_Kit) and upgrades (2s), Grilled Sneeze, Wubstem, Titanium Honeycomb (60s), Mire Urchin, Kirhosi Hacker Contract (300s) |
| Fire Resistance | 0-40% Fire | Burning, Napalm | 120 | Fire Barrier (augment), Honeysilk Bandage (2s), [Medical Kit](https://starbounder.org/Medical_Kit) and upgrades (2s), Quellstem Bud (60s), Hunter Contract (280s), [Burn Resistance Spray](https://starbounder.org/Burn_Resistance_Spray) (300s), Blam, Sliced Kadavan Cactus, Volcanic Honeycomb (60s), Volcanologist Contract (900s) |
| Honey Immunity | | Honey | 300 | Honeyboon Stim |
| Ice Resistance | 0-30% Ice | Frozen | 120 | Ice Barrier (augment), Honeysilk Bandage (2s), [Medical Kit](https://starbounder.org/Medical_Kit) and upgrades (2s), Blue Melon (60s), Mire Urchin, Butter on a Stick, Thelusian Fire Wine (30s), Code Zerchesium (30s), Talon Sprout, Arctic Contract (300s) |
| Physical & Knockback Resistance | 10-30% Physical | | 120 | Thelusian Fire Wine (30s), Blood Root, Teratomato |
| Poison Resistance | 0-30% Poison | Poison | 120 | Poison Shield (augment), Poison Barrier (augment), Honeysilk Bandage (2s), [Medical Kit](https://starbounder.org/Medical_Kit) and upgrades (2s), Ita Flower Head (60s), [Poison Antidote](https://starbounder.org/Poison_Antidote) (300s), Bluelotl Jelly, Nyani String, Diodia Hybrid Fruit, Cultist Contract (300s), Assassin Contract (300s) |
| Pressure Immune | | Pressure | 300 | Plasma Light Pack (augment), Lumivine (120s), and the flying vehicles Sentinel, and Gryphon and Roc. |
| Radiation Resistance | 10-30% Radiation | Radiation Burn | 120 | Garp Berry, Pasaka Bulb, Radioactive Barrier (augment), Biohazard Contract (900s) |
| Shadow Immunity | | Shadow Taint, Caliginous Gas | 180 | Shadow Shield (augment), Shrouded Honeycomb (60s), Shadow Spirits (60s), Aether Donut (90s), Elder Cookie (150s), Herrod Bush Gem and the Poseidon and Triton submarines |
| Shadow Resistance | 10-30% Shadow | Shadow Taint | 120 | Shadow Barrier (augment), Dunce Cookie, Lactarius Indigo Mushroom, Elder Hook (0.9s), Magical Girl Contract (300s), Harlequin Honeycomb (60s), Precursor Drone Control Chip (300s) |
| X-Grav | | High Gravity | 120 | Gemglow, Xax Wing (180s) |
| X-Gas | | Gas (Helium-3, Caliginous Gas, Metallic Hydrogen, Poison Gas) | 120 | Immunity Field (augment), Gas Specialist Contract (300s) |

The Immunization enhancer grants virtually all of the above immunities until death, and other enhancers provide specific resistances. The Shoggoth Armor (not listed above) also confers immunity to many effects. The Atmospheric Regulator provides immunity to many negative environmental effects within its effective radius.

There are many other ways, besides the status effects listed above, to obtain resistance and immunity, including level-dependent armor piece bonuses, armor set bonuses, shield bonuses, and race-specific bonuses.

## Abilities