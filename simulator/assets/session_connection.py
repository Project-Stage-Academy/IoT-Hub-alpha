import os
import requests
import socket
from dotenv import load_dotenv
from paho.mqtt.client import Client
from paho.mqtt.enums import CallbackAPIVersion
from .data_structures import Config

load_dotenv()


class SessionContext:

    username = os.getenv("MQTT_USERNAME", "test")
    password = os.getenv("MQTT_PASSWORD", "test")
    use_tls = (
        False if os.getenv("MQTT_USE_TLS", "false") in ["false", "False", "0"] else True
    )

    def __init__(self, mode: str, config: Config):
        self.mode = mode
        self.session = None
        self.client = None
        self.broker_url = config.mqtt_url
        self.topic = config.mqtt_topic
        self.port = config.mqtt_port
        self.timeout = config.default_timeout
        self.username = SessionContext.username
        self.password = SessionContext.password

    def __enter__(self):
        if self.mode == "http":
            self.session = requests.Session()
            return self.session

        elif self.mode == "mqtt":
            self.client = Client(CallbackAPIVersion.VERSION2)
            self.client.connect_timeout = self.timeout
            socket.setdefaulttimeout(self.timeout)
            self.client.username_pw_set(self.username, self.password)
            if SessionContext.use_tls:
                self.client.tls_set()
            self.client.connect(self.broker_url, self.port, 60)
            self.client.loop_start()
            return self.client
        else:
            raise ValueError(f"{self.mode} does not exist!")

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.mode == "http" and self.session:
            self.session.close()

        elif self.mode == "mqtt" and self.client:
            self.client.loop_stop()
            self.client.disconnect()
