# [FU] Configurable 3-State Cycler

**来源**: Frackin' Universe Wiki | **链接**: https://frackinuniverse.miraheze.org/wiki/Configurable_3-State_Cycler

---

**Configurable 3-State Cycler** is an object that you can place on background walls. It has three **outputs** that you can wire to other devices. It will send ON signal to the first wire for A seconds, then to second wire for B seconds, then to third wire for C seconds. Here A, B and C are numbers between 1 and 120, and you can choose them by approaching the Cycler and interacting ([E] button) with it.

## How it looks
Interface of 3-State Cycler when you Interact (**[E]**) with it:

## Anti-lag device
Description above may look useless at first, but this device is **amazing at eliminating lag** from your Item Transference Devices. For example, if you do the following:
1. Set the timers (A/B/C) to 8/1/1.
1. Wire the third to the left of Item Transference Device.
... then Item Transference Device would be disabled for 9 seconds out of 10, and would only "awaken" once every 10 seconds. Therefore it will consume 10 times less CPU time than without the 3-State Cycler (normally Item Transference Device would be performing its intense calculations for the entirety of those 10 seconds).

Example of throttled ITD: 

Because most item transfers are not urgent (for example, moving the water from Wells to Trays can be done rarely), almost every Item Transference Device can be made faster via this trick.

## See also
- Performance