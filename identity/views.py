from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from moodle_integration.models import MoodleUser

from .authentication import (
    ExperienceTokenAuthentication,
    LauncherAccessAuthentication,
)
from .serializers import (
    ExperienceLaunchSerializer,
    LaunchTicketExchangeSerializer,
    MoodleLoginSerializer,
    RefreshTokenSerializer,
)
from .services import (
    InvalidLaunchTicketError,
    InvalidRefreshTokenError,
    MoodleAuthenticationError,
    MoodleConfigurationError,
    MoodleProtocolError,
    MoodleUnavailableError,
    authenticate_with_moodle,
    close_experience,
    exchange_launch_ticket,
    issue_launch_ticket,
    issue_launcher_session,
    revoke_launcher_session,
    rotate_launcher_refresh_token,
)
from .throttling import (
    IdentityLoginRateThrottle,
    LaunchTicketExchangeRateThrottle,
)


def _error_response(code, detail, status):
    return Response(
        {"status": "error", "code": code, "detail": detail},
        status=status,
    )


def _user_payload(moodle_user, username="", full_name="", profile_image_url=""):
    return {
        "moodle_user_id": moodle_user.moodle_user_id,
        "username": username or moodle_user.username,
        "name": full_name or moodle_user.full_name,
        "first_name": moodle_user.first_name,
        "last_name": moodle_user.last_name,
        "email": moodle_user.email,
        "profile_image_url": profile_image_url or None,
    }


def _launcher_credentials_payload(credentials):
    now = timezone.now()
    return {
        "launcher_session_id": str(credentials.launcher_session.id),
        "access_token": credentials.access_token.value,
        "token_type": "Bearer",
        "access_token_expires_in": max(
            0,
            int((credentials.access_token.expires_at - now).total_seconds()),
        ),
        "access_token_expires_at": credentials.access_token.expires_at.isoformat(),
        "refresh_token": credentials.refresh_token.value,
        "refresh_token_expires_in": max(
            0,
            int((credentials.refresh_token.expires_at - now).total_seconds()),
        ),
        "refresh_token_expires_at": credentials.refresh_token.expires_at.isoformat(),
    }


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
@throttle_classes([IdentityLoginRateThrottle])
def moodle_login(request):
    serializer = MoodleLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "status": "error",
                "code": "invalid_request",
                "errors": serializer.errors,
            },
            status=400,
        )

    try:
        authenticated_user = authenticate_with_moodle(
            serializer.validated_data["username"],
            serializer.validated_data["password"],
        )
    except MoodleAuthenticationError:
        return _error_response(
            "invalid_credentials",
            "Usuario o contrasena incorrectos.",
            401,
        )
    except MoodleConfigurationError:
        return _error_response(
            "identity_not_configured",
            "El inicio de sesion con Moodle no esta disponible.",
            503,
        )
    except MoodleUnavailableError:
        return _error_response(
            "moodle_unavailable",
            "Moodle no esta disponible en este momento.",
            503,
        )
    except MoodleProtocolError:
        return _error_response(
            "invalid_moodle_response",
            "Moodle devolvio una respuesta inesperada.",
            502,
        )

    try:
        moodle_user = MoodleUser.objects.get(
            site_url=authenticated_user.site_url,
            moodle_user_id=authenticated_user.user_id,
        )
    except MoodleUser.DoesNotExist:
        return _error_response(
            "identity_not_registered",
            "El usuario se autentico en Moodle, pero aun no esta registrado en SOM.",
            403,
        )

    if moodle_user.is_suspended or moodle_user.is_deleted:
        return _error_response(
            "identity_inactive",
            "La identidad de Moodle esta suspendida o eliminada en SOM.",
            403,
        )

    try:
        credentials = issue_launcher_session(
            moodle_user,
            source_ip=request.META.get("REMOTE_ADDR"),
            user_agent=request.headers.get("User-Agent", ""),
        )
    except MoodleConfigurationError:
        return _error_response(
            "identity_not_configured",
            "El inicio de sesion con Moodle no esta disponible.",
            503,
        )

    return Response(
        {
            "status": "ok",
            "user": _user_payload(
                moodle_user,
                authenticated_user.username,
                authenticated_user.full_name,
                authenticated_user.profile_image_url,
            ),
            **_launcher_credentials_payload(credentials),
        }
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
@throttle_classes([IdentityLoginRateThrottle])
def refresh_launcher_token(request):
    serializer = RefreshTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"status": "error", "code": "invalid_request", "errors": serializer.errors},
            status=400,
        )
    try:
        credentials = rotate_launcher_refresh_token(
            serializer.validated_data["refresh_token"]
        )
    except InvalidRefreshTokenError:
        return _error_response(
            "invalid_refresh_token",
            "El token de renovacion vencio, fue revocado o ya fue utilizado.",
            401,
        )
    except MoodleConfigurationError:
        return _error_response(
            "identity_not_configured",
            "La renovacion de sesion no esta disponible.",
            503,
        )

    return Response({"status": "ok", **_launcher_credentials_payload(credentials)})


@api_view(["POST"])
@authentication_classes([LauncherAccessAuthentication])
@permission_classes([IsAuthenticated])
def logout_launcher(request):
    revoke_launcher_session(request.auth.launcher_session)
    return Response({"status": "ok", "detail": "Sesion cerrada."})


@api_view(["POST"])
@authentication_classes([LauncherAccessAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def create_experience_launch(request):
    serializer = ExperienceLaunchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"status": "error", "code": "invalid_request", "errors": serializer.errors},
            status=400,
        )

    try:
        issued = issue_launch_ticket(
            request.auth.launcher_session,
            serializer.validated_data["application_id"],
        )
    except InvalidRefreshTokenError:
        return _error_response(
            "launcher_session_inactive",
            "La sesion del launcher ya no esta activa.",
            401,
        )

    launch = issued.experience_launch
    return Response(
        {
            "status": "ok",
            "launch_id": str(launch.id),
            "application_id": launch.application_id,
            "launch_ticket": issued.value,
            "ticket_expires_at": launch.ticket_expires_at.isoformat(),
        },
        status=201,
    )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
@throttle_classes([LaunchTicketExchangeRateThrottle])
def exchange_experience_launch(request):
    serializer = LaunchTicketExchangeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {"status": "error", "code": "invalid_request", "errors": serializer.errors},
            status=400,
        )

    try:
        issued = exchange_launch_ticket(
            serializer.validated_data["launch_id"],
            serializer.validated_data["launch_ticket"],
        )
    except InvalidLaunchTicketError:
        return _error_response(
            "invalid_launch_ticket",
            "El ticket vencio, ya fue utilizado o no pertenece al lanzamiento.",
            401,
        )
    except MoodleConfigurationError:
        return _error_response(
            "identity_not_configured",
            "No fue posible activar la experiencia.",
            503,
        )

    launch = issued.experience_launch
    return Response(
        {
            "status": "ok",
            "launch_id": str(launch.id),
            "application_id": launch.application_id,
            "user": _user_payload(launch.moodle_user),
            "xapi_access_token": issued.value,
            "token_type": "Bearer",
            "idle_timeout_seconds": settings.IDENTITY_XAPI_IDLE_TTL_SECONDS,
            "absolute_expires_at": launch.absolute_expires_at.isoformat(),
        }
    )


def _validate_experience_path(request, launch_id):
    if request.auth.id != launch_id:
        return _error_response(
            "launch_mismatch",
            "El token no pertenece al lanzamiento indicado.",
            403,
        )
    return None


@api_view(["POST"])
@authentication_classes([ExperienceTokenAuthentication])
@permission_classes([IsAuthenticated])
def experience_heartbeat(request, launch_id):
    error = _validate_experience_path(request, launch_id)
    if error:
        return error
    return Response(
        {
            "status": "ok",
            "launch_id": str(request.auth.id),
            "idle_expires_at": request.auth.idle_expires_at.isoformat(),
            "absolute_expires_at": request.auth.absolute_expires_at.isoformat(),
        }
    )


@api_view(["POST"])
@authentication_classes([ExperienceTokenAuthentication])
@permission_classes([IsAuthenticated])
def close_experience_launch(request, launch_id):
    error = _validate_experience_path(request, launch_id)
    if error:
        return error
    close_experience(request.auth)
    return Response({"status": "ok", "detail": "Experiencia cerrada."})
