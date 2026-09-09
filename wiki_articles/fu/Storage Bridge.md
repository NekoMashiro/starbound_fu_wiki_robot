# [FU] Storage Bridge

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/Storage_Bridge

---

**Storage Bridge** adds / to the nearby chest (or any other container), allowing you to wire it to the Item Transference Device (ITD).

Stations like Extraction Lab and some storage objects like Wall Storage don't need this, because they already have their own Input/Output. Don't add a storage bridge to an object that already has I/O nodes; instead wire them directly to the ITD. 

## Troubleshooting
If you have two chests very close to each other, you may run into problem where Storage Bridge uses a chest other than the chest you wanted to use. To solve this issue, craft an Object Data Sensor tool, which will show you the optimal points for placing Storage Bridges. The way it works, a Storage Bridge will always select a chest with the closest Placement Point.