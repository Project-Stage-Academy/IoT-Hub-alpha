from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class TestAdminLogin(TestCase):
    """Test admin login functionality."""

    ADMIN_USERNAME = "test_admin"
    ADMIN_EMAIL = "admin@test.com"
    ADMIN_PASSWORD = "adminpass123"

    OPERATOR_USERNAME = "test_operator"
    OPERATOR_EMAIL = "operator@test.com"
    OPERATOR_PASSWORD = "operatorpass123"

    VIEWER_USERNAME = "test_viewer"
    VIEWER_EMAIL = "viewer@test.com"
    VIEWER_PASSWORD = "viewerpass123"

    @classmethod
    def setUpTestData(cls):
        """Create test users"""
        cls.admin_user = User.objects.create_superuser(
            username=cls.ADMIN_USERNAME,
            email=cls.ADMIN_EMAIL,
            password=cls.ADMIN_PASSWORD,
        )

        cls.operator_user = User.objects.create_user(
            username=cls.OPERATOR_USERNAME,
            email=cls.OPERATOR_EMAIL,
            password=cls.OPERATOR_PASSWORD,
            is_staff=True,
        )

        cls.viewer_user = User.objects.create_user(
            username=cls.VIEWER_USERNAME,
            email=cls.VIEWER_EMAIL,
            password=cls.VIEWER_PASSWORD,
            is_staff=True,
        )

    def test_admin_login_page_renders(self):
        """Test that admin login page renders"""
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_login(self):
        """Test superuser can login to admin"""
        logged_in = self.client.login(
            username=self.ADMIN_USERNAME, password=self.ADMIN_PASSWORD
        )
        self.assertTrue(logged_in)

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_operator_can_login(self):
        """Test operator can login to admin"""
        logged_in = self.client.login(
            username=self.OPERATOR_USERNAME, password=self.OPERATOR_PASSWORD
        )
        self.assertTrue(logged_in)

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_viewer_can_login(self):
        """Test viewer can login to admin"""
        logged_in = self.client.login(
            username=self.VIEWER_USERNAME, password=self.VIEWER_PASSWORD
        )
        self.assertTrue(logged_in)

        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
