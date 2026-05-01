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

## Server system structure
![alt text](https://github.com/Ashley5478/EEEN30330_Project/blob/main/Server_flowchart.png?raw=true)
The flowchart above is the flowchart that the Raspberry Pi Pico 2 W will follow.

## Deployment Guide
There are a few steps required for deployment.
### SSL Certificate and Key
You must have installed `OpenSSL` in your system. Please install one if you have not.

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

Once you have copied SSL keys above, create a shared key that is used for authentication, by running the following:
```
openssl rand -hex 32
```
and then copy the resulting hex string onto `rainer.py`, `rainer_client.py`, and `webconsole/app.py` at appropriate location by finding the following lines:
```
# 256-bit key used for challenge-response.
CR_KEY=bytes.fromhex("<PLEASE USE 'openssl rand -hex 32' IN YOUR COMMAND PROMPT AND PASTE THE HEX GENERATED HERE>")
```
and replace the text in quotation marks with the hex string generated. Make sure the CR_KEY has the same key for all three files.

(If needed, change it. Note that it is paramount that this is not stolen.)

## Command ID Match
Make sure that the command constants defined in `rainer.py` and `rainer_client.py` match.
```
# Modes
# MODE_AUTOMATIC: Automatically detect if the soil is dry, and starts watering.
# MODE_MANUAL: Only alert via LED that the plant needs watering, but does not water until commanded to.
MODE_AUTOMATIC = 0
MODE_MANUAL = 1

# Commands
COMMAND_QUERY = 0			# Checks the status of the system, including automatic mode, pump state, threshold, interval, and watering duration
COMMAND_SET_MODE = 1		# Changes the mode between automatic and manual mode
COMMAND_SET_PUMP = 2		# Turns the pump on or off (Manual mode only, does not work in auto mode)
COMMAND_SET_THRESHOLD = 3	# Changes the moisture threshold level
COMMAND_SET_INTERVAL = 4	# Changes the interval of measuring the moisture level (Auto mode)
COMMAND_SET_DURATION = 5	# Changes the duration of water pump releasing when the soil is dry (Auto mode)
```

## Pins
Within `__init__` method of `Application` class,
```
self.pot_sensors: list[ADC] = [
    ADC(26),
]
self.pumps: list[Pin] = [
    Pin(15, Pin.OUT)
]
```
`ADC(26)` is for the soil humidity sensor. (GP26)
`Pin(15, Pin.OUT)` is for the pump. (GP15, To be controlled like an LED.)
**Number of `self.pot_sensors` elements must equal the number of `self.pumps` elements.**

### Flash the Application
This is straightforward. Load `rainer.py` to Raspberry Pi Pico 2W

### Setting up the virtual environment (recommended)
Setting the virtual environment before running Python isolates Python dependencies at the project level, preventing version conflicts.
If you are in the folder `C:\Users\Project\Rainer` then run
```
python -m venv "C:\Users\Project\Rainer\.venv"
.\.venv\Scripts\Activate.ps1
```
where `.ps1` file is used for Windows Powershell. Please use the appropriate file starting with `Activate` for your operating system.

### Boot
Once Raspberry Pi Pico 2W boots, it should print out IP address. The port used is 5254.
If running headless, check the router information or run an ARP scan and figure it out.

Run the virtual environment and then follow one of the options:
### Option 1: Using client (command-line)
`rainer_client.py` is what you use to interact with the application.

It is a small script that sends commands to your device and receives replies.
Note that this script uses `rainer.pem` file.

Also note that this script requires the installation of `cryptography` Python module.

Example Usage:
```
python rainer_client.py 192.168.35.251 5254
```

### Option 2: Using client (User interface, recommended)
An alternative program `webconsole/app.py` is used to run the user interface client program through `localhost:5000` or `127.0.0.1:5000`.
Please install `cryptography` Python module in advance.

Go to the folder `webconsole` and enter in your command line:
```
python app.py
```
Then go to your web browser and navigate `localhost:5000` or `127.0.0.1:5000`. You will notice a screen that asks you to fill in the IP address and the port.
Enter the IP address of the server such as `192.168.35.251` and the port `5254`. Press connect. Enjoy.

## Brief technical details
The unit of the moisture level is in percentage and the time in seconds when typing in the numbers for changing the settings.

The default settings are as followed:
* Mode = Automatic
* Lower threshold = 50%
* Upper threshold = 90%
* Moisture sensing period = 10 seconds
* Water pump duration = 2 seconds
The user can change all the options above using either Option 1 or Option 2. The lower threshold is what determines the behavior of the water pump. When the detected moisture level is below the lower threshold, then the water pump activates for 2 seconds by default. To make the moisture sening be done every 1 day, please set the moisture sensing period to `86400`.

The manual activation of water pump can only be done when the system is set to manual mode.

A resistive moisture sensor is assumed to be used and it gives the voltage up to 2 V when the moisture is at full level. Hence the percentage of the moisture is calculated as followed:
$MoistureLevel = SensorVoltage * \frac{100%}{2 V}$
and 100% when $SensorVoltage > 2$.

Upon querying for the current status of the system, the server returns the state information in JSON format.

## Current limitations
Clients must be connected to the same network where the server is connected to since the connection is done through the private IP address. To connect to the server abroad from a different network, then setting a VPN server is necessary.

The client must know the server's IP address, which changes every time the server restarts or reconnects. It is essential to configure the router to assign a fixed IP address of the server.

Currently only one sensor and a pump is supported, therefore, the index number `0` should be used when changing the moisture threshold and manually controlling the pump. The index feature is reserved for future expansion when multiple sensors and pumps are added.
