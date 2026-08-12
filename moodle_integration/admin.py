from django.contrib import admin

from .models import MoodleEvent


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
