import asyncio
from datetime import datetime
import unittest
from unittest.mock import AsyncMock

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.schemas.workspace import UpdatePatientRequest
from backend.app.services.supabase_workspace_service import SupabaseWorkspaceService


class PatientAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = object.__new__(SupabaseWorkspaceService)

    def test_trial_without_end_date_fails_closed(self) -> None:
        patient = {"access_status": "TRIAL", "trial_ends_at": None}

        self.assertTrue(self.service._patient_trial_is_expired(patient))
        access = self.service._patient_access_payload(patient)
        self.assertEqual(access["status"], "EXPIRED")
        self.assertFalse(access["has_premium_access"])
        self.assertFalse(access["can_use_ai_chat"])

    def test_future_trial_keeps_premium_access(self) -> None:
        patient = {
            "access_status": "TRIAL",
            "trial_ends_at": "2999-01-01T00:00:00Z",
        }

        self.assertFalse(self.service._patient_trial_is_expired(patient))
        access = self.service._patient_access_payload(patient)
        self.assertEqual(access["status"], "TRIAL")
        self.assertTrue(access["has_premium_access"])
        self.assertTrue(access["can_use_ai_chat"])

    def test_expired_trial_loses_premium_access(self) -> None:
        patient = {
            "access_status": "TRIAL",
            "trial_ends_at": "2000-01-01T00:00:00Z",
        }

        self.assertTrue(self.service._patient_trial_is_expired(patient))
        access = self.service._patient_access_payload(patient)
        self.assertEqual(access["status"], "EXPIRED")
        self.assertFalse(access["has_premium_access"])

    def test_invalid_trial_date_fails_closed(self) -> None:
        patient = {"access_status": "TRIAL", "trial_ends_at": "not-a-date"}

        self.assertTrue(self.service._patient_trial_is_expired(patient))
        self.assertFalse(
            self.service._patient_access_payload(patient)["has_premium_access"]
        )

    def test_active_patient_does_not_require_trial_end_date(self) -> None:
        access = self.service._patient_access_payload(
            {"access_status": "ACTIVE", "trial_ends_at": None}
        )

        self.assertEqual(access["status"], "ACTIVE")
        self.assertTrue(access["has_premium_access"])

    def test_expired_patient_cannot_be_reopened_by_future_trial_date(self) -> None:
        access = self.service._patient_access_payload(
            {
                "access_status": "EXPIRED",
                "trial_ends_at": "2999-01-01T00:00:00Z",
            }
        )

        self.assertEqual(access["status"], "EXPIRED")
        self.assertFalse(access["has_premium_access"])

    def test_refresh_persists_fail_closed_trial_state(self) -> None:
        patient = {
            "id": "patient-id",
            "access_status": "TRIAL",
            "trial_ends_at": None,
            "is_active": True,
        }
        self.service._request = AsyncMock(
            return_value=[
                {
                    **patient,
                    "access_status": "EXPIRED",
                    "is_active": False,
                }
            ]
        )

        result = asyncio.run(self.service._refresh_patient_access_status(patient))

        self.assertEqual(result["access_status"], "EXPIRED")
        self.assertFalse(result["is_active"])
        request_payload = self.service._request.await_args.kwargs["json"]
        self.assertEqual(request_payload["access_status"], "EXPIRED")
        self.assertFalse(request_payload["is_active"])

    def test_generic_patient_update_cannot_restart_trial(self) -> None:
        with self.assertRaises(ValidationError):
            UpdatePatientRequest(access_status="TRIAL")

    def test_null_access_controls_are_ignored(self) -> None:
        result = self.service._normalize_patient_access_update(
            {"objective": "Recomposição", "access_status": None, "is_active": None}
        )

        self.assertEqual(result, {"objective": "Recomposição"})

    def test_contradictory_access_controls_are_rejected(self) -> None:
        conflicting_updates = (
            {"access_status": "ACTIVE", "is_active": False},
            {"access_status": "EXPIRED", "is_active": True},
        )

        for update in conflicting_updates:
            with self.subTest(update=update), self.assertRaises(HTTPException) as raised:
                self.service._normalize_patient_access_update(update)
            self.assertEqual(raised.exception.status_code, 400)

    def test_activation_without_trial_days_grants_active_access(self) -> None:
        payload = self.service._patient_activation_payload(None)

        self.assertEqual(payload["access_status"], "ACTIVE")
        self.assertTrue(payload["is_active"])
        self.assertIsNone(payload["expired_at"])

    def test_activation_with_trial_days_restarts_finite_trial(self) -> None:
        payload = self.service._patient_activation_payload(7)
        started_at = datetime.fromisoformat(payload["trial_started_at"])
        ends_at = datetime.fromisoformat(payload["trial_ends_at"])

        self.assertEqual(payload["access_status"], "TRIAL")
        self.assertEqual(payload["trial_days"], 7)
        self.assertEqual((ends_at - started_at).days, 7)
        self.assertTrue(payload["is_active"])

    def test_activation_rejects_unsupported_trial_duration(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            self.service._patient_activation_payload(365)

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
