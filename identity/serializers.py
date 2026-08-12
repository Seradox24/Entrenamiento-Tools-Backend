from rest_framework import serializers


class MoodleLoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=255,
        allow_blank=False,
        trim_whitespace=True,
    )
    password = serializers.CharField(
        max_length=1024,
        allow_blank=False,
        trim_whitespace=False,
        write_only=True,
    )


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(
        max_length=512,
        allow_blank=False,
        trim_whitespace=False,
        write_only=True,
    )


class ExperienceLaunchSerializer(serializers.Serializer):
    application_id = serializers.RegexField(
        regex=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
        max_length=128,
    )


class LaunchTicketExchangeSerializer(serializers.Serializer):
    launch_id = serializers.UUIDField()
    launch_ticket = serializers.CharField(
        max_length=512,
        allow_blank=False,
        trim_whitespace=False,
        write_only=True,
    )
