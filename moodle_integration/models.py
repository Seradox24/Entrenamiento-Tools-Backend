from django.db import models
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
