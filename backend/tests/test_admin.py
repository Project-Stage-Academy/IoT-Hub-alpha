from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class TestAdminLogin(TestCase):
    """Test admin login functionality."""

    @classmethod
    def setUpTestData(cls):
        """Create test users"""
        cls.admin_user = User.objects.create_superuser(
            username="test_admin",
            email="admin@test.com",
            password="adminpass123",
        )

        cls.operator_user = User.objects.create_user(
            username="test_operator",
            email="operator@test.com",
            password="operatorpass123",
            is_staff=True,
        )

        cls.viewer_user = User.objects.create_user(
            username="test_viewer",
            email="viewer@test.com",
            password="viewerpass123",
            is_staff=True,
        )

    def test_admin_login_page_renders(self):
        """Test that admin login page renders"""
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_login(self):
        """Test superuser can login to admin"""
        logged_in = self.client.login(username="test_admin", password="adminpass123")
        self.assertTrue(logged_in)

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_operator_can_login(self):
        """Test operator can login to admin"""
        logged_in = self.client.login(username="test_operator", password="operatorpass123")
        self.assertTrue(logged_in)

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_viewer_can_login(self):
        """Test viewer can login to admin"""
        logged_in = self.client.login(username="test_viewer", password="viewerpass123")
        self.assertTrue(logged_in)

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
