# [FU] Default Unlock Checker

**来源**: Frackin' Universe Wiki | **分类**: Information for developers | **链接**: https://frackinuniverse.miraheze.org/wiki/Default_Unlock_Checker

---

**Default Unlock Checker** is a troubleshooting tool. It helps determine the cause if you can't find items like Torch, Campfire, etc. in your hand-crafting (C) menu.

When used, it will display an onscreen message showing how many recipes are missing, and print an error report to **Starbound.log** in the form:
 [Info] Default unlocks that are likely causing issues: {"item1", "item2", "item3", "item4"}

## Why are items missing?
This is caused by some third-party mod being written in a way that is incompatible with Frackin' Universe (first of all, look at the page Incompatible for a list of mods which are known to cause problems, both those in the crafting section and elsewhere).

If you simply cannot live without the other mod, you should identify the mod adding the listed item(s) and politely ask their developer to fix it, and link them to this page. You should remove the incompatible mod for the time being, if possible.

## I'm a developer of mod that has this issue, how do I fix this?
Default unlocks should always be added to the *end* of the list, rather than the front, using /-. Doing so looks like this:
[ { "op": "add", "path": "/defaultBlueprints/tier1/-", "value": {"item" : "something"} } ],

When patched incorrectly, the operation looks like this (notice /0 instead of /-):
[ { "op": "add", "path": "/defaultBlueprints/tier1/0", "value": {"item" : "something"} } ],

The second approach makes the order of "defaultBlueprints" unpredictable, thus causing unlocks of Torches, Campfire, etc. to end up in places where other items (those items that now require research and must have their unlocks removed) had their unlocks.

Always patching /- instead of /0 will avoid many potential mod conflicts (not just with the Crafting menu).

## Whose fault is it?
It's about 50/50.

Mods that insert at indexes instead of the end of the list are usually symptomatic of using a JSON patch generator (such as http://chbrown.github.io/rfc6902/) without manual editing of the produced results; this is bad practice. The beginning of the list (or any other position in the list) would ordinarily be safe if Frackin' Universe were not installed, but mods which add default-unlock blueprints anywhere other than the very end of the list are broken by Frackin' Universe's research system. Because Frackin' Universe must target exact indexes to remove default recipes due to the limitations of the patching system, this causes Frackin' Universe to break the list of default crafting recipes when those mods are installed. Unfortunately, the problem can only be corrected by making changes directly to the other mod because it is not possible to make a "patch of a patch", only to change what a patch has already done if the exact changes already made are known -- which, given the wide variety of mod packs, collections, and handmade user setups, is simply not possible.

This problem is easily fixed by other mod authors, and Frackin' Universe is by far the most popular mod for Starbound; ensuring compatibility with it should be a significant consideration of any mod author, even if the modder does not use it. Because it is Frackin' Universe's deliberate removal of default blueprints that makes these other mods incompatible, it is entirely accurate to say that Frackin' Universe is incompatible with those other mods, rather than the other way around. However, although Frackin' Universe is to blame for the incompatibility, it is not possible for FU to correct this problem on its own end.

Please do not badger mod authors to fix the problem: by all means let them know -- they might simply not know! -- but ask politely. Implementing the fix is entirely that mod author's prerogative. Nobody is forcing them to make changes, and neither is anybody forcing you to keep using their mod. Be nice!

Note that it is also possible for any user to fix the problem on their own end if they wish to use an incompatible mod; to do so, they must unpack the mod, make the corrections, and move the unpacked mod to their /Starbound/mods folder. This requires some level of technical competency and modding ability and is not recommended for novice users. Be sure to unsubscribe from the Workshop version of any mod you have unpacked to avoid conflicts. (You'd have to unsubscribe anyway if you didn't fix it!)

To find any other mods which are made incompatible by the research system, you will have to unpack *all* of your mods and then use a utility like Agent Ransack or grep and search for all "player.config.patch" files that contain the regular expression "/defaultBlueprints/tier1/\d+". Any file that appears in the list targets a specific index instead of the end of the list. Since no other mods remove default blueprints that we're aware of, this will be more or less guaranteed to be a mod that inserts a default blueprint at a position that is incompatible with Frackin' Universe's research system.