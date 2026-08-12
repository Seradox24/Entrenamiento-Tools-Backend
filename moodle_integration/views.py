import json

from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .authentication import bearer_token_matches, get_webhook_token
from .constants import MAX_PAYLOAD_SIZE
from .services import request_audit_data, store_event
from .validation import EventPayloadValidationError, validate_event_payload


def _authentication_error():
    response = JsonResponse(
        {"status": "error", "detail": "Token Bearer ausente o incorrecto."},
        status=401,
    )
    response["WWW-Authenticate"] = "Bearer"
    return response


def _reject_json_constant(value):
    raise ValueError(f"Constante JSON no valida: {value}")


@csrf_exempt
@require_POST
def receive_event(request):
    expected_token = get_webhook_token()
    if not expected_token:
        return JsonResponse(
            {
                "status": "error",
                "detail": "La recepcion de eventos no esta configurada.",
            },
            status=503,
        )

    if not bearer_token_matches(
        request.headers.get("Authorization", ""),
        expected_token,
    ):
        return _authentication_error()

    if request.content_type != "application/json":
        return JsonResponse(
            {
                "status": "error",
                "errors": {"content_type": "Debe ser application/json."},
            },
            status=400,
        )

    try:
        raw_body = request.body
    except RequestDataTooBig:
        return JsonResponse(
            {"status": "error", "errors": {"payload": "El cuerpo es muy grande."}},
            status=400,
        )

    if len(raw_body) > MAX_PAYLOAD_SIZE:
        return JsonResponse(
            {"status": "error", "errors": {"payload": "El cuerpo es muy grande."}},
            status=400,
        )

    try:
        payload = json.loads(raw_body, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"status": "error", "errors": {"payload": "JSON invalido."}},
            status=400,
        )

    try:
        validated_payload = validate_event_payload(payload)
    except EventPayloadValidationError as error:
        return JsonResponse(
            {"status": "error", "errors": error.errors},
            status=400,
        )

    event, created = store_event(
        payload,
        validated_payload,
        request_audit_data(request),
    )

    return JsonResponse(
        {
            "status": "received" if created else "duplicate",
            "event_id": event.event_id,
        },
        status=201 if created else 200,
    )
