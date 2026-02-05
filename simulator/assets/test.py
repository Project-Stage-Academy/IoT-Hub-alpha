import json
import time
import paho.mqtt.client as mqtt

broker = "54abf624e48440ad8e6733f1d400a8b8.s1.eu.hivemq.cloud"
port = 8883
topic = "telemetry/devices"

username = "testmqtt"
password = "a319260188A!"

payload = {"device_id": "dev-1", "temperature": 42.1}

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(username, password)
client.tls_set()  # <-- required for 8883

print(client.connect(broker, port, 60))
client.loop_start()  # <-- required so publish can actually go out

info = client.publish(topic, json.dumps(payload), qos=1)
info.wait_for_publish(timeout=5)

time.sleep(0.2)  # tiny grace period
client.loop_stop()
client.disconnect()

print("published:", info.is_published(), "rc:", info.rc)
