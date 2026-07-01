from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Project


User = get_user_model()


class NormalUserManagementTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="superuser",
            email="super@example.com",
            password="password123",
        )
        self.normal_user = User.objects.create_user(
            username="normaluser",
            email="normal@example.com",
            password="password123",
        )

    def test_anonymous_users_are_sent_to_login(self):
        response = self.client.get(reverse("normal-user-list"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/?next="))

    def test_normal_users_cannot_access_management_views(self):
        self.client.force_login(self.normal_user)

        response = self.client.get(reverse("normal-user-list"))

        self.assertEqual(response.status_code, 403)

    def test_sidebar_user_link_is_visible_only_for_superusers(self):
        self.client.force_login(self.superuser)
        superuser_response = self.client.get(reverse("home"))

        self.client.force_login(self.normal_user)
        normal_response = self.client.get(reverse("home"))

        self.assertContains(superuser_response, 'id="app-sidebar"')
        self.assertContains(superuser_response, "Administrador")
        self.assertContains(superuser_response, "Proyectos")
        self.assertContains(superuser_response, "Usuarios")
        self.assertContains(normal_response, 'id="app-sidebar"')
        self.assertNotContains(normal_response, "Administrador")
        self.assertNotContains(normal_response, "Proyectos")
        self.assertNotContains(normal_response, "Usuarios")

    def test_superuser_can_create_normal_user(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("normal-user-create"),
            {
                "username": "createduser",
                "email": "created@example.com",
                "first_name": "Created",
                "last_name": "User",
                "is_active": "on",
                "password1": "StrongPass12345",
                "password2": "StrongPass12345",
            },
        )
        user = User.objects.get(username="createduser")

        self.assertRedirects(response, reverse("normal-user-list"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, "created@example.com")

    def test_superuser_can_update_only_normal_users(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("normal-user-update", args=[self.normal_user.pk]),
            {
                "username": "normaluser",
                "email": "updated@example.com",
                "first_name": "Updated",
                "last_name": "User",
                "is_active": "on",
            },
        )
        self.normal_user.refresh_from_db()
        superuser_response = self.client.get(
            reverse("normal-user-update", args=[self.superuser.pk])
        )

        self.assertRedirects(response, reverse("normal-user-list"))
        self.assertEqual(self.normal_user.email, "updated@example.com")
        self.assertFalse(self.normal_user.is_staff)
        self.assertFalse(self.normal_user.is_superuser)
        self.assertEqual(superuser_response.status_code, 404)


class ProjectAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        self.normal_user = User.objects.create_user(
            username="normal",
            email="normal@example.com",
            password="password123",
        )

    def test_only_superusers_can_access_project_admin(self):
        anonymous_response = self.client.get(reverse("project-admin"))

        self.client.force_login(self.normal_user)
        normal_response = self.client.get(reverse("project-admin"))

        self.assertEqual(anonymous_response.status_code, 302)
        self.assertTrue(anonymous_response["Location"].startswith("/?next="))
        self.assertEqual(normal_response.status_code, 403)

    def test_superuser_can_create_update_and_delete_project(self):
        self.client.force_login(self.superuser)

        create_response = self.client.post(
            reverse("project-admin"),
            {"name": "Proyecto A"},
        )
        project = Project.objects.get(name="Proyecto A")

        update_response = self.client.post(
            reverse("project-admin-edit", args=[project.pk]),
            {"name": "Proyecto B"},
        )
        project.refresh_from_db()

        delete_response = self.client.post(
            reverse("project-admin"),
            {
                "action": "delete",
                "project_id": project.pk,
            },
        )

        self.assertRedirects(create_response, reverse("project-admin"))
        self.assertRedirects(update_response, reverse("project-admin"))
        self.assertEqual(project.name, "Proyecto B")
        self.assertRedirects(delete_response, reverse("project-admin"))
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
