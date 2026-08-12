from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, URLValidator
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .constants import SCHEMA_VERSION, SUPPORTED_EVENTS


USER_STRING_FIELDS = {
    "username": 255,
    "idnumber": 255,
    "firstname": 255,
    "lastname": 255,
    "email": 254,
}


class EventPayloadValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("El payload del evento no es valido.")
        self.errors = errors


def _is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_resource_object(resource, name, errors):
    value = resource.get(name)
    field_name = f"resource.{name}"

    if not isinstance(value, dict):
        errors[field_name] = "Debe ser un objeto JSON."
        return

    resource_id = value.get("id")
    if not _is_integer(resource_id) or resource_id <= 0:
        errors[f"{field_name}.id"] = "Debe ser un entero positivo."

    if name != "user":
        return

    for source_name, max_length in USER_STRING_FIELDS.items():
        if source_name not in value or value[source_name] is None:
            continue
        if not isinstance(value[source_name], str):
            errors[f"{field_name}.{source_name}"] = "Debe ser un texto."
        elif len(value[source_name]) > max_length:
            errors[f"{field_name}.{source_name}"] = (
                f"No puede superar los {max_length} caracteres."
            )
        elif source_name == "email" and value[source_name]:
            try:
                EmailValidator()(value[source_name])
            except DjangoValidationError:
                errors[f"{field_name}.{source_name}"] = (
                    "Debe ser un correo electronico valido."
                )

    for source_name in ("suspended", "deleted"):
        if source_name not in value or value[source_name] is None:
            continue
        flag_value = value[source_name]
        if not isinstance(flag_value, (bool, int)) or flag_value not in (0, 1):
            errors[f"{field_name}.{source_name}"] = "Debe ser 0, 1 o booleano."


def validate_event_payload(payload):
    if not isinstance(payload, dict):
        raise EventPayloadValidationError(
            {"payload": "El cuerpo debe ser un objeto JSON."}
        )

    errors = {}

    schema_version = payload.get("schema_version")
    if not _is_integer(schema_version) or schema_version != SCHEMA_VERSION:
        errors["schema_version"] = (
            f"La unica version soportada actualmente es {SCHEMA_VERSION}."
        )

    event_id = payload.get("event_id")
    if not isinstance(event_id, str) or not event_id:
        errors["event_id"] = "Debe ser un texto no vacio."
    elif event_id != event_id.strip():
        errors["event_id"] = "No puede comenzar ni terminar con espacios."
    elif len(event_id) > 255:
        errors["event_id"] = "No puede superar los 255 caracteres."

    event_name = payload.get("event")
    event_contract = None
    if not isinstance(event_name, str) or not event_name:
        errors["event"] = "Debe ser un texto no vacio."
    else:
        event_contract = SUPPORTED_EVENTS.get(event_name)
        if event_contract is None:
            errors["event"] = "El evento no esta soportado."

    action = payload.get("action")
    if not isinstance(action, str) or not action:
        errors["action"] = "Debe ser un texto no vacio."
    elif event_contract and action != event_contract["action"]:
        errors["action"] = (
            f"La accion esperada para este evento es {event_contract['action']}."
        )

    occurred_at_value = payload.get("occurred_at")
    occurred_at = None
    if not isinstance(occurred_at_value, str) or not occurred_at_value:
        errors["occurred_at"] = "Debe ser una fecha ISO 8601."
    else:
        occurred_at = parse_datetime(occurred_at_value)
        if occurred_at is None or timezone.is_naive(occurred_at):
            errors["occurred_at"] = (
                "Debe ser una fecha ISO 8601 con zona horaria."
            )

    site_url = payload.get("site_url")
    if not isinstance(site_url, str) or not site_url:
        errors["site_url"] = "Debe ser una URL no vacia."
    else:
        try:
            URLValidator(schemes=("http", "https"))(site_url)
        except DjangoValidationError:
            errors["site_url"] = "Debe ser una URL HTTP o HTTPS valida."

    actor_user_id = payload.get("actor_user_id")
    if "actor_user_id" not in payload:
        errors["actor_user_id"] = "Este campo es obligatorio."
    elif actor_user_id is not None and (
        not _is_integer(actor_user_id) or actor_user_id < 0
    ):
        errors["actor_user_id"] = "Debe ser nulo o un entero no negativo."

    resource = payload.get("resource")
    if not isinstance(resource, dict):
        errors["resource"] = "Debe ser un objeto JSON."
    elif event_contract:
        for resource_name in event_contract["resources"]:
            _validate_resource_object(resource, resource_name, errors)

    if errors:
        raise EventPayloadValidationError(errors)

    return {
        "schema_version": schema_version,
        "event_id": event_id,
        "event_name": event_name,
        "action": action,
        "occurred_at": occurred_at,
        "site_url": site_url.rstrip("/"),
        "actor_user_id": actor_user_id,
        "resource": resource,
    }
