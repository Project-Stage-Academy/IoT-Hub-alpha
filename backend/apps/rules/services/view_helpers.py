import json
from apps.events.models import Event


def get_json_body(body) -> dict:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {}
    return data

def check_external_cooldown(external_id, cooldown):
    pass