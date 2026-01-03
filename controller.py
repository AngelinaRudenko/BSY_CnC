from paho.mqtt import client as mqtt

MQTT_BROKER = "147.32.82.209"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors"

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
    except Exception as ex:
        print(f"Failed to handle message: {ex}")

def main():
    # create MQTT client
    client_id = "Controller"
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