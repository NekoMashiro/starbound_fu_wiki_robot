# [FU] Power Progression

**来源**: Frackin' Universe Wiki | **分类**: Tutorials, Power | **链接**: https://frackinuniverse.miraheze.org/wiki/Power_Progression

---

This guide is designed to give players a view at how their power production will start in a new game, develop through various level of exploration and reasearch, and point out some basic strategies. This guide assumes you already have the required Electronics Center as well as either the Mechanic's Wrench or the wiring unlocked on your Matter Manipulator to start.
## The Alternator Generator
Your first step into producing power is the Alternator Generator. This is the simplest of power producers. It requires iron bars, copper bars, and copper wire, all of which can be made from your Primitive Furnace and Machining Table from materials on your starting planet. You learn how to make it at the same time you learn how to make your Electronics Center.

The Alternator can produce 4W of energy. This is enough to run a Sifter or an Iron Centrifuge. These devices require 2W and 4W, respectively. Even when using these, some of your power may go to waste as it's not used when the machines are inactive or if it doesn't need to full amount. You can save this energy by building a battery.

### Burn Fuel
The alternator's function is simple. Insert fuel and output power. The most common fuels you'll have available at this point are Wooden Logs and Coal. One piece of either will fire the generator for 7 seconds. Coal can be mined from the ground and Logs can be harvested by felling trees. You can replant the trees' saplings to keep a steady supply of wood nearby. Fuel that is burned is consumed immediately. If you put a wooden log in, it will be consumed, but the alternator will run for 7 seconds.

This behavior can be seen in later generators and reactors.
### Warm Up and Cool Down
The alternator produces 4W of power, but it doesn't do this right away. It takes about 18 seconds for the alternator to reach full power. It will still produce power before then, gradually working up to the full 4W. Likewise, it takes time for the alternator to cool down, 20 seconds to be exact. During this time, with no more fuel, it will still produce power, but that amount will diminish until it has cooled down enough.

This behavior can be seen in later generators and reactors.
### Wiring Nodes
The Alternator has 3 wiring nodes. The first is for a power switch and will be identified by examining the generator. This will allow you to hook up items like an Iron Lever to turn on and off the Alternator (and other generators and reactors) without having to always open up the generator to remove fuel. While this and other generators or reactors are turned off, the fuel inside them will not be consumed. Then, whenever you need to run it, you can turn the generator back on easily.

The other nodes on this are for use with the Item Network. This is a much more complex topic and is better left for other guides that make use of them. 

## The Simple Battery
The first battery you'll have available is the Simple Battery. This has the potential of holding up to 350J of energy. The Lead and Sulphur you'll need can be found on your starting planet, though they may not be as common as copper and iron. The sulphur is used to create the needed Sulphuric Acid by placing it in a Hand Mill. You learn how to make it at the same time you learn how to make your Electronics Center. You can duplicate Sulphuric Acid by mixing it with water.

At this point we should clarify the difference between Watts (W) and Joules (J). When something is producing or consuming Watts, it's doing it at a rate of Joules per second. The Alternator Generator produces 4W, or 4 J/s. The Sifter consumes 2 W, or 2 J/s.

The way the Simple Battery (and all other batteries) work is when a Watt exists that isn't consumed, it stores that excess as Joules. Then, when other devices need to consume that energy, the batteries will release those joules each second the device needs it.

Assuming we have just the alternator and a simple battery, the alternator can fully charge the battery after 88 seconds. If we turn off the generator and run the sifter, it will drain the battery dry after 175 seconds.

From this, we can devise a simple system that will allow you to generate power, store it, then consume it from the batteries. The simplest of which looks like:

Generator -> Battery -> Device
### Wiring Nodes
The node is for incoming power. Connect the generator to it. There are two Blue nodes, it doesn't matter which one of them you use.

The nodes are for power output. They are described as Partial Power (left) and Full Power (right). Both of them dispense power regardless of how full the battery is, but in addition to dispensing power, they also send a logical signal (which you can use for logic automation), which informs about the current state of the battery.
> If the battery is 100% full, then Full Power node sends logical "On" signal, otherwise it sends "Off".
> If the battery is less than 1% full, then Partial Power node sends logical "Off" signal, otherwise it sends "On".

The signals can be used to activate other wiring devices, such as turning on a generator if a battery gets too low or sounding an alarm.

## The Hydraulic Dynamo
You may soon find your needs for power are greater than what you're currently producing. For this, you can create the Hydraulic Dynamo. This can be made with materials all available on your starting planet, though it will require a lot of them, as well as researching the recipe in Electronics.

The Hydraulic Generator has 4 slots in it: 3 fuel slots on top and 1 coolant slot on the bottom. The fuel slots can take a variety of fuels, but we'll be looking at Core Fragments, Lava, and Volatile Powder as the others are not readily available. You can get all of these closer to the planet's core. Core Fragments can be mined from the stone and broken down into Volatile powder. If you can make it to the very core, there is an infinite amount of lava that you can drain.
### Decay
To start, you can place any of the fuels in the top slots. While the Alternator would burn fuel at a steady rate, the Dynamo will consume fuel as it decays. What this mean is a unit of fuel will be consumed randomly. Each fuel has a different decay rate, meaning that on average they will last for a certain amount of seconds. Lava has a decay rate of 15, meaning it should last around 15 seconds. Core Fragments and Volatile Powder have a decay rate of 40.

This behavior can be seen in later generators and reactors.
### Multiple Fuel Slots
In addition, each fuel you use supplies a different amount of power. Lava and Core Fragments produce 5W and Volatile Powder produces 7W. While this may not seem like much more than an alternator, the Dynamo's power comes from multiple fuel slots. By adding fuel to all three slots, you can produce energy from each slot. If you put Lava in all 3 slots, you can produce 15W with your Dynamo.

This behavior can be seen in later generators and reactors.
### Coolant
Finally, the coolant slot needs Water or Salt Water to operate. You'll likely only have easy access to Water at this point, either from a Well or draining lakes that collect rainwater. Whenever the Dynamo consumes a unit of fuel, whichever that may be, it will also consume a unit of water. Without any water, the Dynamo will not operate.

A similar behavior can be seen in Fusion Reactors which will be discussed down the line.

## Time to leave the planet
Without even leaving our beginning planet, we can create the Alternator Generator, the Simple Battery, and the Hydraulic Dynamo. Once we leave our planet (but not our system), a little more opens up to us. The next step comes once we have access to Titanium. If you're using BYOS, you'll need Tungsten next in order to leave your beginning star unless it happened to have planets that have Titanium. If you use the Vanilla ship build system, you'll need to meet someone before you can move to another planet, let alone another star.

## Titanium and More Power
Once you can get access to Titanium, new power options become available to us, including renewable energy sources.
### A Note On Batteries
Batteries with higher capacities will become available as you explore and research. However, as these batteries function the same, they will not be delved into. It should be noted that older batteries are never useless. Consider keeping them around for more *total* capacity, unless you really need the room.

Also, as you build your bank of batteries, you may think to wire them to one another in a chain, either from your generators to the first battery or your last battery to your devices. This will not work. Batteries ignore the connections to each other.

If you wish to help keep things neater, you can use a Power Relay or [Service Panel](https://starbounder.org/Service_Panel) to create single connection points to wire between your batteries. Service Panels have the added benefit of being made at a Pixel Printer once scanned.

## The Combustion Generator
The Combustion Generator operates like the Alternator Generator. It burns fuel and has a warm up/cool down. It produces more power at 12W, and has much greater list of fuels it can burn, including Biofuel Canisters made at your Alchemy Lab or even Hydrogen that you obtained from processing different materials.

## The Wind Turbine
The Wind Turbine is unique in generating power from wind. This can be a good way to keeping banks of batteries topped up for use and can generate power from even light breezes. Between this, solar energy, and a generator for larger productions or extractions, you should be able to meet most of your power needs.

However, this isn't viable on all planets as some do not have wind at all. Also, the wind can vary throughout the day, generating different amounts of power. The best way to determine how viable wind turbines are for power is to use your tricorder's GPS feature to determine frequency of wind-related weather. Planets with above 70% chance of 'clear' are not ideal for wind turbines. Planets with frequent rain, wind, thunderstorms, etc. Are very good for wind power.
Your ship will not produce wind at all, so don't even bother.

## Solar Power
There are 3 solar power generators: Solar Panels, Solar Arrays, and Solar Towers. As expected, these generate power based on sunlight and require no fuel. In keeping with the renewable line of power generation, each higher tier version requires recycling the old ones into new generators. 2 Solar Panels are needed to make a Solar Array and 2 Solar Arrays are need to make a Solar tower. These items work different based on whether they are used on a planet or on your ship.
### On Planet
These will generate power during the day. The lights on them will start out red at sunrise, slowly turning to green when they'll be at full power. They'll start to generate power just like warming up an Alternator Generator. When nighttime approaches, they will likewise cool down. The amount of power they generate is usually in excess of the power rating listed when the solar generator is examined. Keep in mind these will not operate underground. Also, if they're placed in liquid, their capabilities are reduced.
### On Ship
When placed on a ship, they are limited to the amount listed when the solar generator is examined and cannot go any higher. Their lights will always be yellow. While less efficient, they are a constant source of power.

## Are you mad?
By this point, you may have been delving into the Metaphysics tree and have access to the Nocturn Array and the Neuro-Psionic Generator.

The Nocturn Array functions similarly to the Solar Array, except it requires darkness. This doesn't mean an absence of sunlight, it means *no light*. If there are any objects nearby that emit light, it will weaken the output of the array. This makes it difficult to place, even deep underground, as many devices that use power also produce light. It is also difficult to make, requiring some difficult-to-come-by ingredients. Still, in absolute darkness, it will produce a constant 10W.

The Neuro-Psionic Generator acts as generator that burns fuel and has a warm up/cool down. However, instead of wood or biofuel, it burns brains. While you may have a steady supply of Fresh Brains from the Autopsy Table and think to feed it a Brain in a Jar or two, you'd be more efficient in converting an Inferior Brain into Psi-1 Energy. Since it just burns the brains, the quality only determines the length of time the brains last. When fully warmed up, the Neuro-Psionic Generator outputs 60W of power.

## The S Is Silent
After a while, you will gather materials that, while they can be used as ship fuel, can also make excellent power sources. Plutonium Rods are just the tip of the iceberg once you start diving into the Nuclear Power branch of Electronics Research. But first, you must ask yourself a question:

Do you even need to?

Given a base on a planet, Solar and Wind power can keep batteries topped up for use in common processing. Rock Smashers, Power Sifters, and even Blast Furnaces do require heftier amounts of power, but that power can be drained from batteries which can be recharged from cheaper options. The options you're about to get into will produce much more power than even empty batteries can soak up.

So do you need that much power?

The answer to this comes in the form of the Atmospheric Filter, Atmospheric Regulator, and other devices that require large amounts of energy to continuously run. Taking the Atmospheric Filter as an example of 100W, it would take 5 Solar Towers to keep it running full time with only 20W leftover to recharge any batteries. When night falls, those batteries will drain at 5 times the rate that it took to fill them.

If you don't plan on using these tools to settle an inhospitable world and build bases in even the most unforgiving of climates, then you should be good. A few Solar Towers and Wind turbines charging a bank of batteries should keep you good for a long time. Have fun and hopefully this helped you plan a great base.

For the rest of you who want to stick a finger in the eye of a Nightmare Atropus planet, read on.
## The Fission Reactor
The Fission Reactor is the first step down the nuclear path. Like the Hydraulic Dynamo, it uses fuel that will decay and has 4 fuel slots. Instead of hot temperature fuel like Lava, it uses hot radioactive fuels like Plutonium Rods. Each type of fuel it can use produces variable amounts of power and decays at different rates. It also has 2 additional slots for waste products.

One of the bigger draws (and drawbacks) is the Toxic Waste and Tritium Rods it can produce. The Toxic Waste can be used to produce more Uranium Ore for power. The Tritium Rods have their own uses. They can be used for power in a pinch, but this reactor isn't the best way to use it. However, these byproducts come at a cost. The Fission Reactor will produce radiation. As the Toxic Waste and Tritium Rods build up, it deals more and more radiation damage. This can damage you, your ship crew, your livestock, or tenants. For this reason, it is either recommended to isolate the reactor from others or clean it out periodically.
### Calculating Total Joules
Even though the fuel decays, you can calculate how much power it will produce. Take a Thorium Rod, for example. It produces 50W for an average of 90 seconds. The total Joules it produces is 4500J. That's enough to fill an Industrial Battery with power left over. As you create more and more power, it is useful to understand just how much power can be created and consequently stored in the batteries you have access to. Using the Partial and Full Power nodes on batteries, it is possible to design a system where the reactor runs until your bank of batteries are full and then turn itself off.

## The Small and Large Fusion Reactors
The Small Fusion Reactor and Large Fusion Reactor also decay their fuel and have 4 slots for fuel. Instead of radioactive fuels, it uses Hydrogen and Hydrogen Isotopes. They also have a slot for Toxic Waste to build up and can cause radiation damage.

The major difference is the need for a coolant. As these reactors run, they generate heat. If not cooled down, they can eventually explode, damaging others and your base, before shutting down for 10 seconds. You can use different coolants to drain the heat from it. While water is easy enough to procure, you can also use Liquid Nitrogen. If you have access to a Nitrogen Sea, you have all the coolant you'll ever need.

The main difference between the 2 fusion reactors is the large one will produce more power. In fact, one Ultronium Rod in each fuel slot can produce about 420KJ of energy, enough to fill 23 Ultra Batteries with extra to spare! That would be enough to power the Atmospheric Filter for 70 minutes.

Because of the amount of power generated is so large, it helps to think of it in more compact terms. For comparison's sake, let's abbreviate the amount of power output to how many Full Ultra Batteries (rounded down) it can produce, or FUBs for short. To give a comparison, let's compare how many FUBs 4 Ultronium Rods can produce in each of our reactors so far:
- Fission Reactor: 6 FUBs
- Small Fusion Reactor: 14 FUBs
- Large Fusion Reactor: 23 FUBs

And that's nothing.

## The Quantum Reactor
The Quantum Reactor burns fuel and has a warm up/cool down much like the Alternator Generator. Like it's nuclear brethren, the power and amount of time the fuel lasts depends on the fuel. However, it produces no waste, does not emit radiation, and does not require coolant. It also has a greatly expanded list of fuels it can use.

What's more, it can produce even more power from these fuels. Given our measure of FUBs, how much does the Quantum Reactor produce with 4 Ultronium Rods? 57 FUBs, more than double what the best fusion reactor can do. However, there's a catch to this comparison. Ultronium Rods are not the best kind of fuel it can use.

May I introduce you to Liquid Deuterium. One drop of this fuel in a quantum reactor produces 20 FUBs. This is close to how many FUBs a 4 Ultronium Rod Large Fusion Reactor produces.

But for some people, that's not enough. They need more.

## Ancient meets Eldritch
The Precursor Reactor is a rare find in a Precursor microdungeon and is not found in chests. They have to be found as an object and broken down with a Matter Manipulator or other tool. You don't have to break the Reactor itself, you can mine the floor under it.

However, finding it is only half the equation. You'll also need to plumb the depths of Madness and learn how to make a Neutronium Rod and an Anti-Neutronium Rod. One you have the reactor set and the rods in place, you have access to amazing power generation.

First, let's again compare it using 4 Ultronium Rods. Doing this gives us a rating of 107 FUBs, almost double the Quantum Reactor's 4 Ultronium Rods. And again, that's not the best fuel it can use. The Precursor Reactor can use a Dimensional Cell for fuel, which is a rare drop from precursor enemies and in chests. Just one of these rates at 56 FUBs, about matching the Quantum Reactor's 4 Ultronium Rods.

## Conclusion
From the humble Alternator Generator to the dominating Precursor Reactor, you can get a pretty clear picture how your power needs can be met through various stages of play. Hopefully this guide will let you plan just how you want to face the universe and tackle it, whether you keep to your ship, make a small base for some processing and crops, or being an Overlord of vile planets that want you and yours dead. Have fun!