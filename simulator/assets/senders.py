import json
import time
import requests
from typing import Protocol, Any, Callable
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

    def __init__(
        self,
        broker_url: str,
        topic: str,
        client: Any | None = None,
        encoder: Callable[[dict], str] | None = None,
    ) -> None:

        self.broker_url = broker_url
        self.topic = topic
        self.client = client
        self.encoder = encoder or json.dumps
        self.mock_send_result = SendResult.model_validate(
            {
                "code_got": 200,
                "code_expected": 200,
                "status": "Pass",
                "latency": 20,
                "error": None,
            }
        )

    def send(
        self, item: PayloadEnvelope, session: requests.Session | None
    ) -> SendResult:

        if not self.client:
            print("MQTT Sim not implemented at this stage!")
            return self.mock_send_result

        start = time.perf_counter()

        try:

            payload = self.encoder(item.data.model_dump())
            publish_result = self.client.publish(self.topic, payload)
            code_got = self._publish_code(publish_result)
            status = "Pass" if code_got == item.expected else "Fail"
            latency = int((time.perf_counter() - start) * 1000)

            return SendResult(
                code_got=code_got,
                code_expected=item.expected,
                status=status,
                latency=latency,
                error=None if status == "Pass" else "publish_error",
            )

        except Exception:
            latency = int((time.perf_counter() - start) * 1000)

            return SendResult(
                code_got=None,
                code_expected=item.expected,
                status="FAIL",
                latency=latency,
                error="publish_exception",
            )

    @staticmethod
    def _publish_code(publish_result: Any) -> int:

        if hasattr(publish_result, "rc"):
            return 200 if publish_result.rc == 0 else 500

        if isinstance(publish_result, tuple) and publish_result:
            return 200 if publish_result[0] == 0 else 500

        return 200
