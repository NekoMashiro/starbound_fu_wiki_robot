# [FU] Protection

**来源**: Frackin' Universe Wiki | **分类**: Mechanics | **链接**: https://frackinuniverse.miraheze.org/wiki/Protection

---

> Question: By how much does Protection (Defense) stat on armors, etc. reduce incoming damage?
> Answer : See https://github.com/sayterdarkwynd/FrackinUniverse/blob/master/leveling/protection.2functions.patch
> How to read it:

 [0, [0, 1, 1000000]], <-- at 0 protection you take 100% of incoming damage

 [30, [0, 1, 547157]], <-- at 30 protection you take 54.7% damage

 [150, [0, 1, 49040]], <-- at 150 protection you take 4.9% damage

Maximum protection is 200 (if it's greater, then it counts as 200).