import copy
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .authentication import TOKEN_ENVIRONMENT_VARIABLE
from .constants import SUPPORTED_EVENTS
from .models import MoodleEvent


User = get_user_model()


class MoodleEventEndpointTests(TestCase):
    token = "test-webhook-token"

    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {TOKEN_ENVIRONMENT_VARIABLE: self.token},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.url = reverse("moodle_integration:events")
        self.payload = {
            "schema_version": 1,
            "event_id": "prueba-001",
            "event": r"core\event\user_created",
            "action": "created",
            "occurred_at": "2026-08-12T03:30:00Z",
            "site_url": "https://169.58.128.68",
            "actor_user_id": 2,
            "resource": {"user": {"id": 25}},
        }

    def post_event(self, payload=None, token=None, **extra):
        if payload is None:
            payload = self.payload
        if token is None:
            token = self.token
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            **extra,
        )

    def test_route_matches_the_plugin_contract(self):
        self.assertEqual(self.url, "/som/moodle_integration/events/")

    def test_post_requires_a_valid_bearer_token(self):
        missing_response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )
        wrong_response = self.post_event(token="incorrect-token")

        self.assertEqual(missing_response.status_code, 401)
        self.assertEqual(missing_response.headers["WWW-Authenticate"], "Bearer")
        self.assertEqual(wrong_response.status_code, 401)
        self.assertEqual(MoodleEvent.objects.count(), 0)

    def test_missing_server_token_returns_a_retryable_error(self):
        with patch.dict(os.environ, {TOKEN_ENVIRONMENT_VARIABLE: ""}):
            response = self.post_event()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(MoodleEvent.objects.count(), 0)

    def test_valid_event_is_stored_with_audit_information(self):
        response = self.post_event(
            HTTP_X_FORWARDED_FOR="203.0.113.10",
            HTTP_USER_AGENT="Moodle SOM Observer",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "received")

        event = MoodleEvent.objects.get()
        self.assertEqual(event.event_id, self.payload["event_id"])
        self.assertEqual(event.event_name, self.payload["event"])
        self.assertEqual(event.payload, self.payload)
        self.assertEqual(event.resource, self.payload["resource"])
        self.assertEqual(event.source_ip, "127.0.0.1")
        self.assertEqual(event.forwarded_for, "203.0.113.10")
        self.assertEqual(event.user_agent, "Moodle SOM Observer")
        self.assertEqual(event.delivery_count, 1)
        self.assertEqual(
            event.processing_status,
            MoodleEvent.ProcessingStatus.RECEIVED,
        )
        self.assertEqual(event.processing_attempts, 0)
        self.assertIsNone(event.processed_at)

    def test_duplicate_event_returns_200_and_is_not_stored_twice(self):
        first_response = self.post_event()
        event = MoodleEvent.objects.get()
        first_received_at = event.last_received_at

        duplicate_payload = copy.deepcopy(self.payload)
        duplicate_payload["resource"]["user"]["username"] = "changed"

        second_response = self.post_event(payload=duplicate_payload)
        event.refresh_from_db()

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["status"], "duplicate")
        self.assertEqual(MoodleEvent.objects.count(), 1)
        self.assertEqual(event.delivery_count, 2)
        self.assertGreaterEqual(event.last_received_at, first_received_at)
        self.assertEqual(event.payload, self.payload)

    def test_all_supported_events_are_accepted(self):
        for index, (event_name, contract) in enumerate(
            SUPPORTED_EVENTS.items(),
            start=1,
        ):
            with self.subTest(event_name=event_name):
                payload = copy.deepcopy(self.payload)
                payload["event_id"] = f"event-{index}"
                payload["event"] = event_name
                payload["action"] = contract["action"]
                payload["resource"] = {
                    resource_name: {"id": index}
                    for resource_name in contract["resources"]
                }

                response = self.post_event(payload=payload)

                self.assertEqual(response.status_code, 201)

        self.assertEqual(MoodleEvent.objects.count(), len(SUPPORTED_EVENTS))

    def test_missing_required_field_is_rejected(self):
        for field_name in (
            "schema_version",
            "event_id",
            "event",
            "action",
            "occurred_at",
            "site_url",
            "actor_user_id",
            "resource",
        ):
            with self.subTest(field_name=field_name):
                payload = copy.deepcopy(self.payload)
                payload.pop(field_name)

                response = self.post_event(payload=payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn(field_name, response.json()["errors"])

        self.assertEqual(MoodleEvent.objects.count(), 0)

    def test_unsupported_schema_event_and_inconsistent_action_are_rejected(self):
        invalid_values = (
            ("schema_version", 2),
            ("schema_version", True),
            ("event", r"core\event\course_created"),
            ("action", "deleted"),
            ("occurred_at", "2026-08-12T03:30:00"),
            ("site_url", "not-a-url"),
            ("actor_user_id", -1),
        )

        for field_name, value in invalid_values:
            with self.subTest(field_name=field_name, value=value):
                payload = copy.deepcopy(self.payload)
                payload[field_name] = value

                response = self.post_event(payload=payload)

                self.assertEqual(response.status_code, 400)
                self.assertIn(field_name, response.json()["errors"])

        self.assertEqual(MoodleEvent.objects.count(), 0)

    def test_enrolment_event_requires_enrolment_user_and_course(self):
        payload = copy.deepcopy(self.payload)
        payload.update(
            {
                "event": r"core\event\user_enrolment_created",
                "action": "created",
                "resource": {
                    "enrolment": {"id": 10},
                    "user": {"id": 25},
                },
            }
        )

        response = self.post_event(payload=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("resource.course", response.json()["errors"])
        self.assertEqual(MoodleEvent.objects.count(), 0)

    def test_malformed_non_object_and_non_standard_json_are_rejected(self):
        malformed_response = self.client.post(
            self.url,
            data="{",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        list_response = self.client.post(
            self.url,
            data="[]",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        nan_response = self.client.post(
            self.url,
            data='{"schema_version": NaN}',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(malformed_response.status_code, 400)
        self.assertEqual(list_response.status_code, 400)
        self.assertEqual(nan_response.status_code, 400)
        self.assertEqual(MoodleEvent.objects.count(), 0)

    def test_non_json_and_non_post_requests_are_rejected(self):
        content_type_response = self.client.post(
            self.url,
            data="payload",
            content_type="text/plain",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        method_response = self.client.get(self.url)

        self.assertEqual(content_type_response.status_code, 400)
        self.assertEqual(method_response.status_code, 405)

    def test_moodle_can_post_without_a_csrf_cookie(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 201)


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class MoodleEventAdminTests(TestCase):
    def test_superuser_can_audit_events_in_django_admin(self):
        admin_user = User.objects.create_superuser(
            username="moodle-auditor",
            email="auditor@example.com",
            password="password123",
        )
        event = MoodleEvent.objects.create(
            event_id="audit-001",
            schema_version=1,
            event_name=r"core\event\user_updated",
            action="updated",
            occurred_at="2026-08-12T03:30:00Z",
            site_url="https://169.58.128.68",
            actor_user_id=2,
            resource={"user": {"id": 25}},
            payload={"event_id": "audit-001"},
        )
        self.client.force_login(admin_user)

        list_response = self.client.get(
            reverse("admin:moodle_integration_moodleevent_changelist")
        )
        detail_response = self.client.get(
            reverse(
                "admin:moodle_integration_moodleevent_change",
                args=[event.pk],
            )
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, event.event_id)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, event.event_id)
