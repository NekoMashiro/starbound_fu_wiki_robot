# [FU] Fd:Hen

**来源**: Frackin' Universe Wiki | **分类**: Farm Beasts, Imported | **链接**: https://frackinuniverse.miraheze.org/wiki/Fd:Hen

---

There are some changes made to Hens in FU. See the [Chicken](https://starbounder.org/Chicken) page on Starbounder for info from the vanilla game. They are omnivores and need to be fed from a trough in order to produce.

Hen eggs take 400s to hatch in the Incubator or 9000s without. A primed egg takes 200s to hatch in the Incubator. A regular egg (the kind you harvest from the chickens and eat or cook with) has a 50% chance to hatch into a hen baby in 400s in the Incubator.

## Hen baby:
- Evolve time: 1200s (evolves quicker if fed in trough)
- Max health: 20. Regenerates health
- Hunger time: 5 min.
- Capturable & relocatable.
- Drops if killed:  50% Bone, 50% Raw Poultry, 1% Ancient Essence.
Hen babies have chances to spawn in the wild in Field of Corn and Primeval Forest biomes.

**Monster ID:** fuhenbaby

## Harvest chances:
- 95% Egg
- 5% Research x 10

## Stats:
- Drops if killed:  50% Bone, 50% Raw Poultry, 1% Ancient Essence. 
- Has a 10% chance to lay an egg once an hour, or every 40 minutes if happy.
- Diet: Omnivore. Hunger time: 20 min.
- Max Health: 60. Regenerates health.
- Harvest time: every 500-900 sec depending on happiness. Will not produce at all if starving.
- Capturable & relocatable. The captured monster type is a Hen baby.
**Monster ID:** fuhen

## Bugs
It can occur that the Hen won't mature properly and will stay a baby regardless of the above mentioned evolvetime. To counter this bug you have to give yourself admin rights with the /admin command and use the command /timewarp and put in the specific evolvetime.

### Sources:
- [objects/farmables/eggs/henegg/henegg.object.patch](https://github.com/sayterdarkwynd/FrackinUniverse/blob/c9b5864b911f721c70765431c9f9b9cbf324b1f9/objects/farmables/eggs/henegg/henegg.object.patch)
- [monsters/farming/henbaby/fuhenbaby.monstertype](https://github.com/sayterdarkwynd/FrackinUniverse/blob/a6dd433910caea9015243fe4a5b407488c572425/monsters/farming/henbaby/fuhenbaby.monstertype)
- [monsters/farming/hen/fuhen.monstertype](https://github.com/sayterdarkwynd/FrackinUniverse/blob/a6dd433910caea9015243fe4a5b407488c572425/monsters/farming/hen/fuhen.monstertype)
- [treasure/monsterharvest.treasurepools.patch](https://github.com/sayterdarkwynd/FrackinUniverse/blob/5df7bda851e9c6d95d2a80d85bbce6dc1d0b25fb/treasure/monsterharvest.treasurepools.patch)

> Category:Vanilla