# [FU] Neuro-Psionic Generator

**来源**: Frackin' Universe Wiki | **分类**: Power Generator, Power, Imported | **链接**: https://frackinuniverse.miraheze.org/wiki/Neuro-Psionic_Generator

---

**Neuro-Psionic Generator** is a generator that uses brains as fuel to generate up to 60W of power. It can be fueled with brains (which are consumed fairly quickly), or brains in jars (much more efficient), or PSI Energy (most efficient, lasts for a very long time).

## Mechanics
The Neuro-Psionics Generator requires time to heat up to full power when first fueled, but also takes time to cool down to no power when it runs out of fuel. Specifically for each second that the generator is fueled, the heat *(a variable that is always between 0% and 100%)* increases by 5% and for each second that the generator is without fuel, the heat decreases by 5%. The output of the Neuro-Psionics Generator is related to the threshold it has to hit as follows:

| Heat Threshold (%) | Time to Hit Threshold (Sec) | Power Output (W) |
| --- | --- | --- |
| 10 | 2 | 6 |
| 30 | 6 | 12 |
| 50 | 10 | 20 |
| 70 | 14 | 40 |
| 90 | 18 | 60 |

## Source
https://github.com/sayterdarkwynd/FrackinUniverse/tree/master/objects/power/braingenerator