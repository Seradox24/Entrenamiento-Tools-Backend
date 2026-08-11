from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class LrsRouteTests(TestCase):
    def test_lrs_route_is_scoped_and_requires_authentication(self):
        response = self.client.get(reverse("lrs-home"))

        self.assertEqual(reverse("lrs-home"), "/som/lrs/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/som/?next="))

    def test_authenticated_user_can_access_lrs_root(self):
        user = User.objects.create_user(username="lrs-user", password="password123")
        self.client.force_login(user)

        response = self.client.get(reverse("lrs-home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "som-lrs")
