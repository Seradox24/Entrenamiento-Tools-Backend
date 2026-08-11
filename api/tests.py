from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Project


User = get_user_model()


class SomRouteScopeTests(SimpleTestCase):
    def test_application_routes_are_scoped_under_som(self):
        self.assertEqual(reverse("login"), "/som/")
        self.assertEqual(reverse("home"), "/som/home/")
        self.assertEqual(reverse("project-admin"), "/som/home/projects/")
        self.assertEqual(reverse("normal-user-list"), "/som/home/users/")
        self.assertEqual(reverse("api-health"), "/som/api/health/")
        self.assertEqual(reverse("project-list"), "/som/api/projects/")


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
        self.assertTrue(response["Location"].startswith("/som/?next="))

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
        self.assertTrue(anonymous_response["Location"].startswith("/som/?next="))
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


class ProjectApiTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="api-admin",
            email="api-admin@example.com",
            password="password123",
        )
        self.normal_user = User.objects.create_user(
            username="api-user",
            email="api-user@example.com",
            password="password123",
        )
        self.project = Project.objects.create(name="Proyecto API")

    def test_health_check_is_public(self):
        response = self.client.get(reverse("api-health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

    def test_project_api_rejects_users_without_superuser_permission(self):
        anonymous_response = self.client.get(reverse("project-list"))

        self.client.force_authenticate(user=self.normal_user)
        normal_user_response = self.client.get(reverse("project-list"))

        self.assertEqual(anonymous_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(normal_user_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_can_list_and_retrieve_projects(self):
        self.client.force_authenticate(user=self.superuser)

        list_response = self.client.get(reverse("project-list"))
        detail_response = self.client.get(
            reverse("project-detail", args=[self.project.pk])
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]["name"], "Proyecto API")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], self.project.pk)

    def test_superuser_can_create_update_and_delete_projects(self):
        self.client.force_authenticate(user=self.superuser)

        create_response = self.client.post(
            reverse("project-list"),
            {"name": "Proyecto creado desde API"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        project_id = create_response.data["id"]

        update_response = self.client.patch(
            reverse("project-detail", args=[project_id]),
            {"name": "Proyecto actualizado desde API"},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("project-detail", args=[project_id])
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            update_response.data["name"], "Proyecto actualizado desde API"
        )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(pk=project_id).exists())
