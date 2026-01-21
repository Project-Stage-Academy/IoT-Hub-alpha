import time
import requests
from typing import Protocol
from .data_structures import PayloadEnvelope, SendResult


class Sender(Protocol):
    """
    Common http/mqtt interface
    """
    def send(self, item: PayloadEnvelope) -> SendResult:
        ...



class HttpSender(Sender):
    """
    Http sender
    """
    def __init__(self, session: requests.Session, base_url: str) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")

    def send(self, item: PayloadEnvelope) -> SendResult:
        start = time.perf_counter()

        try:
            response = self.session.post(
                self.base_url,
                json=item.data.model_dump(),
                timeout=5.0
            )
            latency = int((time.perf_counter() - start) * 1000)
            return SendResult(code_got = response.status_code,
                              code_expected = item.expected,
                              status="Pass" if response.status_code == item.expected else "Fail",
                              latency = latency)
            
        except requests.RequestException as exc:
            latency = int((time.perf_counter() - start) * 1000)
            print(f"[ERROR] Request failed: {exc}")
            return SendResult(code_got = None,
                              status="Fail",
                              code_expected = None,
                              latency = latency)
        
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

    def send(self, item: PayloadEnvelope) -> SendResult:
        # Not Implemented!
        print ("MQTT Sim not implemented at this stage!")
        return self.mock_send_result