Linux drivers for characterisation of photonic chips.

Included hardware includes:
* Agilent mainframe (including tunable laser and power meter modules),
* Swept lasers: Sacher Lasertechnik and Newport Venturi.
* Power meters: Thorlabs PM100 and Newport 2832C.
* Oscilloscopes: Rigol 1000Z (USB driver).
* Single photon counter/timestamper: ID Quantique IDQ801.
* Stages: Luminos, Newport and Newport Picomotor.

The drivers include generic interface abstract base classes for:
* lasers,
* power meters, and
* stages.

Functionality:
* Control all hardware individually.
* Modules to synchronise laser, power meter and stages to optimise coupling
    efficiency and take fibre swept images.
* Synchronise swept laser with power meters.

Requirements:
* [Gnuplot](http://www.gnuplot.info/) required for plotting.
* [linux-gpib](https://linux-gpib.sourceforge.io/) required for equipment reliant
    on GPIB communication.
* [pyusb](https://github.com/pyusb/pyusb) required for some USB devices.
* [python-usbtmc](https://github.com/python-ivi/python-usbtmc) required for the
    Rigol1000z driver.
