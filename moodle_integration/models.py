from django.db import models
from django.db.models.deletion import ProtectedError
from django.utils import timezone


class MoodleEvent(models.Model):
    class ProcessingStatus(models.TextChoices):
        RECEIVED = "received", "Recibido"
        PROCESSING = "processing", "Procesando"
        PROCESSED = "processed", "Procesado"
        FAILED = "failed", "Fallido"

    event_id = models.CharField(max_length=255, unique=True)
    schema_version = models.PositiveSmallIntegerField()
    event_name = models.CharField(max_length=128)
    action = models.CharField(max_length=32)
    occurred_at = models.DateTimeField()
    site_url = models.URLField(max_length=2048)
    actor_user_id = models.BigIntegerField(null=True, blank=True)
    resource = models.JSONField()
    payload = models.JSONField()

    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_received_at = models.DateTimeField(default=timezone.now)
    delivery_count = models.PositiveIntegerField(default=1)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    forwarded_for = models.CharField(max_length=1024, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    processing_status = models.CharField(
        max_length=16,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.RECEIVED,
    )
    processing_attempts = models.PositiveIntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ("-received_at",)
        indexes = (
            models.Index(
                fields=("processing_status", "received_at"),
                name="moodle_evt_status_time",
            ),
            models.Index(
                fields=("event_name", "occurred_at"),
                name="moodle_evt_event_time",
            ),
        )
        verbose_name = "evento de Moodle"
        verbose_name_plural = "eventos de Moodle"

    def __str__(self):
        return f"{self.event_name} ({self.event_id})"


class NonDeletableMoodleUserQuerySet(models.QuerySet):
    def delete(self):
        raise ProtectedError(
            "Los usuarios sincronizados desde Moodle no se pueden eliminar.",
            self,
        )


class MoodleUser(models.Model):
    site_url = models.URLField(max_length=2048)
    moodle_user_id = models.PositiveBigIntegerField()

    username = models.CharField(max_length=255, blank=True)
    idnumber = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    raw_profile = models.JSONField(default=dict)

    is_suspended = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()
    last_synced_at = models.DateTimeField(auto_now=True)
    last_event = models.ForeignKey(
        MoodleEvent,
        on_delete=models.PROTECT,
        related_name="synchronized_users",
    )

    objects = NonDeletableMoodleUserQuerySet.as_manager()

    class Meta:
        ordering = ("site_url", "moodle_user_id")
        constraints = (
            models.UniqueConstraint(
                fields=("site_url", "moodle_user_id"),
                name="moodle_user_site_id_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(is_deleted=False)
                | models.Q(is_suspended=True),
                name="moodle_user_deleted_suspended",
            ),
        )
        indexes = (
            models.Index(
                fields=("site_url", "is_suspended"),
                name="moodle_user_status_idx",
            ),
            models.Index(
                fields=("site_url", "last_seen_at"),
                name="moodle_user_seen_idx",
            ),
        )
        verbose_name = "usuario de Moodle"
        verbose_name_plural = "usuarios de Moodle"

    def delete(self, using=None, keep_parents=False):
        raise ProtectedError(
            "Los usuarios sincronizados desde Moodle no se pueden eliminar.",
            [self],
        )

    @property
    def full_name(self):
        return " ".join(
            part for part in (self.first_name, self.last_name) if part
        )

    def __str__(self):
        return self.username or f"Moodle user {self.moodle_user_id}"
