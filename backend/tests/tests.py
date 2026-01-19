from django.test import SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    def test_placeholder(self) -> None:
        self.assertTrue(True)

    def test_always_fails(self) -> None:
        self.fail("Intentional failure to verify CI pipeline behavior.")
