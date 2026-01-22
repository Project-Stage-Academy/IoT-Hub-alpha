import time
import requests
from typing import Protocol
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
    def send(self, item: PayloadEnvelope, session: requests.Session | None) -> SendResult:
        ...



class HttpSender(Sender):
    """
    Http sender
    """
    def __init__(self, base_url: str , timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def send(self, item: PayloadEnvelope, session: requests.Session | None) -> SendResult:
        start = time.perf_counter()
        if not session:
            raise ValueError("Session failed to initialize")
        try:
            response = session.post(
                self.base_url,
                json=item.data.model_dump(),
                timeout=self.timeout
            )
            latency = int((time.perf_counter() - start) * 1000)
            return SendResult(code_got = response.status_code,
                            code_expected = item.expected,
                            status="Pass" if response.status_code == item.expected else "Fail",
                            latency = latency,
                            error = None)
            
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
            exc: Exception
    ) -> SendResult:
        latency = int((time.perf_counter() - start) * 1000)
        return SendResult(
            code_got= None,
            code_expected=item.expected,
            status="FAIL",
            latency=latency,
            error = error_type
        )
        
class MqttSender(Sender):
    """
    mqtt sender
    """
    def __init__(self, broker_url: str, topic: str) -> None:
        self.broker_url = broker_url
        self.topic = topic
        self.mock_send_result = SendResult.model_validate({
            "code_got": 200,
            "code_expected": 200,
            "latency": 20
        })

    def send(self, item: PayloadEnvelope, session: requests.Session | None) -> SendResult:
        # Not Implemented!
        print ("MQTT Sim not implemented at this stage!")
        return self.mock_send_result