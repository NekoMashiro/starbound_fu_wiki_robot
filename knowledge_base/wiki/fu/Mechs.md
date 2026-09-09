# [FU] Mechs

**来源**: Frackin' Universe Wiki | **分类**: Mechanics | **链接**: https://frackinuniverse.miraheze.org/wiki/Mechs

---

Mechs have new features in FU distinct from the vanilla game (but very close to the XS Mechs Modular Edition mod, which the code is based on). They are as follows:

- **Sprinting** - Double tapping with mechs increases running speed while held. (see Mass)

- **Flight**- Double-tapping Up will enable Flight Mode.

- **Rebalanced levelled damage** :(mechs are viable in both space and on planetary biomes due to retiering to suit vanilla progression)

## Mass
Mech mass is determined by the mass of each part (arms, head, legs, boosters, body) of the vehicle. Mass can influence a great number of things.

*The base calculation for mass is:*

 Base Mass = Arm + Arm + Legs + Body + Boosters

 Modified Mass = Base Mass * Body Protection rating / Body Energy

### Effects of Mass on Mechs
- **Mass greater than 8** - Mechs affect tiles when walked on, causing impact damage (slight). The higher your mass, the more effect your mass will have on tiles. Your velocity at impact is the key factor in deciding the total effect. Your mass also directly affects the radius of your impact.
Actual damage maxes out at 300 (divided by 2... 150 for each foot) and can be applied simply by walking over creatures as well as jumping on them. Maximum explosive force is 55.
- **Mass greater than 15** - Mech mass at 15 or higher begins to reduce booster and leg speed and control slightly. Mechs over 15 tonnes will take increased damage from long falls.
- **Mass greater than 20** - Mech mass of 20 or higher affects speed and booster control more seriously

### Ablative Armor
Heavier mechs with good protection (rating of 4 or higher) gain a chance to shrug off smaller damage increments completely due to their natural toughness.

 **self.massProtection** = self.parts.body.stats.protection * ((self.parts.body.stats.mechMass)/10)

*the above result is the "threshold" you can defend against. anything higher than that cannot be blocked.*

## Fuel
- See **Acceptable Mech Fuel**

### Introduction
Under *Frackin' Universe*, Mechs now require fuel to function. Failing to do so will render your Mech unresponsive.

### Fuelling your mech
With the new Mech overhaul introduced in February 2019, heavier Mech bodies have high consumption rates, while lighter ones may require less (see notes on **Mass** above). Mechs also receive a new interface, with two bars replacing the old single health/energy bar of the vanilla version of Starbound:
- The **top** red bar represents Mech **health**.
- The **lower **bar represents **your fuel**. This **color of this bar changes **depending on** current fuel type**.
**Should your Mech be low on fuel, a beeping sound will instantly play** to remind you to refuel. Upon running out of fuel, your Mech will become immobile and the bars that normally appear over it will disappear, but nothing else can be done until it receives fuel. An unfuelled Mech will not move nor use its weapons in combat. It is still possible, however, to break your Mech, or use whatever life support systems it has available, ie, keep you from drowning or freezing to death.

### Tricorder (Formerly Mech Tablet)
To fuel your Mech, **you must first have a** Personal Tricorder. This functions as a quick way of assembling and reviewing your Mech (Left-Click - Fuel Icon), as well as refuelling it. 

Once you have opened up your interface, it is simply a matter of **selecting and dragging your chosen fuel type** from your inventory into the drop-shaped icon as shown on the right side of your Mech fuel tank interface, and then **clicking the green button** marked "FUEL" at the bottom right. 

Your Mech will accept various kinds of items as fuel, from conventional Ship fuel (isotopes, biofuels, Erchius) all the way to Oil and even Power Cores. **Choose your fuel with care**, however, for different fuel types will provide different performance rates. You cannot refuel your Mech with a fuel type different from what was previously used so long as its fuel tanks are not empty, and must empty them completely before you can change the fuel type in use.

Should you disassemble your Mech or have it destroyed in combat, you will still retain any fuel that was previously there. However, different Mech bodies have different capacities, so changing to a Mech body with a lower fuel capacity will cause you to lose any fuel you had in excess of your Mech's latest capacity.

## See also
- Acceptable Mech Fuel
- List of mech weapons