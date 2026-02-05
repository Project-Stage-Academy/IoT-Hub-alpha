import os
import time
import requests
from typing import Protocol
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from .data_structures import PayloadEnvelope, SendResult
from requests.exceptions import (
    ConnectTimeout,
    ReadTimeout,
    SSLError,
    ConnectionError,
    HTTPError,
    RequestException,
)

load_dotenv()

class Sender(Protocol):
    """
    Common http/mqtt interface
    """

    def send(
        self, item: PayloadEnvelope, session: requests.Session | None
    ) -> SendResult: ...


class HttpSender(Sender):
    """
    Http sender
    """

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def send(
        self, item: PayloadEnvelope, session: requests.Session | None
    ) -> SendResult:
        start = time.perf_counter()
        if not session:
            raise ValueError("Session failed to initialize")
        try:
            response = session.post(
                self.base_url,
                headers={"X-Device-Serial-Number": item.data.ssn},
                json=item.data.model_dump(exclude={"ssn"}),
                timeout=self.timeout,
            )
            latency = int((time.perf_counter() - start) * 1000)
            return SendResult(
                code_got=response.status_code,
                code_expected=item.expected,
                status="Pass" if response.status_code == item.expected else "Fail",
                latency=latency,
                error=None,
            )

        except ConnectTimeout as exc:
            return self._fail(item, start, "connect_timeout", exc)

        except ReadTimeout as exc:
            return self._fail(item, start, "read_timeout", exc)

        except SSLError as exc:
            return self._fail(item, start, "ssl_error", exc)

        except ConnectionError as exc:
            return self._fail(item, start, "connection_error", exc)

        except HTTPError as exc:
            return self._fail(item, start, "http_error", exc)

        except RequestException as exc:
            return self._fail(item, start, "request_exception", exc)

    def _fail(
        self, item: PayloadEnvelope, start: float, error_type: str, exc: Exception
    ) -> SendResult:
        latency = int((time.perf_counter() - start) * 1000)
        return SendResult(
            code_got=None,
            code_expected=item.expected,
            status="FAIL",
            latency=latency,
            error=error_type,
        )


class MqttSender(Sender):
    """
    mqtt sender
    """
    username = os.getenv("MQTT_USERNAME", "test")
    password = os.getenv("MQTT_PASSWORD", "test")

    def __init__(self, broker_url: str, topic: str, port: int) -> None:
        self.broker_url = broker_url
        self.topic = topic
        self.port = port
        self.username = MqttSender.username
        self.password = MqttSender.password
        
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set()

        def on_connect(client, userdata, flags, reason_code, properties=None):
            # reason_code == 0 means success
            self.connected = (reason_code == 0)
            if not self.connected:
                print("MQTT connect failed, reason_code:", reason_code)

        def on_disconnect(client, *args):
            self.connected = False

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

        self.client.connect(self.broker_url, self.port, 60)
        self.client.loop_start()
        
        t0 = time.time()
        while not self.connected and (time.time() - t0) < 5:
            time.sleep(0.05)

        if not self.connected:
            raise RuntimeError("MQTT: failed to connect within 5s")


    def send(
        self, item: PayloadEnvelope, session: requests.Session | None
    ) -> SendResult:
        
        topic = f'{self.topic.strip("/")}/{item.data.ssn if item.data.ssn else "error"}'
        info = self.client.publish(topic, item.data.model_dump_json())
        info.wait_for_publish(timeout=5)
        time.sleep(0.1)
        return SendResult(
            code_got = info.rc,
            code_expected = 0 if str(item.expected).startswith("2") else 1,
            status = "Pass" if info.rc else "Fail",
            latency = 5,
            error = None
        )
        
    def close(self):
        self.client.loop_stop()
        self.client.disconnect()