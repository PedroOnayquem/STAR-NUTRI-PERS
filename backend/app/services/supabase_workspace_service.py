from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, status

from ..core.config import settings
from ..schemas.workspace import UpdatePatientRequest


class SupabaseWorkspaceService:
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
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = self.headers
        if prefer:
            headers = {**headers, "Prefer": prefer}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{self.supabase_url}{path}",
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Nao foi possivel conectar ao Supabase.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro do Supabase: {self._extract_error(response)}",
            )

        if response.status_code == 204 or not response.text:
            return None

        return response.json()

    async def get_user_from_access_token(self, token: str) -> dict:
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
                detail="Nao foi possivel conectar ao Supabase Auth.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido ou expirado.",
            )

        return response.json()

    async def get_profile(self, user_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/profiles",
            params={
                "id": f"eq.{user_id}",
                "select": "id,full_name,email,role,avatar_url,phone,is_active,created_at",
                "limit": "1",
            },
        )
        profile = rows[0] if rows else None
        if not profile or profile.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Perfil inexistente ou inativo.",
            )
        return profile

    async def get_authenticated_profile(self, token: str) -> dict:
        user = await self.get_user_from_access_token(token)
        return await self.get_profile(user["id"])

    async def get_nutritionist_by_user_id(self, user_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/nutritionists",
            params={
                "user_id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
        )
        nutritionist = rows[0] if rows else None
        if not nutritionist:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cadastro de nutricionista nao encontrado.",
            )
        return nutritionist

    async def get_patient_by_user_id(self, user_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/patients",
            params={"user_id": f"eq.{user_id}", "select": "*", "limit": "1"},
        )
        patient = rows[0] if rows else None
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cadastro de paciente nao encontrado.",
            )
        return patient

    async def get_nutritionist_workspace(self, token: str) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem acessar este workspace.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        patients = await self._request(
            "GET",
            "/rest/v1/patients",
            params={
                "nutritionist_id": f"eq.{nutritionist['id']}",
                "select": "*",
                "order": "created_at.desc",
            },
        )

        return {
            "nutritionist": nutritionist,
            "patients": await self._attach_profiles(patients),
        }

    async def get_admin_workspace(self, token: str) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas admins podem acessar este workspace.",
            )

        profiles = await self._request(
            "GET",
            "/rest/v1/profiles",
            params={
                "select": "id,full_name,email,role,avatar_url,phone,is_active,created_at",
                "order": "created_at.desc",
            },
        )
        nutritionists = await self._request(
            "GET",
            "/rest/v1/nutritionists",
            params={"select": "*", "order": "created_at.desc"},
        )
        patients = await self._request(
            "GET",
            "/rest/v1/patients",
            params={"select": "*", "order": "created_at.desc"},
        )
        diets = await self._request("GET", "/rest/v1/diets", params={"select": "id"})
        workouts = await self._request(
            "GET",
            "/rest/v1/workouts",
            params={"select": "id"},
        )
        messages = await self._request(
            "GET",
            "/rest/v1/chat_messages",
            params={"select": "id"},
        )

        return {
            "profiles": profiles,
            "nutritionists": nutritionists,
            "patients": await self._attach_profiles(patients),
            "stats": {
                "users": len(profiles),
                "nutritionists": len(nutritionists),
                "patients": len(patients),
                "active_patients": len(
                    [patient for patient in patients if patient.get("is_active") is not False]
                ),
                "diets": len(diets),
                "workouts": len(workouts),
                "chat_messages": len(messages),
            },
        }

    async def get_patient_context_for_nutritionist(
        self,
        token: str,
        patient_id: str,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem acessar este paciente.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        patient = await self._get_patient(patient_id)
        if patient["nutritionist_id"] != nutritionist["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Paciente fora do seu workspace.",
            )

        return await self.get_patient_context(patient, nutritionist)

    async def get_patient_context_for_patient(self, token: str) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas pacientes podem acessar este contexto.",
            )

        patient = await self.get_patient_by_user_id(profile["id"])
        nutritionist_rows = await self._request(
            "GET",
            "/rest/v1/nutritionists",
            params={
                "id": f"eq.{patient['nutritionist_id']}",
                "select": "*",
                "limit": "1",
            },
        )
        nutritionist = nutritionist_rows[0] if nutritionist_rows else None
        return await self.get_patient_context(patient, nutritionist)

    async def get_patient_context(
        self,
        patient: dict,
        nutritionist: dict | None,
    ) -> dict:
        patient_profile = await self.get_profile(patient["user_id"])
        patient_id = patient["id"]

        diets = await self._request(
            "GET",
            "/rest/v1/diets",
            params={
                "patient_id": f"eq.{patient_id}",
                "select": "*",
                "order": "is_active.desc,created_at.desc",
            },
        )
        workouts = await self._request(
            "GET",
            "/rest/v1/workouts",
            params={
                "patient_id": f"eq.{patient_id}",
                "select": "*",
                "order": "is_active.desc,created_at.desc",
            },
        )

        meals = await self._rows_by_parent("diet_meals", "diet_id", [row["id"] for row in diets])
        exercises = await self._rows_by_parent(
            "workout_exercises",
            "workout_id",
            [row["id"] for row in workouts],
        )

        for diet in diets:
            diet["meals"] = meals.get(diet["id"], [])
        for workout in workouts:
            workout["exercises"] = exercises.get(workout["id"], [])

        sessions = await self._request(
            "GET",
            "/rest/v1/chat_sessions",
            params={
                "patient_id": f"eq.{patient_id}",
                "select": "*",
                "order": "updated_at.desc,created_at.desc",
            },
        )

        recent_messages = await self._get_recent_messages(sessions)

        return {
            "patient": {**patient, "profile": patient_profile},
            "profile": patient_profile,
            "nutritionist": nutritionist,
            "main_metrics": await self._request(
                "GET",
                "/rest/v1/patient_main_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "created_at.desc",
                },
            ),
            "variable_metrics": await self._request(
                "GET",
                "/rest/v1/patient_variable_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "recorded_at.desc,created_at.desc",
                    "limit": "120",
                },
            ),
            "conditions": await self._request(
                "GET",
                "/rest/v1/patient_health_conditions",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "created_at.desc",
                },
            ),
            "diets": diets,
            "workouts": workouts,
            "chat_sessions": sessions,
            "recent_messages": recent_messages,
        }

    async def update_patient(
        self,
        token: str,
        patient_id: str,
        payload: UpdatePatientRequest,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem editar pacientes.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        patient = await self._get_patient(patient_id)
        if patient["nutritionist_id"] != nutritionist["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Paciente fora do seu workspace.",
            )

        patient_payload = payload.model_dump(
            exclude_unset=True,
            exclude={"full_name", "phone"},
        )
        if patient_payload:
            updated = await self._request(
                "PATCH",
                "/rest/v1/patients",
                params={"id": f"eq.{patient_id}", "select": "*"},
                json=patient_payload,
                prefer="return=representation",
            )
            patient = updated[0]

        profile_payload = payload.model_dump(
            exclude_unset=True,
            include={"full_name", "phone"},
        )
        if profile_payload:
            await self._request(
                "PATCH",
                "/rest/v1/profiles",
                params={"id": f"eq.{patient['user_id']}", "select": "*"},
                json=profile_payload,
                prefer="return=representation",
            )

        profile_row = await self.get_profile(patient["user_id"])
        return {**patient, "profile": profile_row}

    async def deactivate_patient(self, token: str, patient_id: str) -> dict:
        updated = await self.update_patient(
            token,
            patient_id,
            UpdatePatientRequest(is_active=False),
        )
        return {"id": updated["id"], "is_active": updated["is_active"]}

    async def create_chat_session(self, patient_id: str, title: str | None = None) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/chat_sessions",
            json={"patient_id": patient_id, "title": title or "Acompanhamento IA"},
            prefer="return=representation",
        )
        return rows[0]

    async def ensure_chat_session(self, patient_id: str, session_id: str | None) -> dict:
        if session_id:
            rows = await self._request(
                "GET",
                "/rest/v1/chat_sessions",
                params={
                    "id": f"eq.{session_id}",
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "limit": "1",
                },
            )
            if rows:
                return rows[0]

        return await self.create_chat_session(patient_id)

    async def get_chat_session(self, session_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/chat_sessions",
            params={"id": f"eq.{session_id}", "select": "*", "limit": "1"},
        )
        session = rows[0] if rows else None
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa nao encontrada.",
            )
        return session

    async def resolve_chat_patient(
        self,
        token: str,
        *,
        patient_id: str | None = None,
        session_id: str | None = None,
    ) -> tuple[dict, dict, str]:
        profile = await self.get_authenticated_profile(token)
        session = await self.get_chat_session(session_id) if session_id else None

        if profile["role"] == "patient":
            patient = await self.get_patient_by_user_id(profile["id"])
            if patient_id and patient_id != patient["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Paciente nao pode acessar chat de outro paciente.",
                )
            if session and session["patient_id"] != patient["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Conversa fora do paciente autenticado.",
                )
            return profile, patient, "patient"

        if profile["role"] == "nutritionist":
            nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
            if session:
                patient = await self._get_patient(session["patient_id"])
            elif patient_id:
                patient = await self._get_patient(patient_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="patient_id e obrigatorio para nutricionistas.",
                )

            if patient["nutritionist_id"] != nutritionist["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Nutricionista sem acesso a este paciente.",
                )
            return profile, patient, "nutritionist"

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins nao participam do chat clinico.",
        )

    async def list_authorized_chat_sessions(
        self,
        token: str,
        patient_id: str | None = None,
    ) -> list[dict]:
        _, patient, _ = await self.resolve_chat_patient(token, patient_id=patient_id)
        return await self._request(
            "GET",
            "/rest/v1/chat_sessions",
            params={
                "patient_id": f"eq.{patient['id']}",
                "select": "*",
                "order": "updated_at.desc,created_at.desc",
            },
        )

    async def create_authorized_chat_session(
        self,
        token: str,
        patient_id: str | None,
        title: str | None = None,
    ) -> dict:
        _, patient, _ = await self.resolve_chat_patient(token, patient_id=patient_id)
        return await self.create_chat_session(patient["id"], title)

    async def get_authorized_chat_messages(
        self,
        token: str,
        session_id: str,
    ) -> list[dict]:
        await self.resolve_chat_patient(token, session_id=session_id)
        return await self._request(
            "GET",
            "/rest/v1/chat_messages",
            params={
                "session_id": f"eq.{session_id}",
                "select": "*",
                "order": "created_at.asc",
                "limit": "300",
            },
        )

    async def insert_chat_message(
        self,
        session_id: str,
        sender: str,
        content: str,
        metadata: dict | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/chat_messages",
            json={
                "session_id": session_id,
                "sender": sender,
                "content": content,
                "metadata": metadata or {},
            },
            prefer="return=representation",
        )
        await self._request(
            "PATCH",
            "/rest/v1/chat_sessions",
            params={"id": f"eq.{session_id}"},
            json={"updated_at": datetime.now(UTC).isoformat()},
        )
        return rows[0]

    async def _get_patient(self, patient_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/patients",
            params={"id": f"eq.{patient_id}", "select": "*", "limit": "1"},
        )
        patient = rows[0] if rows else None
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paciente nao encontrado.",
            )
        return patient

    async def _attach_profiles(self, patients: list[dict]) -> list[dict]:
        if not patients:
            return []

        profile_ids = [patient["user_id"] for patient in patients]
        profiles = await self._request(
            "GET",
            "/rest/v1/profiles",
            params={
                "id": f"in.({','.join(profile_ids)})",
                "select": "id,full_name,email,role,avatar_url,phone,is_active,created_at",
            },
        )
        by_id = {profile["id"]: profile for profile in profiles}
        return [
            {**patient, "profile": by_id.get(patient["user_id"])}
            for patient in patients
        ]

    async def _rows_by_parent(
        self,
        table: str,
        parent_column: str,
        parent_ids: list[str],
    ) -> dict[str, list[dict]]:
        if not parent_ids:
            return {}

        rows = await self._request(
            "GET",
            f"/rest/v1/{table}",
            params={
                parent_column: f"in.({','.join(parent_ids)})",
                "select": "*",
            },
        )

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(row[parent_column], []).append(row)
        return grouped

    async def _get_recent_messages(self, sessions: list[dict]) -> list[dict]:
        if not sessions:
            return []

        session_ids = [session["id"] for session in sessions[:5]]
        return await self._request(
            "GET",
            "/rest/v1/chat_messages",
            params={
                "session_id": f"in.({','.join(session_ids)})",
                "select": "*",
                "order": "created_at.desc",
                "limit": "80",
            },
        )

    def _extract_error(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text or "Supabase request failed."

        return (
            body.get("msg")
            or body.get("message")
            or body.get("details")
            or body.get("hint")
            or body.get("error_description")
            or body.get("error")
            or "Supabase request failed."
        )
