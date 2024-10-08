Python RapidHA
==============

Intro
-----
RapidHA is an off-the-shelf package of ZigBee hardware, desktop software, and embedded firmware purposed for product developers integrating the ZigBee Home Automation. This is a Python implementation for Serial communication with MMB Networks type devices.

See MMB Networks [Serial Protocol - RapidHA](https://mmbnetworks.atlassian.net/wiki/spaces/SPRHA17/overview)

Usage
-----

```
  from rapidha import RapidHADevice

  ra = RapidHADevice('/dev/ttyUSB0')
  ra.dispatch.register("printall", _printall, lambda packet: True)
  ra.start_thread()
  ra.reset()
```
