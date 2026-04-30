#!/bin/python3
'''This is a client for interacting with rainer server.'''

import socket
import json
import sys
import ssl
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

UINT16_MAX = 65535

# 256-bit key used for challenge-response.
CR_KEY=bytes.fromhex("<PLEASE PASTE THE SAME CR_KEY FROM THE rainer.py>")
def challenge_response(seed: bytes):
    # seed is a 16-byte. It is okay to use ECB
    cipher = Cipher(algorithms.AES(CR_KEY), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(seed) + encryptor.finalize()

# Modes
# MODE_AUTOMATIC: Automatically detect if the soil is dry, and starts watering.
# MODE_MANUAL: Only alert via LED that the plant needs watering, but does not water until commanded to.
MODE_AUTOMATIC = 0
MODE_MANUAL = 1

# Commands
COMMAND_QUERY = 0
COMMAND_SET_MODE = 1
COMMAND_SET_PUMP = 2
COMMAND_SET_THRESHOLD = 3
COMMAND_SET_INTERVAL = 4
COMMAND_SET_DURATION = 5

def build_command() -> bytes:
    available_commands = [COMMAND_QUERY, COMMAND_SET_MODE, COMMAND_SET_PUMP, COMMAND_SET_THRESHOLD,COMMAND_SET_INTERVAL,COMMAND_SET_DURATION]
    available_modes = [MODE_AUTOMATIC, MODE_MANUAL]
    command_data = dict()
    print("Type of Command")
    print("0. COMMAND_QUERY")
    print("1. COMMAND_SET_MODE")
    print("2. COMMAND_SET_PUMP")
    print("3. COMMAND_SET_THRESHOLD")
    print("4. COMMAND_SET_INTERVAL")
    print("5. COMMAND_SET_DURATION")

    command = available_commands[int(input("Enter index: "))]
    if command == COMMAND_QUERY:
        command_data["command"] = command
    elif command == COMMAND_SET_MODE:
        command_data["command"] = command
        print("Type of Mode")
        print("0. MODE_AUTOMATIC")
        print("1. MODE_MANUAL")
        command_data["mode"] = available_modes[int(input("Enter index: "))]
    elif command == COMMAND_SET_PUMP:
        command_data["command"] = command
        command_data["index"] = int(input("Enter pump index: "))
        status = input("Open or close: ").lower()
        if status == "open":
            command_data["status"] = True
        elif status == "close":
            command_data["status"] = False
        else:
            raise ValueError
    elif command == COMMAND_SET_THRESHOLD:
        command_data["command"] = command
        command_data["index"] = int(input("Enter pump index: "))
        t_type = input("High or low: ").lower()
        if t_type == "high":
            command_data["type"] = "high"
        elif t_type == "low":
            command_data["type"] = "low"
        else:
            raise ValueError
        value = int(input(f"Enter threshold value (0~{UINT16_MAX}): "))
        if value < 0 or value > UINT16_MAX:
            raise ValueError
        else:
            command_data["value"] = value
    elif command == COMMAND_SET_INTERVAL:
        command_data["command"] = command
        command_data["interval"] = int(input("Enter interval in seconds: "))
    elif command == COMMAND_SET_DURATION:
        command_data["command"] = command
        command_data["duration"] = int(input("Enter watering duration in seconds: "))
    else:
        raise ValueError

        
    return (json.dumps(command_data) + '\n').encode()

if __name__ == "__main__":
    #ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.load_verify_locations("./rainer.pem")
    ssl_ctx.check_hostname = False

    argc = len(sys.argv)
    if argc != 3:
        print("Usage: python rainer_client.py host_ip port")
        sys.exit(1)
    
    host_ip = sys.argv[1]
    try:
        port = int(sys.argv[2])
    except:
        print(f"Failed to parse port into integer: {sys.argv[2]}")
        sys.exit(1)
    
    # Building command
    try:
        command_b = build_command()
    except:
        print("Wrong choice entered when building command")
        sys.exit(1)
    
    # Create a socket
    s_raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s_raw.connect((host_ip, port))
    except:
        print(f"Failed to connect to {host_ip}")
        sys.exit(1)

    s = ssl_ctx.wrap_socket(s_raw, server_hostname=host_ip)
    seed = b""
    while len(seed) != 16:
        seed += s.recv(16 - len(seed))
    # Computing response
    response = challenge_response(seed)
    s.sendall(response)

    print(s.recv(1000))

    s.sendall(command_b)
    print(s.recv(1000))
    s.close()
    
    