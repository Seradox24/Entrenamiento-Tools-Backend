import hashlib
import ipaddress
import json
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta
from secrets import token_urlsafe
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    ExperienceLaunch,
    LauncherAccessToken,
    LauncherRefreshToken,
    LauncherSession,
)


MAX_MOODLE_RESPONSE_BYTES = 1024 * 1024
SENSITIVE_URL_PARAMETERS = {"token", "wstoken", "password"}


class MoodleAuthenticationError(Exception):
    pass


class MoodleConfigurationError(Exception):
    pass


class MoodleUnavailableError(Exception):
    pass


class MoodleProtocolError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


class InvalidLaunchTicketError(Exception):
    pass


@dataclass(frozen=True)
class MoodleAuthenticatedUser:
    site_url: str
    user_id: int
    username: str
    full_name: str
    profile_image_url: str


@dataclass(frozen=True)
class IssuedAccessToken:
    value: str
    expires_at: datetime


@dataclass(frozen=True)
class IssuedLauncherCredentials:
    launcher_session: LauncherSession
    access_token: IssuedAccessToken
    refresh_token: IssuedAccessToken


@dataclass(frozen=True)
class IssuedLaunchTicket:
    experience_launch: ExperienceLaunch
    value: str


@dataclass(frozen=True)
class IssuedExperienceToken:
    experience_launch: ExperienceLaunch
    value: str


def _configured_moodle():
    base_url = settings.MOODLE_BASE_URL.strip().rstrip("/")
    service = settings.MOODLE_SERVICE_SHORTNAME.strip()
    parsed_url = urlsplit(base_url)

    if not base_url or not service:
        raise MoodleConfigurationError(
            "La URL y el nombre corto del servicio Moodle son obligatorios."
        )
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise MoodleConfigurationError("MOODLE_BASE_URL no es una URL valida.")
    if parsed_url.query or parsed_url.fragment:
        raise MoodleConfigurationError(
            "MOODLE_BASE_URL no puede contener query string ni fragmento."
        )
    if parsed_url.scheme != "https" and not settings.DEBUG:
        raise MoodleConfigurationError(
            "Moodle debe usar HTTPS fuera del entorno de desarrollo."
        )
    if settings.MOODLE_HTTP_TIMEOUT_SECONDS <= 0:
        raise MoodleConfigurationError(
            "MOODLE_HTTP_TIMEOUT_SECONDS debe ser mayor que cero."
        )

    return base_url, service


def _decode_json_response(response):
    body = response.read(MAX_MOODLE_RESPONSE_BYTES + 1)
    if len(body) > MAX_MOODLE_RESPONSE_BYTES:
        raise MoodleProtocolError("La respuesta de Moodle es demasiado grande.")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MoodleProtocolError("Moodle no devolvio JSON valido.") from error

    if not isinstance(payload, dict):
        raise MoodleProtocolError("Moodle devolvio una estructura inesperada.")
    return payload


def _post_form_json(url, data):
    request = Request(
        url,
        data=urlencode(data).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SOM-Identity/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=settings.MOODLE_HTTP_TIMEOUT_SECONDS,
        ) as response:
            return _decode_json_response(response)
    except HTTPError as error:
        try:
            payload = _decode_json_response(error)
        except MoodleProtocolError:
            payload = None
        if isinstance(payload, dict) and payload.get("errorcode") == "invalidlogin":
            raise MoodleAuthenticationError from error
        raise MoodleUnavailableError("Moodle rechazo la solicitud HTTP.") from error
    except (URLError, TimeoutError, socket.timeout) as error:
        raise MoodleUnavailableError("No fue posible conectar con Moodle.") from error


def _same_moodle_site(configured_url, returned_url):
    configured = urlsplit(configured_url)
    returned = urlsplit(returned_url)
    return (
        configured.scheme.lower(),
        configured.netloc.lower(),
        configured.path.rstrip("/"),
    ) == (
        returned.scheme.lower(),
        returned.netloc.lower(),
        returned.path.rstrip("/"),
    )


def _safe_profile_image_url(value, site_url):
    if not isinstance(value, str) or not value:
        return ""

    parsed = urlsplit(value)
    site = urlsplit(site_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if (parsed.scheme.lower(), parsed.netloc.lower()) != (
        site.scheme.lower(),
        site.netloc.lower(),
    ):
        return ""
    if any(
        key.lower() in SENSITIVE_URL_PARAMETERS
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        return ""
    return value


def _required_text(payload, field_name, max_length):
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise MoodleProtocolError(
            f"Moodle no devolvio un valor valido para {field_name}."
        )
    return value[:max_length]


def authenticate_with_moodle(username, password):
    base_url, service = _configured_moodle()
    login_payload = _post_form_json(
        urljoin(f"{base_url}/", "login/token.php"),
        {
            "username": username,
            "password": password,
            "service": service,
        },
    )

    if login_payload.get("errorcode") == "invalidlogin":
        raise MoodleAuthenticationError
    moodle_token = login_payload.get("token")
    if not isinstance(moodle_token, str) or not moodle_token:
        if login_payload.get("error") or login_payload.get("errorcode"):
            raise MoodleConfigurationError(
                "Moodle no pudo emitir un token para el servicio configurado."
            )
        raise MoodleProtocolError("Moodle no devolvio un token valido.")

    site_payload = _post_form_json(
        urljoin(f"{base_url}/", "webservice/rest/server.php"),
        {
            "wstoken": moodle_token,
            "wsfunction": "core_webservice_get_site_info",
            "moodlewsrestformat": "json",
        },
    )

    if site_payload.get("exception") or site_payload.get("errorcode"):
        raise MoodleConfigurationError(
            "El token no puede consultar core_webservice_get_site_info."
        )

    site_url = site_payload.get("siteurl")
    user_id = site_payload.get("userid")
    if not isinstance(site_url, str) or not _same_moodle_site(base_url, site_url):
        raise MoodleProtocolError(
            "La URL informada por Moodle no coincide con MOODLE_BASE_URL."
        )
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise MoodleProtocolError("Moodle no devolvio un ID de usuario valido.")

    return MoodleAuthenticatedUser(
        site_url=site_url.rstrip("/"),
        user_id=user_id,
        username=_required_text(site_payload, "username", 255),
        full_name=_required_text(site_payload, "fullname", 511),
        profile_image_url=_safe_profile_image_url(
            site_payload.get("userpictureurl"),
            site_url,
        ),
    )


def token_digest(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _valid_ip(value):
    try:
        return str(ipaddress.ip_address(value))
    except (TypeError, ValueError):
        return None


def _positive_setting(name):
    value = getattr(settings, name)
    if value <= 0:
        raise MoodleConfigurationError(f"{name} debe ser mayor que cero.")
    return value


def _new_token(prefix):
    return f"{prefix}{token_urlsafe(32)}"


def _issue_launcher_access_token(launcher_session, now=None):
    now = now or timezone.now()
    ttl_seconds = _positive_setting("IDENTITY_ACCESS_TOKEN_TTL_SECONDS")
    expires_at = min(
        now + timedelta(seconds=ttl_seconds),
        launcher_session.expires_at,
    )
    for _attempt in range(3):
        value = _new_token("som_la_")
        try:
            with transaction.atomic():
                LauncherAccessToken.objects.create(
                    launcher_session=launcher_session,
                    token_digest=token_digest(value),
                    expires_at=expires_at,
                )
        except IntegrityError:
            continue
        return IssuedAccessToken(value=value, expires_at=expires_at)

    raise RuntimeError("No fue posible generar un token de acceso unico.")


def _issue_launcher_refresh_token(launcher_session, now=None):
    now = now or timezone.now()
    for _attempt in range(3):
        value = _new_token("som_lr_")
        try:
            with transaction.atomic():
                refresh_token = LauncherRefreshToken.objects.create(
                    launcher_session=launcher_session,
                    token_digest=token_digest(value),
                    expires_at=launcher_session.expires_at,
                )
        except IntegrityError:
            continue
        return (
            refresh_token,
            IssuedAccessToken(value=value, expires_at=launcher_session.expires_at),
        )

    raise RuntimeError("No fue posible generar un token de renovacion unico.")


@transaction.atomic
def issue_launcher_session(moodle_user, source_ip=None, user_agent=""):
    now = timezone.now()
    refresh_ttl = _positive_setting("IDENTITY_REFRESH_TOKEN_TTL_SECONDS")
    launcher_session = LauncherSession.objects.create(
        moodle_user=moodle_user,
        expires_at=now + timedelta(seconds=refresh_ttl),
        source_ip=_valid_ip(source_ip),
        user_agent=(user_agent or "")[:512],
    )
    access_token = _issue_launcher_access_token(launcher_session, now)
    _refresh_record, refresh_token = _issue_launcher_refresh_token(
        launcher_session,
        now,
    )
    return IssuedLauncherCredentials(
        launcher_session=launcher_session,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@transaction.atomic
def revoke_launcher_session(launcher_session, now=None):
    now = now or timezone.now()
    LauncherSession.objects.filter(
        pk=launcher_session.pk,
        revoked_at__isnull=True,
    ).update(revoked_at=now)
    LauncherAccessToken.objects.filter(
        launcher_session=launcher_session,
        revoked_at__isnull=True,
    ).update(revoked_at=now)
    LauncherRefreshToken.objects.filter(
        launcher_session=launcher_session,
        revoked_at__isnull=True,
    ).update(revoked_at=now)
    ExperienceLaunch.objects.filter(
        launcher_session=launcher_session,
        closed_at__isnull=True,
    ).update(
        closed_at=now,
        close_reason=ExperienceLaunch.CloseReason.LOGOUT,
    )
    launcher_session.revoked_at = now


def rotate_launcher_refresh_token(raw_token):
    if not isinstance(raw_token, str) or not raw_token.startswith("som_lr_"):
        raise InvalidRefreshTokenError

    invalidated_session = False
    credentials = None
    with transaction.atomic():
        refresh_token = (
            LauncherRefreshToken.objects.select_for_update()
            .select_related("launcher_session__moodle_user")
            .filter(token_digest=token_digest(raw_token))
            .first()
        )
        if refresh_token is None:
            raise InvalidRefreshTokenError

        launcher_session = refresh_token.launcher_session
        now = timezone.now()
        moodle_user = launcher_session.moodle_user
        if (
            refresh_token.used_at is not None
            or refresh_token.revoked_at is not None
            or refresh_token.expires_at <= now
            or launcher_session.expires_at <= now
            or launcher_session.revoked_at is not None
            or moodle_user.is_suspended
            or moodle_user.is_deleted
        ):
            revoke_launcher_session(launcher_session, now)
            invalidated_session = True
        else:
            refresh_token.used_at = now
            refresh_token.save(update_fields=("used_at",))
            replacement_record, replacement = _issue_launcher_refresh_token(
                launcher_session,
                now,
            )
            refresh_token.replaced_by = replacement_record
            refresh_token.save(update_fields=("replaced_by",))
            access_token = _issue_launcher_access_token(launcher_session, now)
            credentials = IssuedLauncherCredentials(
                launcher_session=launcher_session,
                access_token=access_token,
                refresh_token=replacement,
            )

    if invalidated_session:
        raise InvalidRefreshTokenError
    return credentials


def resolve_launcher_access_token(raw_token):
    if not isinstance(raw_token, str) or not raw_token.startswith("som_la_"):
        return None

    now = timezone.now()
    access_token = (
        LauncherAccessToken.objects.select_related(
            "launcher_session__moodle_user"
        )
        .filter(
            token_digest=token_digest(raw_token),
            revoked_at__isnull=True,
            expires_at__gt=now,
            launcher_session__revoked_at__isnull=True,
            launcher_session__expires_at__gt=now,
            launcher_session__moodle_user__is_suspended=False,
            launcher_session__moodle_user__is_deleted=False,
        )
        .first()
    )
    if access_token is None:
        return None

    LauncherAccessToken.objects.filter(pk=access_token.pk).update(
        last_used_at=now
    )
    access_token.last_used_at = now
    return access_token


@transaction.atomic
def issue_launch_ticket(launcher_session, application_id):
    ticket_ttl = _positive_setting("IDENTITY_LAUNCH_TICKET_TTL_SECONDS")
    now = timezone.now()
    locked_session = (
        LauncherSession.objects.select_for_update()
        .select_related("moodle_user")
        .get(pk=launcher_session.pk)
    )
    if not locked_session.is_active:
        raise InvalidRefreshTokenError

    ExperienceLaunch.objects.filter(
        launcher_session=locked_session,
        application_id=application_id,
        closed_at__isnull=True,
    ).update(
        closed_at=now,
        close_reason=ExperienceLaunch.CloseReason.REPLACED,
    )

    for _attempt in range(3):
        value = _new_token("som_lt_")
        try:
            with transaction.atomic():
                experience_launch = ExperienceLaunch.objects.create(
                    launcher_session=locked_session,
                    moodle_user=locked_session.moodle_user,
                    application_id=application_id,
                    ticket_digest=token_digest(value),
                    ticket_expires_at=now + timedelta(seconds=ticket_ttl),
                )
        except IntegrityError:
            continue
        return IssuedLaunchTicket(
            experience_launch=experience_launch,
            value=value,
        )

    raise RuntimeError("No fue posible generar un ticket de lanzamiento unico.")


@transaction.atomic
def exchange_launch_ticket(launch_id, raw_ticket):
    if not isinstance(raw_ticket, str) or not raw_ticket.startswith("som_lt_"):
        raise InvalidLaunchTicketError

    experience_launch = (
        ExperienceLaunch.objects.select_for_update()
        .select_related("launcher_session", "moodle_user")
        .filter(pk=launch_id, ticket_digest=token_digest(raw_ticket))
        .first()
    )
    if experience_launch is None:
        raise InvalidLaunchTicketError

    now = timezone.now()
    if (
        experience_launch.ticket_used_at is not None
        or experience_launch.ticket_expires_at <= now
        or experience_launch.closed_at is not None
        or experience_launch.launcher_session.revoked_at is not None
        or experience_launch.launcher_session.expires_at <= now
        or experience_launch.moodle_user.is_suspended
        or experience_launch.moodle_user.is_deleted
    ):
        raise InvalidLaunchTicketError

    idle_ttl = _positive_setting("IDENTITY_XAPI_IDLE_TTL_SECONDS")
    max_ttl = _positive_setting("IDENTITY_XAPI_MAX_TTL_SECONDS")
    if idle_ttl > max_ttl:
        raise MoodleConfigurationError(
            "IDENTITY_XAPI_IDLE_TTL_SECONDS no puede superar "
            "IDENTITY_XAPI_MAX_TTL_SECONDS."
        )

    for _attempt in range(3):
        value = _new_token("som_xapi_")
        digest = token_digest(value)
        if not ExperienceLaunch.objects.filter(xapi_token_digest=digest).exists():
            break
    else:
        raise RuntimeError("No fue posible generar un token xAPI unico.")

    experience_launch.ticket_used_at = now
    experience_launch.xapi_token_digest = digest
    experience_launch.activated_at = now
    experience_launch.last_activity_at = now
    experience_launch.absolute_expires_at = now + timedelta(seconds=max_ttl)
    experience_launch.save(
        update_fields=(
            "ticket_used_at",
            "xapi_token_digest",
            "activated_at",
            "last_activity_at",
            "absolute_expires_at",
        )
    )
    return IssuedExperienceToken(
        experience_launch=experience_launch,
        value=value,
    )


def resolve_experience_token(raw_token):
    if not isinstance(raw_token, str) or not raw_token.startswith("som_xapi_"):
        return None

    now = timezone.now()
    experience_launch = (
        ExperienceLaunch.objects.select_related("launcher_session", "moodle_user")
        .filter(
            xapi_token_digest=token_digest(raw_token),
            closed_at__isnull=True,
            activated_at__isnull=False,
            launcher_session__revoked_at__isnull=True,
            moodle_user__is_suspended=False,
            moodle_user__is_deleted=False,
        )
        .first()
    )
    if experience_launch is None:
        return None

    if (
        experience_launch.absolute_expires_at is None
        or experience_launch.absolute_expires_at <= now
    ):
        ExperienceLaunch.objects.filter(
            pk=experience_launch.pk,
            closed_at__isnull=True,
        ).update(
            closed_at=now,
            close_reason=ExperienceLaunch.CloseReason.MAX_DURATION,
        )
        return None

    if experience_launch.idle_expires_at <= now:
        ExperienceLaunch.objects.filter(
            pk=experience_launch.pk,
            closed_at__isnull=True,
        ).update(
            closed_at=now,
            close_reason=ExperienceLaunch.CloseReason.IDLE_TIMEOUT,
        )
        return None

    ExperienceLaunch.objects.filter(pk=experience_launch.pk).update(
        last_activity_at=now
    )
    experience_launch.last_activity_at = now
    return experience_launch


def close_experience(experience_launch):
    now = timezone.now()
    ExperienceLaunch.objects.filter(
        pk=experience_launch.pk,
        closed_at__isnull=True,
    ).update(
        closed_at=now,
        close_reason=ExperienceLaunch.CloseReason.APPLICATION_CLOSED,
    )
    experience_launch.closed_at = now
    experience_launch.close_reason = ExperienceLaunch.CloseReason.APPLICATION_CLOSED
