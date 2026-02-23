import json
from django.views import View
from django.http import JsonResponse


def get_json_body(body) -> dict:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {}
    return data