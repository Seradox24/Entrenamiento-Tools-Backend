import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class LauncherSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    moodle_user = models.ForeignKey(
        "moodle_integration.MoodleUser",
        on_delete=models.PROTECT,
        related_name="launcher_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("moodle_user", "expires_at"),
                name="identity_session_user_exp",
            ),
        )
        verbose_name = "sesion del launcher"
        verbose_name_plural = "sesiones del launcher"

    @property
    def is_active(self):
        return (
            self.revoked_at is None
            and self.expires_at > timezone.now()
            and not self.moodle_user.is_suspended
            and not self.moodle_user.is_deleted
        )

    def __str__(self):
        return f"Launcher session {self.id}"


class LauncherAccessToken(models.Model):
    launcher_session = models.ForeignKey(
        LauncherSession,
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("launcher_session", "expires_at"),
                name="identity_access_sess_exp",
            ),
        )
        verbose_name = "token de acceso del launcher"
        verbose_name_plural = "tokens de acceso del launcher"


class LauncherRefreshToken(models.Model):
    launcher_session = models.ForeignKey(
        LauncherSession,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
    )
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.OneToOneField(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaces",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("launcher_session", "expires_at"),
                name="identity_refresh_sess_exp",
            ),
        )
        verbose_name = "token de renovacion del launcher"
        verbose_name_plural = "tokens de renovacion del launcher"


class ExperienceLaunch(models.Model):
    class CloseReason(models.TextChoices):
        APPLICATION_CLOSED = "application_closed", "Aplicacion cerrada"
        REPLACED = "replaced", "Reemplazado por otro lanzamiento"
        LOGOUT = "logout", "Sesion cerrada"
        IDLE_TIMEOUT = "idle_timeout", "Tiempo de inactividad agotado"
        MAX_DURATION = "max_duration", "Duracion maxima agotada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    launcher_session = models.ForeignKey(
        LauncherSession,
        on_delete=models.PROTECT,
        related_name="experience_launches",
    )
    moodle_user = models.ForeignKey(
        "moodle_integration.MoodleUser",
        on_delete=models.PROTECT,
        related_name="experience_launches",
    )
    application_id = models.CharField(max_length=128)

    ticket_digest = models.CharField(max_length=64, unique=True, editable=False)
    ticket_expires_at = models.DateTimeField()
    ticket_used_at = models.DateTimeField(null=True, blank=True)

    xapi_token_digest = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True, db_index=True)
    absolute_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(
        max_length=32,
        choices=CloseReason.choices,
        blank=True,
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(
                fields=("launcher_session", "application_id", "closed_at"),
                name="identity_launch_sess_app",
            ),
        )
        verbose_name = "lanzamiento de experiencia"
        verbose_name_plural = "lanzamientos de experiencias"

    @property
    def idle_expires_at(self):
        if self.last_activity_at is None or self.absolute_expires_at is None:
            return None
        return min(
            self.last_activity_at
            + timedelta(seconds=settings.IDENTITY_XAPI_IDLE_TTL_SECONDS),
            self.absolute_expires_at,
        )

    @property
    def is_active(self):
        idle_expires_at = self.idle_expires_at
        return (
            self.closed_at is None
            and self.xapi_token_digest is not None
            and idle_expires_at is not None
            and idle_expires_at > timezone.now()
            and self.launcher_session.revoked_at is None
            and not self.moodle_user.is_suspended
            and not self.moodle_user.is_deleted
        )

    def __str__(self):
        return f"{self.application_id} ({self.id})"
