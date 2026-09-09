# [FU] Colony Core

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/Colony_Core

---

**Colony Core** will automatically collect the rent from Tenants. It looks for tenants who have their Colony Deed Mark II within 128 blocks of the Colony Core. Collected pixels are placed into a 1-slot storage inside the Colony Core.

- If you scan the Colony Core, it will show information on the current number of tenants (that are within its range) and their happiness (greatly affects their rent).
- Only one Colony Core can exist per town. If you add a second one, it won't do anything.

## Happiness and rent
Colony Core generates the following amount of pixels every 150 seconds: NumberOfTenants * Happiness. For example, with 15 tenants and 20 happiness it will generate 15*20 = 300 pixels. Base happiness is 10, but some buildings (such as Recycling Center or Hidden Camera Network) will increase/decrease happiness.

Maximum happiness (with all happiness-increasing buildings and no happiness-reducing buildings) is **68** happiness = 10 (base) + 1 (Recycling Center) + 2 (Sewage Storage) + 2 (Community Garden) + 10 (Psionic Harvester) + 6 (Community Library) + 10 (Computer Lab) + 12 (Subliminal Messaging) + 15 (FTL Internet Dish). Having all buildings results in **52** happiness = 68 - 1 (Blood Drive) - 5 (Hidden Camera Network) - 10 (Drug Diffuser).

Happiness doesn't affect the number of items that are produced by buildings like Blood Drive. Their productivity depends only on the number of tenants (and, for Community Garden, on liquid and fertilizer).

## Colony on another planet
Colony Core doesn't need a Watcher. Even if you were on another planet (it's not possible for machinery to run when you are offworld), Colony Core will still give you the rent for the time you weren't there. However, any producing buildings like Blood Drive are machinery and won't produce items when unloaded.