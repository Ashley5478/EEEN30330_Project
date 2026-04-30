# To start, run Powershell and type in the following command in the Rainer folder:
# .\.venv\Scripts\Activate.ps1
# python .\rainer_client.py 192.168.XXX.XXX 5254

from machine import Pin, ADC
from utime import sleep
import network
import asyncio
import ssl
from os import urandom
from cryptolib import aes
import json
from binascii import a2b_base64

UINT16_MAX = 65535
SENSOR_MAX_VOLT = 3.3 # Theoretical maximum voltage of the sensor through ADC pin
SENSOR_MAX_MOIST = 2.0 # Maximum voltage achievable by sensor for full moisture

# SSL/TLS Certificate
# PEM file is only for the client-side.
# rainer.crt.base64
rainer_certificate=a2b_base64("""




<PLEASE PASTE THE WHOLE CONTENT OF THE FILE NAMED "rainer.crt.base64">




""".strip())
# rainer.key.base64
rainer_key=a2b_base64("""

<PLEASE PASTE THE WHOLE CONTENT OF THE FILE NAMED "rainer.key.base64">

""".strip())

# 256-bit key used for challenge-response.
CR_KEY=bytes.fromhex("<PLEASE USE 'openssl rand -hex 32' IN YOUR COMMAND PROMPT AND PASTE THE HEX GENERATED HERE>")

def challenge_response(seed: bytes):
    # seed is a 16-byte. It is okay to use ECB
    challenger = aes(CR_KEY, 1)
    return challenger.encrypt(seed)

# Consts
WLAN_RETRY_SEC = 5	#Re-attempts connection after 5 seconds if not connected
WLAN_CONNECTION_TIMEOUT=10
HOST="0.0.0.0"
PORT=5254
# Hard-coded Values
#SSID = "Bbox-6E0D8E28"
#PASSWORD = "2000007169"
#SSID = "SK_WiFiGIGA8900"
#PASSWORD = "2002000294"
SSID = "DESKTOP-S131ORK 7825"
PASSWORD = "1-2081Gb"

DEFAULT_POT_LOW_THRESHOLD=50    # Default value in percentage for which, if the probe value is lower, flag for watering.  
DEFAULT_POT_HIGH_THRESHOLD=90	# Default value in percentage for which, if the probe value is higher, warn for too much water.
DEFAULT_INTERVAL = 10			# Default measurement interval in seconds
DEFAULT_DURATION = 2			# Default watering duration in seconds

# Modes
MODE_AUTOMATIC = 0 # Automatically detect if the soil is dry, and starts watering.
MODE_MANUAL = 1 # Only alert via LED that the plant needs watering, but does not water until commanded to.

# Commands
COMMAND_QUERY = 0			# Checks the status of the system, including automatic mode, pump state, threshold, interval, and watering duration
COMMAND_SET_MODE = 1		# Changes the mode between automatic and manual mode
COMMAND_SET_PUMP = 2		# Turns the pump on or off (Manual mode only, does not work in auto mode)
COMMAND_SET_THRESHOLD = 3	# Changes the moisture threshold level
COMMAND_SET_INTERVAL = 4	# Changes the interval of measuring the moisture level (Auto mode)
COMMAND_SET_DURATION = 5	# Changes the duration of water pump releasing when the soil is dry (Auto mode)

class Application:
    def __init__(self):
        self.mode = MODE_AUTOMATIC
        self.alert_led = Pin("LED", Pin.OUT)
        self.pot_sensors: list[ADC] = [
            ADC(26), # Pin31, GP26 for moisture sensor
        ]
        self.pumps: list[Pin] = [
            Pin(15, Pin.OUT), # Pin20, GP15 for pump gate switch
        ]

        # Threshold for signalling the need to water.
        self.low_threshold: list[int] = [DEFAULT_POT_LOW_THRESHOLD for _ in range(len(self.pot_sensors))]
        self.high_threshold: list[int] = [DEFAULT_POT_HIGH_THRESHOLD for _ in range(len(self.pot_sensors))]
        self.pot_data: list[int] = [0 for _ in range(len(self.pot_sensors))]
        self.percentage_moist: list[float] = [0 for _ in range(len(self.pot_sensors))]
        self.status_lock = asyncio.Lock()       # Used for lock for reading and writing information.
        
        self.interval = DEFAULT_INTERVAL
        self.duration = DEFAULT_DURATION
        
        # SSL Context
        self.ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ssl_ctx.load_cert_chain(rainer_certificate, rainer_key)
        # TODO: Allow no-internet mode as well. (For debugging, must be connected to internet.)
        while True:
            try:
                self.network_info = self.__connect_to_wifi()
                break
            except:
                print(f"Sleeping for {WLAN_RETRY_SEC} seconds before retrying.")
                sleep(WLAN_RETRY_SEC)
    
    def extractData(self) -> dict:
        # Trigger a fresh read to ensure data is current
        self._refresh_sensor_data()
        
        data = dict()
        data["manual_mode"] = (self.mode == MODE_MANUAL)
        #data["raw_ADC_data"] = self.pot_data # Returns raw ADC level out of 65535
        data["moisture_percentage"] = self.percentage_moist # Returns scaled moisture level in
        
        moisture_status_list = []
        for i in range(len(self.pot_sensors)):
            val = self.percentage_moist[i]
            # Compare current percentage against thresholds
            if val < self.low_threshold[i]:
                moisture_status_list.append("Below threshold: Soil dry")
            elif val > self.high_threshold[i]:
                moisture_status_list.append("Above threshold: Soil wet")
            else:
                moisture_status_list.append("Moisture just right level")
        data["moisture_status"] = moisture_status_list
        
        
        data["pump_status"] = [pump.value() == 1 for pump in self.pumps]
        data["pump_high_thresholds"] = self.high_threshold
        data["pump_low_thresholds"] = self.low_threshold
        return data
    
    def __parse_command(self, data : bytes): # Command parsing
        '''Convert bytes into dictionary form. Throws error if incorrect format.'''
        data_str = data.decode()
        command_data = json.loads(data_str)
        if not isinstance(command_data, dict):
            raise ValueError
        # Needs to have "command" key
        if "command" not in command_data.keys():
            raise ValueError
        
        if command_data["command"] == COMMAND_QUERY:
            # Do nothing
            pass
        elif command_data["command"] == COMMAND_SET_MODE:
            # Check for "mode" field and sanity check
            if "mode" not in command_data.keys():
                raise ValueError
            if command_data["mode"] not in {MODE_AUTOMATIC, MODE_MANUAL}:
                raise ValueError
        elif command_data["command"] == COMMAND_SET_PUMP:
            if "status" not in command_data.keys():
                raise ValueError
            if command_data["status"] not in {True, False}:
                raise ValueError
            if "index" not in command_data.keys():
                raise ValueError
            if not isinstance(command_data["index"], int):
                raise ValueError
            if command_data["index"] < 0 or command_data["index"] >= len(self.pumps):
                raise ValueError
        elif command_data["command"] == COMMAND_SET_THRESHOLD:
            if "index" not in command_data.keys():
                raise ValueError
            if not isinstance(command_data["index"], int):
                raise ValueError
            if "type" not in command_data.keys():
                raise ValueError
            if command_data["type"] not in {"high", "low"}:
                raise ValueError
            if "value" not in command_data.keys():
                raise ValueError
            if not isinstance(command_data["value"], int):
                raise ValueError
            if command_data["value"] < 0 or command_data["value"] > UINT16_MAX:
                raise ValueError
        elif command_data["command"] == COMMAND_SET_INTERVAL:
            if "interval" not in command_data.keys() or not isinstance(command_data["interval"], int) or command_data["interval"] <= 0:
                raise ValueError
        elif command_data["command"] == COMMAND_SET_DURATION:
            if "duration" not in command_data.keys() or not isinstance(command_data["duration"], int) or command_data["duration"] <= 0:
                raise ValueError
        else:
            raise ValueError

        return command_data
    
    def _refresh_sensor_data(self):
        """Helper to perform a fresh sensor read and calculation."""
        for i in range(len(self.pot_sensors)):
            # 1. Read Raw ADC
            raw = self.pot_sensors[i].read_u16()
            self.pot_data[i] = raw
            
            # 2. Convert to voltage and percentage
            # Formula: (raw / 65535) * 3.3V
            voltage = (raw / UINT16_MAX) * SENSOR_MAX_VOLT
            
            # 3. Calculate percentage (2.0V is 100%)
            if voltage >= SENSOR_MAX_MOIST:
                self.percentage_moist[i] = 100.0
            else:
                self.percentage_moist[i] = (voltage / SENSOR_MAX_MOIST) * 100.0
    
    async def __process_command(self, reader, writer, command):
        '''Process the parsed command. Note that this function assumes that the sanity is already checked from __parse_command'''
        
        
        if command["command"] == COMMAND_QUERY:
            async with self.status_lock:
                data = self.extractData()
            writer.write(json.dumps(data))
            await writer.drain()

        elif command["command"] == COMMAND_SET_MODE:
            # Update the mode
            self.mode = command["mode"]
            print(f"Mode switched to: {'Manual' if self.mode == MODE_MANUAL else 'Automatic'}")
            
            # --- NEW LOGIC ---
            # If we are switching to Automatic, ensure all pumps are OFF
            # so they don't continue running from a previous manual session.
            if self.mode == MODE_AUTOMATIC:
                print("Switching to Automatic: Turning off all pumps.")
                for pump in self.pumps:
                    pump.off()
            # -----------------
            
            response = {"ok": True}
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()

        elif command["command"] == COMMAND_SET_PUMP:
            if self.mode == MODE_MANUAL:
                async with self.status_lock:
                    pump_idx = command["index"]
                    if command["status"]:
                        self.pumps[pump_idx].on()
                    else:
                        self.pumps[pump_idx].off()
                writer.write(f"Pump #{pump_idx} set to {command['status']}")
                await writer.drain()
            elif self.mode == MODE_AUTOMATIC:
                writer.write(f"Rainer mode is not MODE_MANUAL! Rejecting!")
                await writer.drain()
            
        elif command["command"] == COMMAND_SET_THRESHOLD:
            async with self.status_lock:
                pump_idx = command["index"]
                if command["type"] == "high":
                    if command["value"] > self.low_threshold[pump_idx]:
                        self.high_threshold[pump_idx] = command["value"]
                        writer.write(f"Pump #{pump_idx} high threshold set to {command['value']}")
                        await writer.drain()
                    else:
                        writer.write("High threshold is equal or lower than the low threshold. Rejecting!")
                        await writer.drain()
                elif command["type"] == "low":
                    if command["value"] < self.high_threshold[pump_idx]:
                        self.low_threshold[pump_idx] = command["value"]
                        writer.write(f"Pump #{pump_idx} low threshold set to {command['value']}")
                        await writer.drain()
                    else:
                        writer.write("Low threshold is equal or higher than the high threshold. Rejecting!")
                        await writer.drain()
        elif command["command"] == COMMAND_SET_INTERVAL:
            async with self.status_lock:
                self.interval = command["interval"]
            writer.write(f"Interval set to {self.interval}s".encode())
            await writer.drain()

        elif command["command"] == COMMAND_SET_DURATION:
            async with self.status_lock:
                self.duration = command["duration"]
            writer.write(f"Duration set to {self.duration}s".encode())
            await writer.drain()
        else:
            writer.write(b"Error in processing command")
            await writer.drain()
        
    
    # Private methods
    def __set_mode(self, mode):
        '''Set the operation mode of the application'''
        if mode not in {MODE_AUTOMATIC, MODE_MANUAL}:
            raise RuntimeError("Unexpected mode.")
        
        self.mode = mode
    
    def __connect_to_wifi(self):
        '''Attempt to connect to Wifi. Returns network_info if successful, otherwise raises error.'''
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.connect(SSID, PASSWORD)
        connection_timeout = WLAN_CONNECTION_TIMEOUT
        while connection_timeout > 0:
            if wlan.status() >= 3:
                break
            connection_timeout -= 1
            print(f"Waiting for connection to {SSID}")
            sleep(1)

        if wlan.status() != 3:
            raise RuntimeError("Connecting to WiFi failed.")
        else:
            print("Connection good!")
            network_info = wlan.ifconfig()
            print(f"IP: {network_info[0]}")
            return network_info
    
    async def __loop_task(self):
        while True:
            # Check the mode before performing any sensor-related tasks
            if self.mode == MODE_AUTOMATIC:
                print("Loop: MODE_AUTOMATIC - Performing moisture check.")
                
                # Perform the fresh read for automatic loop logic
                self._refresh_sensor_data()
                
                isAtLeastOneDry = False
                for i in range(len(self.pot_sensors)):
                    # Logic: Check moisture level against the low_threshold
                    print(f"Sensor {i}: {self.percentage_moist[i]}% moisture.")
                    
                    if self.percentage_moist[i] < self.low_threshold[i]:
                        isAtLeastOneDry = True
                        print(f"Sensor {i} indicates dry soil. Triggering pump.")
                        self.pumps[i].on()
                        # Allow time for watering
                        await asyncio.sleep(self.duration)
                        self.pumps[i].off()
                    elif self.percentage_moist[i] > self.high_threshold[i]:
                        # Ensure pump is off if moisture is above high threshold
                        self.pumps[i].off()
                
                # Update LED status based on the result
                if isAtLeastOneDry:
                    print("Alerting: Moisture levels require attention.")
                    self.alert_led.on()
                else:
                    print("Status: Moisture levels normal.")
                    self.alert_led.off()
            
            else:
                # MODE_MANUAL: Skip sensor reading to prevent oxidation.
                # We do not read the sensor here, saving the probe from unnecessary power.
                # print("Loop: MODE_MANUAL - Skipping moisture check to prevent oxidation.")
                self.alert_led.off()
                # Ensure all pumps are off in manual mode if needed
                for pump in self.pumps:
                    pump.off()

            # The sleep interval remains constant, ensuring we don't mess up the loop timing
            await asyncio.sleep(self.interval)
    
    async def __handle_connection(self, reader, writer):
        # Generating seed for challenge_response. It uses shared-secret key authentication.
        challenge_seed = urandom(16)
        challenge_expected_response = challenge_response(challenge_seed)
        print("Sending seed to a client...")
        #print(challenge_seed)
        writer.write(challenge_seed)
        await writer.drain()
        try:
            data_received = await reader.readexactly(16)
            if data_received != challenge_expected_response:
                raise RuntimeError
        except:
            print("Error at challenge response.")
            await writer.wait_closed()
            return
        
        writer.write(b"Challenge accepted!")
        await writer.drain()

        try:
            data_recved = await reader.readline()
        except OSError:
            print("Connection closed unexpectedly!")
            await writer.wait_closed()
            return
        try:
            command = self.__parse_command(data_recved)
            print(command)
            await self.__process_command(reader, writer, command)
        except ValueError:
            print("Could not parse command")
        await writer.wait_closed()
    
    async def __main(self):
        asyncio.create_task(self.__loop_task())
        await asyncio.start_server(self.__handle_connection, HOST, PORT, ssl=self.ssl_ctx)
        
        while True:
            await asyncio.sleep(3600)

    def run(self):
        '''Runs the application.'''
        asyncio.run(self.__main())

############################# Pre-launch Setup #############################

############################# Main Server Loop Tick #############################
app = Application()
app.run()

'''
print("LED starts flashing...")
while True:
    try:
        pin.toggle()
        sleep(1) # sleep 1sec
    except KeyboardInterrupt:
        break
pin.off()
print("Finished.")
'''
