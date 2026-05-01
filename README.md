# Internet of Things – IoT Irrigation machine: Rainer!
This is an application that runs on Rasberry Pi Pico 2W (Possibly on Raspberry Pi Pico W too)
for monitoring and watering plants. In the project, an IoT irrigation device is proposed,
which allows users such as households owning plants to monitor and maintain plants while being abroad.
The moisture sensor is used to measure the moisture level and the system automatically releases the water pump
when the moisture level is detected low.

A html user interface is included to allow communication with the irrigation system.
The control panel allows users to monitor the status such as current moisture level,
automation mode, moisture threshold level, and whether the water pump is active.
Users can also request the irrigation system wirelessly to change the system into manual mode,
adjust threshold level that determines wet/dry status, and activate the water pump.


## Deployment Guide
There are a few steps required for deployment.
### SSL Certificate and Key
Run the following to generate new SSL certificate and key.
```
make clean
make ssl
```
You should see `rainer.key*`, `rainer.crt*` and `rainer.pem`.
(Note that `rainer.key` and `rainer.crt` are in DER format whereas `rainer.pem` is in PEM format.
This is due to what the functions used in server application and client application expect.)

Copy the contents of `rainer.key.base64` and `rainer.crt.base64` onto `rainer.py` application at appropriate location.
(It is at the lines containing `a2b_base64` function.)

# Command ID Match
Make sure that the command constants defined in `rainer.py` and `rainer_client.py` match.
```
# Modes
# MODE_AUTOMATIC: Automatically detect if the soil is dry, and starts watering.
# MODE_MANUAL: Only alert via LED that the plant needs watering, but does not water until commanded to.
MODE_AUTOMATIC = 0
MODE_MANUAL = 1

# Commands
COMMAND_QUERY = 0
COMMAND_SET_MODE = 1
COMMAND_SET_PUMP = 2
```

Also make sure that CR_KEY matches between the two files.
(If needed, change it. Note that it is paramount that this is not stolen.)

# Pins
Within `__init__` method of `Application` class,
```
self.pot_sensors: list[ADC] = [
    ADC(26),
]
self.pumps: list[Pin] = [
    Pin(0, Pin.OUT)
]
```
`ADC(26)` is for the soil humidity sensor. (Add `ADC(27)` and `ADC(28)` if needed in the list.)
`Pin(0, Pin.OUT)` is for the pump. (To be controlled like an LED.)
**Number of `self.pot_sensors` elements must equal the number of `self.pumps` elements.**

### Flash the Application
This is straightforward. Load `rainer.py` to Raspberry Pi Pico 2W

### Boot
Once Raspberry Pi Pico 2W boots, it should print out IP address. The port used is 5254.
If running headless, check the router information or run an ARP scan and figure it out.

### Using Client
`rainer_client.py` is what you use to interact with the application.

It is a small script that sends commands to your device and receives replies.
Note that this script uses `rainer.pem` file.

Also note that this script requires the installation of `cryptography` Python module.

Example Usage:
```
python rainer_client.py 192.168.35.251 5254
```
