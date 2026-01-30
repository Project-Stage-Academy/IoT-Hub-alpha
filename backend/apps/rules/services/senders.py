from apps.notifications.models import NotificationDelivery
from datetime import datetime

class SendFailed(RuntimeError):
    """Raise this for transient delivery failures (network, provider down, etc.)."""
    ...

class NotificationSender:
    def __init__(self, notif: dict[str, str], msg: str):
        self.type: str = notif['type']
        self.name: str | None = notif.get('name', None)
        self.recipient_address: str = notif[self.get_recipient(notif)]
        self.msg: str = msg
        self.sent_at = datetime.now()
        
    def get_recipient(self, notif: dict[str, str]) -> str:
        type_map = {
            "sms": "phone",
            "email": "address",
            "webhook": "url"
        }
        return type_map[self.type]
    
    def send_once(self):
        sender_map = {
            "sms": self.sms_handler,
            "email": self.email_handler,
            "webhook": self.webhook_handler
        }
        sender = sender_map.get(self.type)
        if not sender:
            raise ValueError(f"Unknown channel: {self.type}")
        sender()
    
    def sms_handler(self):
        print(f"Sending SMS....to: {self.name} address: {self.recipient_address} msg: {self.msg}")
        
    def email_handler(self):
        print(f"sending email....to: {self.name} address: {self.recipient_address} msg: {self.msg}")
        
    def webhook_handler(self):
        print(f"Sending webhook....to: {self.name} address: {self.recipient_address} msg: {self.msg}")