from django.contrib import admin
from django.utils.html import format_html

from .models import MoodleEvent, MoodleUser


@admin.register(MoodleEvent)
class MoodleEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_id",
        "event_name",
        "action",
        "site_url",
        "processing_status",
        "delivery_count",
        "occurred_at",
        "received_at",
    )
    list_filter = ("event_name", "processing_status", "schema_version")
    search_fields = ("event_id", "site_url", "actor_user_id")
    date_hierarchy = "received_at"
    ordering = ("-received_at",)
    readonly_fields = tuple(
        field.name for field in MoodleEvent._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MoodleUser)
class MoodleUserAdmin(admin.ModelAdmin):
    list_display = (
        "moodle_user_id",
        "username",
        "full_name",
        "email",
        "site_url",
        "suspension_status",
        "deletion_status",
        "last_seen_at",
    )
    list_filter = ("site_url", "is_suspended", "is_deleted")
    search_fields = (
        "moodle_user_id",
        "username",
        "idnumber",
        "first_name",
        "last_name",
        "email",
    )
    ordering = ("site_url", "moodle_user_id")
    readonly_fields = (
        "id",
        "site_url",
        "moodle_user_id",
        "username",
        "idnumber",
        "first_name",
        "last_name",
        "email",
        "raw_profile",
        "suspension_status",
        "deletion_status",
        "suspended_at",
        "deleted_at",
        "first_seen_at",
        "last_seen_at",
        "last_synced_at",
        "last_event",
    )

    class Media:
        css = {"all": ("moodle_integration/admin.css",)}

    @staticmethod
    def _status_badge(label, danger):
        modifier = "danger" if danger else "ok"
        return format_html(
            '<span class="moodle-status moodle-status--{}">{}</span>',
            modifier,
            label,
        )

    @admin.display(description="Suspension", ordering="is_suspended")
    def suspension_status(self, obj):
        if obj.is_suspended:
            return self._status_badge("Suspendido", danger=True)
        return self._status_badge("Activo", danger=False)

    @admin.display(description="Eliminacion", ordering="is_deleted")
    def deletion_status(self, obj):
        if obj.is_deleted:
            return self._status_badge("Eliminado", danger=True)
        return self._status_badge("No eliminado", danger=False)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
