import json
from django.test import TestCase

from apps.devices.models import DeviceType, Device


class DeviceApiTests(TestCase):
    def setUp(self):
        self.dt = DeviceType.objects.create(
            name="Temp Sensor",
            metric_name=DeviceType.MetricName.TEMPERATURE,
            metric_unit="C",
        )
        self.list_url = "/api/v1/devices/"

    def test_list_devices_returns_pagination(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertIn("data", body)
        self.assertIn("pagination", body)
        self.assertIsInstance(body["data"], list)

        p = body["pagination"]
        for key in ("page", "page_size", "total", "total_pages", "next_page", "prev_page"):
            self.assertIn(key, p)

    def test_list_devices_invalid_page_returns_400(self):
        resp = self.client.get(self.list_url, {"page": 0, "page_size": 10})
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("errors", body)
        self.assertIn("page", body["errors"])

    def test_list_devices_invalid_page_size_returns_400(self):
        resp = self.client.get(self.list_url, {"page": 1, "page_size": 1001})
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("errors", body)
        self.assertIn("page_size", body["errors"])

    def test_create_device_happy_path(self):
        payload = {
            "name": "Sensor 1",
            "serial_number": "SN-001",
            "device_type_id": str(self.dt.id),
            "status": "active",
            "location": "Lab",
        }
        resp = self.client.post(
            self.list_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)

        body = resp.json()
        self.assertIn("data", body)
        self.assertEqual(body["data"]["name"], "Sensor 1")
        self.assertTrue(Device.objects.filter(id=body["data"]["id"]).exists())

    def test_create_device_validation_error(self):
        payload = {
            "name": "",
            "serial_number": "",
            "device_type_id": str(self.dt.id),
        }
        resp = self.client.post(
            self.list_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertIn("errors", body)

    def test_retrieve_update_delete_flow(self):
        d = Device.objects.create(
            name="Sensor X",
            serial_number="SN-XYZ",
            device_type=self.dt,
            status=Device.DeviceStatus.ACTIVE,
            location="Lab",
        )

        detail_url = f"/api/v1/devices/{d.id}/"

        # retrieve
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)

        # patch
        payload = {"status": Device.DeviceStatus.INACTIVE}
        resp = self.client.patch(
            detail_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        d.refresh_from_db()
        self.assertEqual(d.status, Device.DeviceStatus.INACTIVE)

        # delete
        resp = self.client.delete(detail_url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Device.objects.filter(id=d.id).exists())

    def test_detail_not_found(self):
        resp = self.client.get("/api/v1/devices/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(resp.status_code, 404)
