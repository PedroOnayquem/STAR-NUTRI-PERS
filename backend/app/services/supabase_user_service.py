import httpx
from fastapi import HTTPException, status
from datetime import UTC, datetime, timedelta

from ..core.config import settings
from ..schemas.patients import CreatePatientRequest
from .auth_policy import assert_password_change_complete, requires_password_change
from .bioimpedance_metrics import imported_metrics_to_rows


class SupabaseUserService:
    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Backend Supabase nao configurado. Defina SUPABASE_URL e "
                    "SUPABASE_SERVICE_ROLE_KEY em backend/.env e reinicie a API."
                ),
            )

        self.supabase_url = settings.supabase_url.rstrip("/")
        self.service_key = settings.supabase_service_role_key

    @property
    def service_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    async def get_user_from_access_token(
        self,
        token: str,
        *,
        allow_password_change: bool = False,
    ) -> dict:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.supabase_url}/auth/v1/user",
                    headers={
                        "apikey": self.service_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível validar o acesso. Tente novamente em instantes.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
            )

        auth_user = response.json()
        if not allow_password_change:
            assert_password_change_complete(auth_user)
        return auth_user

    async def change_own_password(self, token: str, password: str) -> None:
        auth_user = await self.get_user_from_access_token(
            token,
            allow_password_change=True,
        )
        user_id = auth_user.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado.",
            )
        if not requires_password_change(auth_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Esta conta não possui uma troca de senha provisória pendente.",
            )

        app_metadata = dict(auth_user.get("app_metadata") or {})
        app_metadata["must_change_password"] = False
        app_metadata["password_changed_at"] = datetime.now(UTC).isoformat()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.put(
                    f"{self.supabase_url}/auth/v1/admin/users/{user_id}",
                    headers=self.service_headers,
                    json={
                        "password": password,
                        "app_metadata": app_metadata,
                    },
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível atualizar a senha. Tente novamente em instantes.",
            ) from None

        if response.status_code >= 400:
            self._raise_supabase_error(response)

    async def assert_nutritionist(self, token: str) -> dict:
        auth_user = await self.get_user_from_access_token(token)
        user_id = auth_user.get("id")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado.",
            )

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    f"{self.supabase_url}/rest/v1/profiles",
                    headers=self.service_headers,
                    params={
                        "id": f"eq.{user_id}",
                        "select": "id,email,role,is_active",
                        "limit": "1",
                    },
                )

                nutritionist_response = await client.get(
                    f"{self.supabase_url}/rest/v1/nutritionists",
                    headers=self.service_headers,
                    params={
                        "user_id": f"eq.{user_id}",
                        "select": "id,user_id",
                        "limit": "1",
                    },
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível validar o nutricionista. Entre novamente e tente de novo.",
            ) from None

        if response.status_code >= 400 or nutritionist_response.status_code >= 400:
            detail = self._extract_error(response)
            if nutritionist_response.status_code >= 400:
                detail = self._extract_error(nutritionist_response)

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Nao foi possivel validar o nutricionista no Supabase: {detail}",
            )

        profiles = response.json()
        nutritionists = nutritionist_response.json()
        profile = profiles[0] if profiles else None
        nutritionist = nutritionists[0] if nutritionists else None

        if (
            not profile
            or profile.get("role") != "nutritionist"
            or profile.get("is_active") is False
            or not nutritionist
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only active nutritionists can create patients.",
            )

        return nutritionist

    async def create_patient(
        self,
        payload: CreatePatientRequest,
        nutritionist_id: str,
    ) -> dict:
        created_user_id: str | None = None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                trial_days = await self._get_nutritionist_trial_days(client, nutritionist_id)
                trial_started_at = datetime.now(UTC)
                trial_ends_at = trial_started_at + timedelta(days=trial_days)

                auth_response = await client.post(
                    f"{self.supabase_url}/auth/v1/admin/users",
                    headers=self.service_headers,
                    json={
                        "email": payload.email,
                        "password": payload.password,
                        "email_confirm": True,
                        "user_metadata": {
                            "full_name": payload.full_name,
                        },
                        "app_metadata": {"must_change_password": True},
                    },
                )

                if auth_response.status_code >= 400:
                    self._raise_supabase_error(auth_response)

                auth_user = auth_response.json()
                created_user_id = auth_user["id"]

                profile_response = await client.post(
                    f"{self.supabase_url}/rest/v1/profiles",
                    headers={
                        **self.service_headers,
                        "Prefer": "resolution=merge-duplicates,return=representation",
                    },
                    params={"on_conflict": "id"},
                    json={
                        "id": created_user_id,
                        "full_name": payload.full_name,
                        "email": payload.email,
                        "role": "patient",
                        "is_active": True,
                    },
                )

                if profile_response.status_code >= 400:
                    await self._delete_auth_user(client, created_user_id)
                    self._raise_supabase_error(profile_response)

                patient_payload = {
                    "user_id": created_user_id,
                    "nutritionist_id": nutritionist_id,
                    "birth_date": payload.birth_date.isoformat()
                    if payload.birth_date
                    else None,
                    "gender": payload.gender,
                    "objective": payload.objective,
                    "notes": payload.notes,
                    "is_active": True,
                    "access_status": "TRIAL",
                    "trial_days": trial_days,
                    "trial_started_at": trial_started_at.isoformat(),
                    "trial_ends_at": trial_ends_at.isoformat(),
                }
                patient_response = await client.post(
                    f"{self.supabase_url}/rest/v1/patients",
                    headers={
                        **self.service_headers,
                        "Prefer": "resolution=merge-duplicates,return=representation",
                    },
                    params={"on_conflict": "user_id"},
                    json=patient_payload,
                )
                if patient_response.status_code >= 400 and self._looks_like_missing_trial_columns(patient_response):
                    patient_response = await client.post(
                        f"{self.supabase_url}/rest/v1/patients",
                        headers={
                            **self.service_headers,
                            "Prefer": "resolution=merge-duplicates,return=representation",
                        },
                        params={"on_conflict": "user_id"},
                        json={
                            key: value
                            for key, value in patient_payload.items()
                            if key
                            not in {
                                "access_status",
                                "trial_days",
                                "trial_started_at",
                                "trial_ends_at",
                            }
                        },
                    )

                if patient_response.status_code >= 400:
                    await self._delete_auth_user(client, created_user_id)
                    self._raise_supabase_error(patient_response)

                patient = patient_response.json()[0]

                if payload.import_id:
                    await self._finalize_patient_import(
                        client=client,
                        import_id=payload.import_id,
                        nutritionist_id=nutritionist_id,
                        patient_id=patient["id"],
                    )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível concluir o cadastro. Tente novamente em instantes.",
            ) from None

        return {
            "profile_id": created_user_id,
            "patient_id": patient["id"],
            "email": payload.email,
            "full_name": payload.full_name,
            "role": "patient",
            "access_status": "TRIAL",
            "trial_days": trial_days,
            "trial_ends_at": trial_ends_at.isoformat(),
        }

    async def _get_nutritionist_trial_days(
        self,
        client: httpx.AsyncClient,
        nutritionist_id: str,
    ) -> int:
        response = await client.get(
            f"{self.supabase_url}/rest/v1/nutritionists",
            headers=self.service_headers,
            params={
                "id": f"eq.{nutritionist_id}",
                "select": "default_patient_trial_days",
                "limit": "1",
            },
        )
        if response.status_code >= 400:
            detail = self._extract_error(response).lower()
            if "default_patient_trial_days" in detail or "column" in detail:
                return 7
            self._raise_supabase_error(response)

        rows = response.json()
        raw_days = rows[0].get("default_patient_trial_days") if rows else 7
        return raw_days if raw_days in {7, 14, 30} else 7

    def _looks_like_missing_trial_columns(self, response: httpx.Response) -> bool:
        detail = self._extract_error(response).lower()
        return any(
            column in detail
            for column in (
                "access_status",
                "trial_days",
                "trial_started_at",
                "trial_ends_at",
            )
        )

    async def _finalize_patient_import(
        self,
        *,
        client: httpx.AsyncClient,
        import_id: str,
        nutritionist_id: str,
        patient_id: str,
    ) -> None:
        import_response = await client.get(
            f"{self.supabase_url}/rest/v1/patient_imports",
            headers=self.service_headers,
            params={
                "id": f"eq.{import_id}",
                "nutritionist_id": f"eq.{nutritionist_id}",
                "select": "*",
                "limit": "1",
            },
        )
        if import_response.status_code >= 400:
            self._raise_supabase_error(import_response)

        rows = import_response.json()
        import_row = rows[0] if rows else None
        if not import_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Importação de relatório não encontrada para este nutricionista.",
            )

        metrics = imported_metrics_to_rows(
            payload=import_row.get("extracted_payload") or {},
            patient_id=patient_id,
            import_id=import_id,
            source_type=import_row.get("source_type") or "bioimpedance_report",
        )
        if metrics:
            metrics_response = await client.post(
                f"{self.supabase_url}/rest/v1/patient_variable_metrics",
                headers={**self.service_headers, "Prefer": "return=minimal"},
                json=metrics,
            )
            if metrics_response.status_code >= 400:
                self._raise_supabase_error(metrics_response)

        import_update = await client.patch(
            f"{self.supabase_url}/rest/v1/patient_imports",
            headers={**self.service_headers, "Prefer": "return=minimal"},
            params={"id": f"eq.{import_id}", "nutritionist_id": f"eq.{nutritionist_id}"},
            json={"patient_id": patient_id, "status": "linked"},
        )
        if import_update.status_code >= 400:
            self._raise_supabase_error(import_update)

        # Linking is part of the real import lifecycle. Failure to write
        # telemetry must not roll back an otherwise valid patient creation.
        try:
            await client.post(
                f"{self.supabase_url}/rest/v1/patient_import_events",
                headers={**self.service_headers, "Prefer": "return=minimal"},
                json={
                    "import_id": import_id,
                    "patient_id": patient_id,
                    "nutritionist_id": nutritionist_id,
                    "event_type": "linked_to_patient",
                    "stage": "patient_link",
                },
            )
        except httpx.RequestError:
            pass

    async def _delete_auth_user(self, client: httpx.AsyncClient, user_id: str) -> None:
        await client.delete(
            f"{self.supabase_url}/auth/v1/admin/users/{user_id}",
            headers=self.service_headers,
        )

    def _raise_supabase_error(self, response: httpx.Response) -> None:
        detail = self._extract_error(response)
        status_code = status.HTTP_400_BAD_REQUEST
        normalized = detail.lower()

        if (
            "already been registered" in normalized
            or "already registered" in normalized
            or "already exists" in normalized
            or "duplicate" in normalized
        ):
            status_code = status.HTTP_409_CONFLICT
            detail = "Este e-mail já está cadastrado. Use outro e-mail."

        raise HTTPException(status_code=status_code, detail=detail)

    def _extract_error(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text or "Supabase request failed."

        return (
            body.get("msg")
            or body.get("message")
            or body.get("error_description")
            or body.get("error")
            or "Supabase request failed."
        )
