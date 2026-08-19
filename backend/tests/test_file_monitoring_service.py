import unittest

from backend.app.services.file_monitoring_service import FileMonitoringService


class FileMonitoringServiceTests(unittest.TestCase):
    def test_response_uses_only_measured_durations(self):
        service = object.__new__(FileMonitoringService)
        imports = [
            {"id": "a", "status": "processed", "file_count": 2, "file_type": "pdf", "processing_duration_ms": 1000, "created_at": "2026-08-17T10:00:00+00:00"},
            {"id": "b", "status": "linked", "file_count": 1, "file_type": "png", "processing_duration_ms": None, "created_at": "2026-08-17T11:00:00+00:00"},
            {"id": "c", "status": "failed", "file_count": 1, "file_type": "pdf", "processing_duration_ms": 3000, "error_code": "http_422", "error_message": "Falha", "created_at": "2026-08-17T12:00:00+00:00"},
        ]
        events = [{"import_id": "a", "event_type": "ai_context_used", "created_at": "2026-08-17T13:00:00+00:00"}]
        result = service._build_response(imports, events, 7, "nutritionist")
        self.assertEqual(result["summary"]["files"], 4)
        self.assertEqual(result["summary"]["processed"], 2)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["summary"]["average_processing_ms"], 2000)
        self.assertEqual(result["summary"]["measured_processing_count"], 2)
        self.assertEqual(result["summary"]["ai_usage_count"], 1)
        self.assertEqual(result["summary"]["file_access_count"], 0)

    def test_invalid_date_is_ignored(self):
        self.assertIsNone(FileMonitoringService._date_key("not-a-date"))


if __name__ == "__main__":
    unittest.main()
