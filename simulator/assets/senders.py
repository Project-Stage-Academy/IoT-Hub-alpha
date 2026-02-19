import json
import time
import requests
import ssl
from typing import Protocol, Any, Callable
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


class Sender(Protocol):
    """
    Common http/mqtt interface
    """

    def send(
        self, item: PayloadEnvelope, session: requests.Session | None
    ) -> SendResult:
        pass


class HttpSender(Sender):
    """
    Http sender
    """

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = f'{base_url.rstrip("/")}/'
        self.timeout = timeout

    def send(
        self, item: PayloadEnvelope, session: requests.Session | None
    ) -> SendResult:
        start = time.perf_counter()

        if not session or not isinstance(session, requests.Session):
            return self._fail(item, start, "Bad session", None)

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
        self,
        item: PayloadEnvelope,
        start: float,
        error_type: str,
        exc: Exception | None,
    ) -> SendResult:

        latency = int((time.perf_counter() - start) * 1000)

        return SendResult(
            code_got=None,
            code_expected=item.expected,
            status="Fail",
            latency=latency,
            error=error_type,
        )


class MqttPublisher(Sender):
    """
    mqtt sender
    """

    def __init__(self, topic: str, mqtt_sleep: int) -> None:
        self.topic = topic
        self.mqtt_sleep = mqtt_sleep

    def send(self, item: PayloadEnvelope, session: mqtt.Client | None) -> SendResult:

        start = time.perf_counter()

        if not session or not isinstance(session, mqtt.Client):
            raise ValueError("Bad session")
        try:
            topic = (
                f'{self.topic.strip("/")}/{item.data.ssn if item.data.ssn else "error"}'
            )
            info = session.publish(topic, item.data.model_dump_json())
            info.wait_for_publish(timeout=5)
            latency = int((time.perf_counter() - start) * 1000)
            time.sleep(self.mqtt_sleep)

            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                print("publish failed:", info.rc)

            return SendResult(
                code_got=info.rc,
                code_expected=0,
                status="Pass" if info.rc == 0 else "Fail",
                latency=latency,
                error=None,
            )
        except TimeoutError as exc:
            return self._fail(item, start, "Timeouterror ", exc)

        except OSError as exc:
            return self._fail(item, start, "OS error ", exc)

        except (ValueError, TypeError) as exc:
            return self._fail(item, start, "Value/Type error ", exc)

        except RuntimeError as exc:
            return self._fail(item, start, "runtime error ", exc)

    def _fail(
        self,
        item: PayloadEnvelope,
        start: float,
        error_type: str,
        exc: Exception | None,
    ) -> SendResult:
        latency = int((time.perf_counter() - start) * 1000)
        return SendResult(
            code_got=1,
            code_expected=0,
            status="Fail",
            latency=latency,
            error=error_type,
        )
