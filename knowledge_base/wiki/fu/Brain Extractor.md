# [FU] Brain Extractor

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/Brain_Extractor

---

> Removes the brains from still-living hosts. Definitely illegal.

**Brain Extractor** extracts Inferior, Superior, and Perfect brains (at a ratio of roughly 100 to 10 to 1) from defeated enemies. Humanoids have a higher chance of yielding a high-quality brain. After hitting enemy with Brain Extractor you can kill it by any other means and as long as you achieve so within 10 seconds from hit, it will yield brain. When used in Warped Regulator, all enemies within range yield brain when killed regardless on if you have used Brain Extractor on them.

Not all enemies will drop a brain. Gas-based enemies (such as Novakid bandits) will drop Hydrogen and Bag of Farts, and robotic enemies will drop Copper Wire, Silicon Board and Artificial Brain. Some enemies are immune and don't drop anything.

Kevin will eventually challenge you to obtain 50 Superior Brains as a quest for 50 Tungsten Bars and 5,000 Madness points. If successful, he'll congratulate you that you are a murderer.

##### Technical Details
Despite appearing as contact weapon, it is classified as shotgun. It fires projectile [brainburstharvest](https://github.com/sayterdarkwynd/FrackinUniverse/blob/6e8483f974812be0fecf651ef331e34175bc2ecb/projectiles/burst/brainburst.projectile#L5) that inflicts target with effect [deathbombbrainharvest](https://github.com/sayterdarkwynd/FrackinUniverse/blob/6e8483f974812be0fecf651ef331e34175bc2ecb/stats/effects/deathbomb/deathbombbrainharvest.statuseffect#L3). This effect has duration of 10 seconds and lacks any visual effects on enemy. If enemy with this status effect dies before duration expire it will yield brain on death. This allows you to finish enemy with any weapon as long as you do so within 10 seconds time limit. Effect can be inflicted only by primary fire. Primary fire deals bio-weapon damage meanwhile secondary fire deals shadow damage, both having a short reach.

##### Trivia
- (Multiplayer) You cannot extract a brain from a player using this weapon, no matter if they're directly killed through PvP or indirectly through other enemies or hazards such as Sulphuric Acid. The reason for it is that their death drops are directly tied to character difficulty settings and not to loot tables.