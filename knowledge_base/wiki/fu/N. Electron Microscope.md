# [FU] N. Electron Microscope

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/N._Electron_Microscope

---

**N. Electron Microscope** is the same as Electron Microscope with a Storage Bridge near it. It can also inform other machinery (e.g. Alarm) of what is the microscope doing right now (see below).
> == Inputs and outputs ==

Scan your microscope to see which input/output is what.

Aside from the and for Item Network, N. Electron Microscope has 3 additional that send a logical On/Off signal:

> Production Status : Sends ON signal if the microscope is scanning something right now.
> Input Fill : Sends ON signal if there is something in the first slot of the microscope.
> Output Fill : Sends ON signal if there is an already scanned item inside the microscope.

Unless you want some complex logical wiring, you probably don't need to use these 3 outputs.