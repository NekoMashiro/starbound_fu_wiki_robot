# [FU] Diet

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/Diet

---

assigns each food to a food group, and each race has a specific diet, which may provide bonuses or penalties depending on the food group. The Feed-Munity Chip augment removes dietary restrictions.

## Food Group Hierarchy
The food groups are organized into a hierarchy to simplify diet definitions.

- Organic
 - Plant
 - Fruit
 - Meat Plant (also safely consumed by carnivores)
 - Meat
 - Cooked Meat
 - Raw Meat
 - Fish
 - Dairy
 - Egg
 - High Glucose
- Inorganic
 - Hot Rock (none yet exist)
 - Cold Rock (none yet exist)
 - Radioactive Rock
- Robot Plant

## Diets
Each diet has a group of foods that can be consumed without penalty. A subset of those foods confers a bonus, and a disjoint subset may be excluded from the consumable foods. Any food that is not consumable within a diet confers a penalty. The specific bonuses and penalties depend on the food group. When a bonus group belongs to an excluded group, the bonus takes precedence.

| Diet | Allowed (no penalty) | Bonus | Excluded (penalty) |
| --- | --- | --- | --- |
| Carnivore | Organic | Raw Meat, Fish | Plant |
| Omnivore | Organic | | Raw Meat |
| Raw Omnivore | Organic | Raw Meat | |
| Piscivore | Organic | Fish | Plant, Meat |
| Herbivore | Organic | Plant | Meat, Egg |
| Robot | Robot Plant | Robot Plant | |
| Lithivore | Rock | Rock | |
| Entity | Organic, Inorganic, Robot Plant | | |

## Status Effects
Bonuses and penalties depend on the food group, following the hierarchy, so the next parent effect applies if a group has no effect of its own. All effects last for 120 seconds, except the radioactive rock effects last for 200 seconds. All penalties include poisoning that drains 1% of Max Heath every 2 seconds.

| Food Group | Bonus | Penalty |
| --- | --- | --- |
| Cooked Meat | +15% Max Health, +15% Max Energy, +1 Protection | -10% Max Health, -25% Protection, -10% Speed |
| Dairy | | -10% Max Health, -10% Max Energy, -10% Speed |
| Egg | | -10% Max Health, 2.5x Energy Regeneration Rate, -10% Speed |
| Fish | +10% Max Health, +10% Max Energy, +2 Protection | -10% Max Health, -10% Max Breath, -20% Speed |
| High Glucose | +10% Speed | |
| Meat Plant | | -10% Max Health, -20% Protection, -10% Speed |
| Plant | +10% Max Health, +10% Max Energy, +2 Protection | -15% Max Energy, 1.5x Energy Block Time, -10% Speed |
| Radioactive Rock | +14% Max Health, +14% Max Energy, +50% Health Regeneration | -25% Max Health, -100% Heath Regeneration |
| Raw Meat | +10% Max Health, +10% Max Energy, +2 Protection | -10% Max Health, 2x Energy Block Time, -10% Speed |
| Robot Plant | +10% Max Health, +10% Max Energy, -15% Fall Damage | -15% Max Health, -15% Max Energy, 2x Energy Regeneration Rate, -20% Speed |