import json
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from moodle_integration.models import MoodleEvent, MoodleUser

from .models import (
    ExperienceLaunch,
    LauncherAccessToken,
    LauncherRefreshToken,
    LauncherSession,
)
from .services import (
    MoodleAuthenticatedUser,
    MoodleAuthenticationError,
    authenticate_with_moodle,
    resolve_experience_token,
    resolve_launcher_access_token,
    token_digest,
)


MOODLE_SETTINGS = {
    "MOODLE_BASE_URL": "https://moodle.example.test",
    "MOODLE_SERVICE_SHORTNAME": "t_launcher",
    "MOODLE_HTTP_TIMEOUT_SECONDS": 3,
    "IDENTITY_ACCESS_TOKEN_TTL_SECONDS": 900,
    "IDENTITY_REFRESH_TOKEN_TTL_SECONDS": 43200,
    "IDENTITY_LAUNCH_TICKET_TTL_SECONDS": 60,
    "IDENTITY_XAPI_IDLE_TTL_SECONDS": 3600,
    "IDENTITY_XAPI_MAX_TTL_SECONDS": 28800,
}


class FakeHTTPResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


@override_settings(**MOODLE_SETTINGS)
class MoodleClientTests(SimpleTestCase):
    @patch("identity.services.urlopen")
    def test_authenticates_and_discards_moodle_token(self, mocked_urlopen):
        mocked_urlopen.side_effect = [
            FakeHTTPResponse(json.dumps({"token": "moodle-secret"}).encode()),
            FakeHTTPResponse(
                json.dumps(
                    {
                        "siteurl": "https://moodle.example.test",
                        "userid": 42,
                        "username": "student",
                        "fullname": "Student Example",
                        "userpictureurl": (
                            "https://moodle.example.test/pluginfile.php/42/user/icon/f1"
                        ),
                    }
                ).encode()
            ),
        ]

        user = authenticate_with_moodle("student", "secret password")

        self.assertEqual(user.user_id, 42)
        self.assertEqual(user.full_name, "Student Example")
        self.assertEqual(mocked_urlopen.call_count, 2)
        first_request = mocked_urlopen.call_args_list[0].args[0]
        second_request = mocked_urlopen.call_args_list[1].args[0]
        self.assertIn(b"service=t_launcher", first_request.data)
        self.assertIn(b"password=secret+password", first_request.data)
        self.assertIn(b"wstoken=moodle-secret", second_request.data)

    @patch("identity.services.urlopen")
    def test_rejects_invalid_moodle_credentials(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeHTTPResponse(
            json.dumps(
                {"error": "Invalid login", "errorcode": "invalidlogin"}
            ).encode()
        )

        with self.assertRaises(MoodleAuthenticationError):
            authenticate_with_moodle("student", "wrong")

    @patch("identity.services.urlopen")
    def test_does_not_return_an_image_url_containing_a_token(self, mocked_urlopen):
        mocked_urlopen.side_effect = [
            FakeHTTPResponse(json.dumps({"token": "moodle-secret"}).encode()),
            FakeHTTPResponse(
                json.dumps(
                    {
                        "siteurl": "https://moodle.example.test",
                        "userid": 42,
                        "username": "student",
                        "fullname": "Student Example",
                        "userpictureurl": (
                            "https://moodle.example.test/webservice/pluginfile.php"
                            "?token=moodle-secret&file=/42/icon"
                        ),
                    }
                ).encode()
            ),
        ]

        user = authenticate_with_moodle("student", "secret")

        self.assertEqual(user.profile_image_url, "")


@override_settings(**MOODLE_SETTINGS)
class IdentityEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        now = timezone.now()
        event = MoodleEvent.objects.create(
            event_id="identity-test-user-created",
            schema_version=1,
            event_name=r"core\event\user_created",
            action="created",
            occurred_at=now,
            site_url="https://moodle.example.test",
            actor_user_id=2,
            resource={"user": {"id": 42}},
            payload={},
        )
        self.moodle_user = MoodleUser.objects.create(
            site_url="https://moodle.example.test",
            moodle_user_id=42,
            username="student",
            first_name="Local",
            last_name="Student",
            email="student@example.test",
            last_seen_at=now,
            last_event=event,
        )
        self.authenticated_user = MoodleAuthenticatedUser(
            site_url="https://moodle.example.test",
            user_id=42,
            username="student",
            full_name="Moodle Student",
            profile_image_url=(
                "https://moodle.example.test/pluginfile.php/42/user/icon/f1"
            ),
        )

    def _login(self, authenticate):
        authenticate.return_value = self.authenticated_user
        response = self.client.post(
            reverse("identity:moodle-login"),
            {"username": "student", "password": "secret"},
            content_type="application/json",
            HTTP_USER_AGENT="Desktop Client/1.0",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _create_launch(self, access_token, application_id="simulator-one"):
        return self.client.post(
            reverse("identity:launch-create"),
            {"application_id": application_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

    def _exchange_launch(self, launch_payload):
        return self.client.post(
            reverse("identity:launch-exchange"),
            {
                "launch_id": launch_payload["launch_id"],
                "launch_ticket": launch_payload["launch_ticket"],
            },
            content_type="application/json",
        )

    @patch("identity.views.authenticate_with_moodle")
    def test_login_returns_profile_and_separate_launcher_tokens(self, authenticate):
        payload = self._login(authenticate)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["user"]["moodle_user_id"], 42)
        self.assertEqual(payload["user"]["name"], "Moodle Student")
        self.assertEqual(payload["user"]["first_name"], "Local")
        self.assertEqual(payload["user"]["email"], "student@example.test")
        self.assertTrue(payload["access_token"].startswith("som_la_"))
        self.assertTrue(payload["refresh_token"].startswith("som_lr_"))
        self.assertEqual(LauncherSession.objects.count(), 1)

        access = LauncherAccessToken.objects.get()
        refresh = LauncherRefreshToken.objects.get()
        self.assertEqual(access.token_digest, token_digest(payload["access_token"]))
        self.assertEqual(refresh.token_digest, token_digest(payload["refresh_token"]))
        self.assertNotEqual(access.token_digest, payload["access_token"])
        self.assertEqual(access.launcher_session.user_agent, "Desktop Client/1.0")

    @patch("identity.views.authenticate_with_moodle")
    def test_refresh_rotates_token_and_reuse_revokes_session(self, authenticate):
        login = self._login(authenticate)
        old_refresh = login["refresh_token"]

        response = self.client.post(
            reverse("identity:token-refresh"),
            {"refresh_token": old_refresh},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        refreshed = response.json()
        self.assertNotEqual(refreshed["refresh_token"], old_refresh)
        self.assertTrue(refreshed["access_token"].startswith("som_la_"))
        self.assertIsNotNone(
            LauncherRefreshToken.objects.get(
                token_digest=token_digest(old_refresh)
            ).used_at
        )

        reuse = self.client.post(
            reverse("identity:token-refresh"),
            {"refresh_token": old_refresh},
            content_type="application/json",
        )

        self.assertEqual(reuse.status_code, 401)
        self.assertEqual(reuse.json()["code"], "invalid_refresh_token")
        self.assertIsNotNone(LauncherSession.objects.get().revoked_at)
        self.assertIsNone(resolve_launcher_access_token(refreshed["access_token"]))

    @patch("identity.views.authenticate_with_moodle")
    def test_each_start_replaces_previous_launch_for_same_application(self, authenticate):
        login = self._login(authenticate)
        first = self._create_launch(login["access_token"])
        self.assertEqual(first.status_code, 201)
        first_exchange = self._exchange_launch(first.json())
        self.assertEqual(first_exchange.status_code, 200)
        old_xapi_token = first_exchange.json()["xapi_access_token"]

        second = self._create_launch(login["access_token"])

        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(second.json()["launch_id"], first.json()["launch_id"])
        old_launch = ExperienceLaunch.objects.get(pk=first.json()["launch_id"])
        self.assertEqual(old_launch.close_reason, ExperienceLaunch.CloseReason.REPLACED)
        self.assertIsNone(resolve_experience_token(old_xapi_token))

    @patch("identity.views.authenticate_with_moodle")
    def test_unreal_exchanges_ticket_once_for_xapi_token(self, authenticate):
        login = self._login(authenticate)
        launch = self._create_launch(login["access_token"]).json()

        response = self._exchange_launch(launch)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["xapi_access_token"].startswith("som_xapi_"))
        self.assertEqual(payload["user"]["moodle_user_id"], 42)
        self.assertEqual(payload["idle_timeout_seconds"], 3600)
        experience = ExperienceLaunch.objects.get(pk=launch["launch_id"])
        self.assertEqual(
            experience.xapi_token_digest,
            token_digest(payload["xapi_access_token"]),
        )

        reuse = self._exchange_launch(launch)
        self.assertEqual(reuse.status_code, 401)
        self.assertEqual(reuse.json()["code"], "invalid_launch_ticket")

    @patch("identity.views.authenticate_with_moodle")
    def test_heartbeat_keeps_active_experience_alive(self, authenticate):
        login = self._login(authenticate)
        launch = self._create_launch(login["access_token"]).json()
        exchanged = self._exchange_launch(launch).json()
        experience = ExperienceLaunch.objects.get(pk=launch["launch_id"])
        previous_activity = experience.last_activity_at

        response = self.client.post(
            reverse("identity:launch-heartbeat", args=(experience.id,)),
            HTTP_AUTHORIZATION=f"Bearer {exchanged['xapi_access_token']}",
        )

        self.assertEqual(response.status_code, 200)
        experience.refresh_from_db()
        self.assertGreaterEqual(experience.last_activity_at, previous_activity)
        self.assertIn("idle_expires_at", response.json())

    @patch("identity.views.authenticate_with_moodle")
    def test_close_experience_invalidates_xapi_token(self, authenticate):
        login = self._login(authenticate)
        launch = self._create_launch(login["access_token"]).json()
        xapi_token = self._exchange_launch(launch).json()["xapi_access_token"]

        response = self.client.post(
            reverse("identity:launch-close", args=(launch["launch_id"],)),
            HTTP_AUTHORIZATION=f"Bearer {xapi_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(resolve_experience_token(xapi_token))

    @patch("identity.views.authenticate_with_moodle")
    def test_logout_revokes_launcher_and_open_experiences(self, authenticate):
        login = self._login(authenticate)
        launch = self._create_launch(login["access_token"]).json()
        xapi_token = self._exchange_launch(launch).json()["xapi_access_token"]

        response = self.client.post(
            reverse("identity:logout"),
            HTTP_AUTHORIZATION=f"Bearer {login['access_token']}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(resolve_launcher_access_token(login["access_token"]))
        self.assertIsNone(resolve_experience_token(xapi_token))
        experience = ExperienceLaunch.objects.get(pk=launch["launch_id"])
        self.assertEqual(experience.close_reason, ExperienceLaunch.CloseReason.LOGOUT)

    @patch("identity.views.authenticate_with_moodle")
    def test_idle_xapi_token_is_rejected_and_closed(self, authenticate):
        login = self._login(authenticate)
        launch = self._create_launch(login["access_token"]).json()
        xapi_token = self._exchange_launch(launch).json()["xapi_access_token"]
        ExperienceLaunch.objects.filter(pk=launch["launch_id"]).update(
            last_activity_at=timezone.now() - timedelta(seconds=3601)
        )

        self.assertIsNone(resolve_experience_token(xapi_token))
        experience = ExperienceLaunch.objects.get(pk=launch["launch_id"])
        self.assertEqual(
            experience.close_reason,
            ExperienceLaunch.CloseReason.IDLE_TIMEOUT,
        )

    @patch("identity.views.authenticate_with_moodle")
    def test_login_rejects_invalid_credentials(self, authenticate):
        authenticate.side_effect = MoodleAuthenticationError

        response = self.client.post(
            reverse("identity:moodle-login"),
            {"username": "student", "password": "wrong"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "invalid_credentials")
        self.assertFalse(LauncherSession.objects.exists())

    @patch("identity.views.authenticate_with_moodle")
    def test_login_rejects_unknown_or_inactive_local_identity(self, authenticate):
        authenticate.return_value = MoodleAuthenticatedUser(
            site_url="https://moodle.example.test",
            user_id=999,
            username="other",
            full_name="Other Student",
            profile_image_url="",
        )
        missing = self.client.post(
            reverse("identity:moodle-login"),
            {"username": "other", "password": "secret"},
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.json()["code"], "identity_not_registered")

        authenticate.return_value = self.authenticated_user
        self.moodle_user.is_suspended = True
        self.moodle_user.suspended_at = timezone.now()
        self.moodle_user.save(update_fields=("is_suspended", "suspended_at"))
        inactive = self.client.post(
            reverse("identity:moodle-login"),
            {"username": "student", "password": "secret"},
            content_type="application/json",
        )
        self.assertEqual(inactive.status_code, 403)
        self.assertEqual(inactive.json()["code"], "identity_inactive")

    def test_login_requires_complete_json(self):
        response = self.client.post(
            reverse("identity:moodle-login"),
            {"username": "student"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_request")
