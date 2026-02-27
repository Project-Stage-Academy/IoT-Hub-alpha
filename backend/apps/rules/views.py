from __future__ import annotations
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from apps.rules.services.view_helpers import get_json_body
from apps.rules.services.inbound_transform import TransformEngine, TransformationError
from apps.rules.services.external_rule_producer import ExternalProducer, ProducerError


@method_decorator(csrf_exempt, name="dispatch")
class ExternalRule(View):
    """
    Recieve external event and generates an internally complient instance
    of event.topic
    """

    def post(self, request: HttpRequest, inbound_id) -> JsonResponse:

        engine = TransformEngine()

        parsed_body = get_json_body(request.body)
        if not parsed_body:
            return JsonResponse({"error": "Empty body"}, status=400)

        try:
            transformed = engine.transform(inbound_id, parsed_body)
            ExternalProducer().produce(transformed.model_dump())
        except TransformationError as e:
            return JsonResponse({"error": f"Failed: {e}"}, status=400)
        except ProducerError as e:
            return JsonResponse({"error": f"Producer error {e}"}, status=400)

        return JsonResponse(transformed.model_dump(), status=202)
