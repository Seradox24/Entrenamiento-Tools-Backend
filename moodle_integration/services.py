import ipaddress

from django.db.models import F
from django.utils import timezone

from .models import MoodleEvent


def _valid_source_ip(value):
    if not value:
        return None

    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def request_audit_data(request):
    return {
        "source_ip": _valid_source_ip(request.META.get("REMOTE_ADDR")),
        "forwarded_for": request.META.get("HTTP_X_FORWARDED_FOR", "")[:1024],
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:512],
    }


def store_event(payload, validated_payload, audit_data):
    event, created = MoodleEvent.objects.get_or_create(
        event_id=validated_payload["event_id"],
        defaults={
            "schema_version": validated_payload["schema_version"],
            "event_name": validated_payload["event_name"],
            "action": validated_payload["action"],
            "occurred_at": validated_payload["occurred_at"],
            "site_url": validated_payload["site_url"],
            "actor_user_id": validated_payload["actor_user_id"],
            "resource": validated_payload["resource"],
            "payload": payload,
            **audit_data,
        },
    )

    if not created:
        MoodleEvent.objects.filter(pk=event.pk).update(
            delivery_count=F("delivery_count") + 1,
            last_received_at=timezone.now(),
        )

    return event, created
