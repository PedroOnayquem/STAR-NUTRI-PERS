import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from backend.app.services.supabase_admin_service import SupabaseAdminService
from backend.app.services.supabase_user_service import SupabaseUserService
from backend.app.services.supabase_workspace_service import SupabaseWorkspaceService


def async_client_context(*, get_response=None, put_response=None, request_response=None):
    client = MagicMock()
    client.get = AsyncMock(return_value=get_response)
    client.put = AsyncMock(return_value=put_response)
    client.request = AsyncMock(return_value=request_response)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=None)
    return context, client


def response_with_json(payload, *, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.text = "json"
    response.json.return_value = payload
    return response


class WorkspaceAuthBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = object.__new__(SupabaseWorkspaceService)
        self.service.supabase_url = "https://example.supabase.co"
        self.service.service_key = "service-key"

    async def test_regular_rest_responses_are_not_treated_as_auth_users(self):
        response = response_with_json([{"id": "profile-1"}])
        context, _ = async_client_context(request_response=response)

        with patch(
            "backend.app.services.supabase_workspace_service.httpx.AsyncClient",
            return_value=context,
        ):
            result = await self.service._request("GET", "/rest/v1/profiles")

        self.assertEqual(result, [{"id": "profile-1"}])

    async def test_auth_user_with_temporary_password_is_blocked(self):
        response = response_with_json(
            {
                "id": "user-1",
                "app_metadata": {"must_change_password": True},
            },
        )
        context, _ = async_client_context(get_response=response)

        with patch(
            "backend.app.services.supabase_workspace_service.httpx.AsyncClient",
            return_value=context,
        ):
            with self.assertRaises(HTTPException) as caught:
                await self.service.get_user_from_access_token("token")

        self.assertEqual(caught.exception.status_code, 403)


class TemporaryPasswordServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = object.__new__(SupabaseUserService)
        self.service.supabase_url = "https://example.supabase.co"
        self.service.service_key = "service-key"

    async def test_change_password_rejects_account_without_pending_flag(self):
        self.service.get_user_from_access_token = AsyncMock(
            return_value={
                "id": "user-1",
                "app_metadata": {"must_change_password": False},
            },
        )

        with self.assertRaises(HTTPException) as caught:
            await self.service.change_own_password("token", "Strong1!")

        self.assertEqual(caught.exception.status_code, 403)

    async def test_change_password_updates_only_password_and_app_metadata(self):
        self.service.get_user_from_access_token = AsyncMock(
            return_value={
                "id": "user-1",
                "app_metadata": {
                    "must_change_password": True,
                    "provider": "email",
                },
                "user_metadata": {
                    "full_name": "Paciente",
                    "preferences": {"theme": "dark"},
                },
            },
        )
        response = response_with_json({"id": "user-1"})
        context, client = async_client_context(put_response=response)

        with patch(
            "backend.app.services.supabase_user_service.httpx.AsyncClient",
            return_value=context,
        ):
            await self.service.change_own_password("token", "Strong1!")

        payload = client.put.await_args.kwargs["json"]
        self.assertNotIn("user_metadata", payload)
        self.assertEqual(payload["password"], "Strong1!")
        self.assertFalse(payload["app_metadata"]["must_change_password"])
        self.assertEqual(payload["app_metadata"]["provider"], "email")
        self.assertIn("password_changed_at", payload["app_metadata"])


class AuthUserCreationMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def test_nutritionist_role_is_not_written_to_user_metadata(self):
        service = object.__new__(SupabaseAdminService)
        service.supabase_url = "https://example.supabase.co"
        service.service_key = "service-key"
        client = MagicMock()
        client.post = AsyncMock(
            side_effect=[
                response_with_json({"id": "user-1"}),
                response_with_json([{"id": "user-1"}]),
                response_with_json([{"id": "nutritionist-1"}]),
            ],
        )
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=None)
        payload = SimpleNamespace(
            full_name="Nutricionista",
            email="nutri@example.com",
            password="Strong1!",
            crn="CRN-1",
            specialty=None,
            bio=None,
        )

        with patch(
            "backend.app.services.supabase_admin_service.httpx.AsyncClient",
            return_value=context,
        ):
            await service.create_nutritionist(payload)

        auth_payload = client.post.await_args_list[0].kwargs["json"]
        self.assertEqual(auth_payload["user_metadata"], {"full_name": "Nutricionista"})
        self.assertEqual(auth_payload["app_metadata"], {"must_change_password": True})

    async def test_patient_role_is_not_written_to_user_metadata(self):
        service = object.__new__(SupabaseUserService)
        service.supabase_url = "https://example.supabase.co"
        service.service_key = "service-key"
        client = MagicMock()
        client.get = AsyncMock(
            return_value=response_with_json([{"default_patient_trial_days": 7}]),
        )
        client.post = AsyncMock(
            side_effect=[
                response_with_json({"id": "user-1"}),
                response_with_json([{"id": "user-1"}]),
                response_with_json([{"id": "patient-1"}]),
            ],
        )
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=None)
        payload = SimpleNamespace(
            full_name="Paciente",
            email="patient@example.com",
            password="Strong1!",
            birth_date=None,
            gender=None,
            objective=None,
            notes=None,
            import_id=None,
        )

        with patch(
            "backend.app.services.supabase_user_service.httpx.AsyncClient",
            return_value=context,
        ):
            await service.create_patient(payload, "nutritionist-1")

        auth_payload = client.post.await_args_list[0].kwargs["json"]
        self.assertEqual(auth_payload["user_metadata"], {"full_name": "Paciente"})
        self.assertEqual(auth_payload["app_metadata"], {"must_change_password": True})


if __name__ == "__main__":
    unittest.main()
