import time
import requests
from typing import Protocol
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
        self, item: PayloadEnvelope, session: requests.Session | mqtt.Client | None
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
        
        if not session or not isinstance(session, requests.Session):
            raise ValueError("Bad session")
        
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


    def __init__(self, topic: str) -> None:
        self.topic = topic


    def send(
        self, item: PayloadEnvelope, session: requests.Session | mqtt.Client | None
    ) -> SendResult:
        
        if not session or not isinstance(session, mqtt.Client):
            raise ValueError("Bad session")
        
        topic = f'{self.topic.strip("/")}/{item.data.ssn if item.data.ssn else "error"}'
        start = time.perf_counter()
        info = session.publish(topic, item.data.model_dump_json())
        info.wait_for_publish(timeout=5)
        latency = int((time.perf_counter() - start) * 1000)
        time.sleep(0.1)
        return SendResult(
            code_got = info.rc,
            code_expected = 0 if str(item.expected).startswith("2") else 1,
            status = "Pass" if info.rc else "Fail",
            latency = latency,
            error = None
        )