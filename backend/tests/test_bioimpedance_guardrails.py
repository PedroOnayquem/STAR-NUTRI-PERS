import unittest

from backend.app.services.bioimpedance_import_service import BioimpedanceImportService


class BioimpedanceGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(BioimpedanceImportService)

    def test_metric_invented_by_extractor_is_removed(self):
        result = self.service._normalize_payload(
            {"patient": {}, "metrics": {"weight_kg": 92}, "warnings": []},
            "Relatorio de bioimpedancia. Peso: 70 kg. IMC: 22.",
            "pdf",
        )
        self.assertNotIn("weight_kg", result["metrics"])
        self.assertTrue(any("não estar presente" in item for item in result["warnings"]))

    def test_metric_present_in_document_is_kept(self):
        result = self.service._normalize_payload(
            {"patient": {}, "metrics": {"weight_kg": 70}, "warnings": []},
            "Relatorio de bioimpedancia. Peso: 70,0 kg. IMC: 22.",
            "pdf",
        )
        self.assertEqual(result["metrics"]["weight_kg"], 70.0)


if __name__ == "__main__":
    unittest.main()
