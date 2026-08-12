import ipaddress

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import MoodleEvent, MoodleUser


USER_FIELD_MAPPING = {
    "username": "username",
    "idnumber": "idnumber",
    "firstname": "first_name",
    "lastname": "last_name",
    "email": "email",
}

USER_DELETED_EVENT = r"core\event\user_deleted"


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


def _moodle_flag(value):
    if value is None:
        return None
    return bool(value)


def synchronize_user(event):
    user_payload = event.resource["user"]
    profile_defaults = {
        target_name: user_payload.get(source_name) or ""
        for source_name, target_name in USER_FIELD_MAPPING.items()
    }
    incoming_suspended = _moodle_flag(user_payload.get("suspended"))
    incoming_deleted = _moodle_flag(user_payload.get("deleted"))
    deleted_by_event = event.event_name == USER_DELETED_EVENT
    is_deleted = deleted_by_event or bool(incoming_deleted)
    is_suspended = is_deleted or bool(incoming_suspended)

    moodle_user, created = MoodleUser.objects.select_for_update().get_or_create(
        site_url=event.site_url,
        moodle_user_id=user_payload["id"],
        defaults={
            **profile_defaults,
            "raw_profile": user_payload,
            "is_suspended": is_suspended,
            "is_deleted": is_deleted,
            "suspended_at": event.occurred_at if is_suspended else None,
            "deleted_at": event.occurred_at if is_deleted else None,
            "last_seen_at": event.occurred_at,
            "last_event": event,
        },
    )

    if created or event.occurred_at < moodle_user.last_seen_at:
        return moodle_user, created

    for source_name, target_name in USER_FIELD_MAPPING.items():
        value = user_payload.get(source_name)
        if value is not None:
            setattr(moodle_user, target_name, value)

    merged_profile = dict(moodle_user.raw_profile)
    merged_profile.update(
        {key: value for key, value in user_payload.items() if value is not None}
    )
    moodle_user.raw_profile = merged_profile

    if incoming_suspended is not None:
        moodle_user.is_suspended = incoming_suspended
        moodle_user.suspended_at = (
            event.occurred_at if incoming_suspended else None
        )

    if is_deleted:
        moodle_user.is_deleted = True
        moodle_user.deleted_at = moodle_user.deleted_at or event.occurred_at
        moodle_user.is_suspended = True
        moodle_user.suspended_at = moodle_user.suspended_at or event.occurred_at
    elif moodle_user.is_deleted:
        moodle_user.is_suspended = True
        moodle_user.suspended_at = moodle_user.suspended_at or event.occurred_at

    moodle_user.last_seen_at = event.occurred_at
    moodle_user.last_event = event
    moodle_user.save()
    return moodle_user, False


@transaction.atomic
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
    else:
        synchronize_user(event)

    return event, created
