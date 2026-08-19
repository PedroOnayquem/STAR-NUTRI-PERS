from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta
import re
from time import perf_counter
from typing import Any
import unicodedata
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import HTTPException, UploadFile, status

from ..core.config import settings
from ..schemas.workspace import UpdateMyPatientProfileRequest, UpdatePatientRequest
from .auth_policy import assert_password_change_complete


MAX_NUTRITIONIST_IMAGE_BYTES = 5 * 1024 * 1024
NUTRITIONIST_IMAGE_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_UNSET = object()
TRIAL_ALLOWED_DAYS = {7, 14, 30}
PATIENT_TRIAL_EXPIRED_MESSAGE = (
    "Seu período gratuito expirou. Entre em contato com seu nutricionista para ativar o acesso."
)


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

        started_at = perf_counter()
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

        elapsed_ms = (perf_counter() - started_at) * 1000
        if settings.app_env == "development" and elapsed_ms > 450:
            print(f"[perf:supabase] {method} {path} {elapsed_ms:.0f}ms")

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Erro do Supabase: {self._extract_error(response)}",
            )

        if response.status_code == 204 or not response.text:
            return None

        return response.json()

    async def _storage_request(
        self,
        method: str,
        path: str,
        *,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            **(headers or {}),
        }
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.request(
                    method,
                    f"{self.supabase_url}{path}",
                    headers=request_headers,
                    content=content,
                )
        except httpx.RequestError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível acessar o armazenamento de imagens.",
            ) from None

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível salvar a imagem enviada.",
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

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

        auth_user = response.json()
        assert_password_change_complete(auth_user)
        return auth_user

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
        patients = await self._refresh_patient_access_statuses(patients)

        return {
            "nutritionist": nutritionist,
            "profile": profile,
            "patients": await self._attach_profiles(patients),
        }

    async def update_nutritionist_profile(
        self,
        token: str,
        *,
        professional_name: str | None,
        clinic_name: str | None,
        phone: str | None,
        bio: str | None,
        default_patient_trial_days: int | None,
        remove_image: bool,
        image: UploadFile | None,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem atualizar este perfil.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        image_path: str | None | object = _UNSET
        image_url: str | None | object = _UNSET
        if image is not None:
            uploaded_image = await self._upload_nutritionist_image(nutritionist["id"], image)
            image_path = uploaded_image["path"]
            image_url = uploaded_image["public_url"]
        elif remove_image:
            image_path = None
            image_url = None

        next_professional_name = self._nullable_text(professional_name)
        next_clinic_name = self._nullable_text(clinic_name)
        next_phone = self._nullable_text(phone)
        next_bio = self._nullable_multiline_text(bio)

        nutritionist_payload: dict[str, Any] = {
            "professional_name": next_professional_name,
            "clinic_name": next_clinic_name,
            "phone": next_phone,
            "bio": next_bio,
        }
        if default_patient_trial_days is not None:
            if default_patient_trial_days not in TRIAL_ALLOWED_DAYS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A duração do Trial deve ser 7, 14 ou 30 dias.",
                )
            nutritionist_payload["default_patient_trial_days"] = default_patient_trial_days
        if image_path is not _UNSET:
            nutritionist_payload["avatar_path"] = image_path
            nutritionist_payload["logo_path"] = image_path
            nutritionist_payload["avatar_url"] = image_url
            nutritionist_payload["logo_url"] = image_url

        try:
            updated_rows = await self._request(
                "PATCH",
                "/rest/v1/nutritionists",
                params={"id": f"eq.{nutritionist['id']}"},
                json=nutritionist_payload,
                prefer="return=representation",
            )
        except HTTPException as exc:
            if (
                "default_patient_trial_days" not in nutritionist_payload
                or "default_patient_trial_days" not in str(exc.detail)
            ):
                raise
            nutritionist_payload.pop("default_patient_trial_days", None)
            updated_rows = await self._request(
                "PATCH",
                "/rest/v1/nutritionists",
                params={"id": f"eq.{nutritionist['id']}"},
                json=nutritionist_payload,
                prefer="return=representation",
            )
        updated_nutritionist = updated_rows[0] if updated_rows else {
            **nutritionist,
            **nutritionist_payload,
        }

        profile_payload: dict[str, Any] = {"phone": next_phone}
        if next_professional_name:
            profile_payload["full_name"] = next_professional_name
        if image_url is not _UNSET:
            profile_payload["avatar_url"] = image_url

        updated_profile_rows = await self._request(
            "PATCH",
            "/rest/v1/profiles",
            params={"id": f"eq.{profile['id']}"},
            json=profile_payload,
            prefer="return=representation",
        )
        updated_profile = updated_profile_rows[0] if updated_profile_rows else {
            **profile,
            **profile_payload,
        }

        if image_path is not _UNSET:
            await self._delete_replaced_nutritionist_images(
                nutritionist,
                keep_path=image_path if isinstance(image_path, str) else None,
            )

        return {
            "nutritionist": updated_nutritionist,
            "profile": updated_profile,
        }

    async def _upload_nutritionist_image(
        self,
        nutritionist_id: str,
        image: UploadFile,
    ) -> dict[str, str]:
        mime_type = (image.content_type or "").lower()
        extension = NUTRITIONIST_IMAGE_MIME_TYPES.get(mime_type)
        if not extension:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Envie uma imagem válida nos formatos PNG, JPG, JPEG ou WEBP.",
            )

        content = await image.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selecione uma imagem antes de salvar.",
            )
        if len(content) > MAX_NUTRITIONIST_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="A imagem deve ter no máximo 5 MB.",
            )
        if not self._looks_like_allowed_image(content, mime_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Envie uma imagem válida nos formatos PNG, JPG, JPEG ou WEBP.",
            )

        timestamp = int(datetime.now(UTC).timestamp())
        path = f"{nutritionist_id}/profile-{timestamp}-{uuid.uuid4().hex[:8]}.{extension}"

        await self._storage_request(
            "POST",
            f"/storage/v1/object/nutritionist-avatars/{path}",
            content=content,
            headers={"Content-Type": mime_type, "x-upsert": "false"},
        )
        return {
            "path": path,
            "public_url": self._public_storage_url("nutritionist-avatars", path),
        }

    def _public_storage_url(self, bucket: str, path: str) -> str:
        base_url = (settings.supabase_public_url or self.supabase_url).rstrip("/")
        return f"{base_url}/storage/v1/object/public/{bucket}/{path}"

    async def _delete_replaced_nutritionist_images(
        self,
        nutritionist: dict,
        *,
        keep_path: str | None,
    ) -> None:
        paths = {
            path
            for key in ("avatar_path", "logo_path", "avatar_url", "logo_url")
            if (path := self._nutritionist_image_path(nutritionist.get(key)))
        }
        if keep_path:
            paths.discard(keep_path)

        for path in paths:
            try:
                await self._storage_request(
                    "DELETE",
                    f"/storage/v1/object/nutritionist-avatars/{path}",
                )
            except HTTPException:
                continue

    def _nutritionist_image_path(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None

        bucket_prefix = "nutritionist-avatars/"
        if normalized.startswith(bucket_prefix):
            return normalized[len(bucket_prefix):].split("?", 1)[0]

        storage_marker = "/nutritionist-avatars/"
        if storage_marker in normalized:
            return normalized.split(storage_marker, 1)[1].split("?", 1)[0]

        if normalized.startswith("http://") or normalized.startswith("https://"):
            return None

        return normalized.split("?", 1)[0]

    def _looks_like_allowed_image(self, content: bytes, mime_type: str) -> bool:
        if mime_type in {"image/jpeg", "image/jpg"}:
            return content.startswith(b"\xff\xd8\xff")
        if mime_type == "image/png":
            return content.startswith(b"\x89PNG\r\n\x1a\n")
        if mime_type == "image/webp":
            return content.startswith(b"RIFF") and content[8:12] == b"WEBP"
        return False

    def _nullable_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    def _nullable_multiline_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "\n".join(line.strip() for line in value.strip().splitlines())
        return normalized or None

    async def get_nutritionist_dashboard(self, token: str) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem acessar este dashboard.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        raw_patients = await self._request(
            "GET",
            "/rest/v1/patients",
            params={
                "nutritionist_id": f"eq.{nutritionist['id']}",
                "select": "*",
                "order": "updated_at.desc.nullslast,created_at.desc",
            },
        )
        raw_patients = await self._refresh_patient_access_statuses(raw_patients)
        patients = self._dedupe_patients(await self._attach_profiles(raw_patients))
        active_patients = [
            patient
            for patient in patients
            if self._patient_has_premium_access(patient)
        ]
        active_patient_ids = [patient["id"] for patient in active_patients]
        active_patient_id_set = set(active_patient_ids)
        trial_patients = [patient for patient in patients if patient.get("access_status") == "TRIAL"]
        activated_patients = [patient for patient in patients if patient.get("access_status") == "ACTIVE"]
        expired_patients = [patient for patient in patients if patient.get("access_status") == "EXPIRED"]

        now = datetime.now(UTC)
        today_date = self._dashboard_date(now)
        upcoming_until = now + timedelta(days=7)

        diets, appointments, conditions, metrics = (
            await asyncio.gather(
                self._request(
                    "GET",
                    "/rest/v1/diets",
                    params={
                        "nutritionist_id": f"eq.{nutritionist['id']}",
                        "select": "id,patient_id,title,is_active,updated_at,created_at",
                        "order": "updated_at.desc.nullslast,created_at.desc",
                    },
                ),
                self._request(
                    "GET",
                    "/rest/v1/patient_appointments",
                    params={
                        "nutritionist_id": f"eq.{nutritionist['id']}",
                        "date": f"gte.{today_date}",
                        "status": "neq.cancelado",
                        "select": "id,patient_id,title,type,date,start_time,end_time,status,location,meeting_link",
                        "order": "date.asc,start_time.asc",
                        "limit": "100",
                    },
                ),
                self._fetch_patient_rows(
                    "patient_health_conditions",
                    active_patient_ids,
                    select=(
                        "id,patient_id,condition_type,title,severity,created_at,"
                        "started_at"
                    ),
                    order="created_at.desc",
                    limit=150,
                ),
                self._fetch_patient_rows(
                    "patient_variable_metrics",
                    active_patient_ids,
                    select="id,patient_id,name,recorded_at,created_at",
                    order="recorded_at.desc.nullslast,created_at.desc",
                    limit=300,
                ),
            )
        )

        active_diets = [
            diet
            for diet in diets
            if diet.get("is_active") is not False
            and diet.get("patient_id") in active_patient_id_set
        ]
        appointments_today = [
            appointment
            for appointment in appointments
            if appointment.get("date") == today_date
        ]
        upcoming_appointments = [
            {
                **appointment,
                "scheduled_at": self._appointment_datetime_value(appointment),
            }
            for appointment in appointments
            if self._is_appointment_between(appointment, now, upcoming_until)
        ][:30]
        active_diet_patient_ids = {
            diet["patient_id"] for diet in active_diets if diet.get("patient_id")
        }
        latest_metric_by_patient = self._latest_by_patient(metrics, "recorded_at")
        next_appointment_by_patient = self._latest_by_patient(
            upcoming_appointments,
            "scheduled_at",
            prefer_earliest=True,
        )
        latest_condition_by_patient = self._latest_by_patient(conditions, "created_at")

        alerts = self._build_dashboard_alerts(
            active_patients=active_patients,
            active_diet_patient_ids=active_diet_patient_ids,
            latest_metric_by_patient=latest_metric_by_patient,
            latest_condition_by_patient=latest_condition_by_patient,
            next_appointment_by_patient=next_appointment_by_patient,
            now=now,
        )

        recent_patients = [
            self._dashboard_patient_summary(
                patient,
                latest_metric_by_patient=latest_metric_by_patient,
                next_appointment_by_patient=next_appointment_by_patient,
                latest_condition_by_patient=latest_condition_by_patient,
                active_diet_patient_ids=active_diet_patient_ids,
                now=now,
            )
            for patient in active_patients[:6]
        ]

        return {
            "nutritionist": nutritionist,
            "profile": profile,
            "stats": {
                "active_patients": len(active_patients),
                "trial_patients": len(trial_patients),
                "activated_patients": len(activated_patients),
                "expired_patients": len(expired_patients),
                "appointments_today": len(appointments_today),
                "active_diets": len(active_diets),
                "important_alerts": len(alerts),
            },
            "recent_patients": recent_patients,
            "alerts": alerts[:8],
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
        nutritionist_messages = await self._request(
            "GET",
            "/rest/v1/nutritionist_messages",
            params={"select": "id"},
        )
        patient_messages = await self._request(
            "GET",
            "/rest/v1/patient_messages",
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
                "chat_messages": len(nutritionist_messages) + len(patient_messages),
            },
        }

    async def get_ai_guardrail_metrics(self, token: str, *, days: int = 30) -> dict:
        if days not in {7, 30, 90}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Periodo deve ser 7, 30 ou 90 dias.",
            )
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas administradores acessam metricas de seguranca da IA.",
            )

        since = datetime.now(UTC) - timedelta(days=days)
        events: list[dict] = []
        page_size = 1000
        while len(events) < 5000:
            page = await self._request(
                "GET",
                "/rest/v1/ai_guardrail_events",
                params={
                    "created_at": f"gte.{since.isoformat()}",
                    "select": "id,stage,category,action,severity,rule_ids,created_at",
                    "order": "created_at.desc,id.desc",
                    "limit": str(page_size),
                    "offset": str(len(events)),
                },
            )
            events.extend(page)
            if len(page) < page_size:
                break
        actions = Counter(item.get("action") or "unknown" for item in events)
        categories = Counter(item.get("category") or "unknown" for item in events)
        stages = Counter(item.get("stage") or "unknown" for item in events)
        severities = Counter(item.get("severity") or "unknown" for item in events)
        return {
            "period_days": days,
            "summary": {
                "events": len(events),
                "blocked": actions["blocked"],
                "safe_completed": actions["safe_completed"],
                "redacted_outputs": actions["redacted"],
                "provider_failures": actions["failed"],
            },
            "categories": [
                {"category": key, "count": value}
                for key, value in categories.most_common()
            ],
            "stages": [{"stage": key, "count": value} for key, value in stages.most_common()],
            "severities": [
                {"severity": key, "count": value}
                for key, value in severities.most_common()
            ],
            "recent_events": events[:100],
            "truncated": len(events) == 5000,
        }

    async def get_patient_context_for_nutritionist(
        self,
        token: str,
        patient_id: str,
        *,
        include_chat_context: bool = False,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem acessar este paciente.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        patient = await self._get_patient(patient_id)
        patient = await self._refresh_patient_access_status(patient)
        if patient["nutritionist_id"] != nutritionist["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Paciente fora do seu workspace.",
            )

        return await self.get_patient_context(
            patient,
            nutritionist,
            chat_scope="nutritionist" if include_chat_context else None,
        )

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
        return await self.get_patient_context(patient, nutritionist, chat_scope="patient")

    async def get_patient_chat_context_for_patient(self, token: str) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas pacientes podem acessar este chat pessoal.",
            )

        patient = await self.get_patient_by_user_id(profile["id"])
        self._assert_patient_ai_access(patient)
        patient_profile = profile
        patient_id = patient["id"]

        diets, workouts, variable_metrics, imports = await asyncio.gather(
            self._request(
                "GET",
                "/rest/v1/diets",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "is_active": "eq.true",
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": "2",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/workouts",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "is_active": "eq.true",
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": "2",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_variable_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": (
                        "id,patient_id,name,value,unit,recorded_at,created_at,"
                        "source_type,source_import_id"
                    ),
                    "order": "recorded_at.desc,created_at.desc",
                    "limit": "20",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_imports",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "status": "in.(processed,linked)",
                    "select": (
                        "id,source_type,extracted_payload,confidence_payload,status,"
                        "original_file_name,file_type,created_at"
                    ),
                    "order": "created_at.desc",
                    "limit": "12",
                },
            ),
        )

        meals, exercises = await asyncio.gather(
            self._rows_by_parent("diet_meals", "diet_id", [row["id"] for row in diets]),
            self._rows_by_parent(
                "workout_exercises",
                "workout_id",
                [row["id"] for row in workouts],
            ),
        )
        meal_items = await self._diet_meal_items_by_meal(meals)
        for diet in diets:
            diet["meals"] = self._attach_items_to_meals(
                meals.get(diet["id"], []),
                meal_items,
            )
        for workout in workouts:
            workout["exercises"] = exercises.get(workout["id"], [])

        return {
            "patient": {
                "id": patient["id"],
                "objective": patient.get("objective"),
                "profile": patient_profile,
            },
            "profile": patient_profile,
            "nutritionist": None,
            "main_metrics": [],
            "variable_metrics": variable_metrics,
            "conditions": [],
            "diets": diets,
            "workouts": workouts,
            "nutritionist_chats": [],
            "patient_chats": [],
            "appointments": [],
            "imports": imports,
            "recent_professional_messages": [],
            "recent_personal_messages": [],
        }

    async def get_patient_context(
        self,
        patient: dict,
        nutritionist: dict | None,
        *,
        chat_scope: str | None = None,
    ) -> dict:
        patient = await self._refresh_patient_access_status(patient)
        patient_id = patient["id"]
        (
            patient_profile,
            diets,
            workouts,
            main_metrics,
            variable_metrics,
            conditions,
            appointments,
            imports,
        ) = await asyncio.gather(
            self.get_profile(patient["user_id"]),
            self._request(
                "GET",
                "/rest/v1/diets",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "is_active.desc,created_at.desc",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/workouts",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "is_active.desc,created_at.desc",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_main_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "created_at.desc",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_variable_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "recorded_at.desc,created_at.desc",
                    "limit": "120",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_health_conditions",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "created_at.desc",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_appointments",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "date.desc,start_time.desc",
                    "limit": "120",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_imports",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": "30",
                },
            ),
        )

        meals, exercises = await asyncio.gather(
            self._rows_by_parent("diet_meals", "diet_id", [row["id"] for row in diets]),
            self._rows_by_parent(
                "workout_exercises",
                "workout_id",
                [row["id"] for row in workouts],
            ),
        )
        meal_items = await self._diet_meal_items_by_meal(meals)

        for diet in diets:
            diet["meals"] = self._attach_items_to_meals(
                meals.get(diet["id"], []),
                meal_items,
            )
        for workout in workouts:
            workout["exercises"] = exercises.get(workout["id"], [])

        nutritionist_chats: list[dict] = []
        patient_chats: list[dict] = []
        recent_professional_messages: list[dict] = []
        recent_personal_messages: list[dict] = []

        if chat_scope == "nutritionist" and nutritionist:
            nutritionist_chats = await self.list_nutritionist_chats_for_patient(
                nutritionist["id"],
                patient_id,
            )
        elif chat_scope == "patient":
            patient_chats = await self.list_patient_chats_for_patient(patient_id)

        patient_payload = {**patient, "profile": patient_profile}
        patient_access = self._patient_access_payload(patient)
        if chat_scope == "patient" and not patient_access["has_premium_access"]:
            diets = []
            workouts = []

        if chat_scope == "patient":
            patient_payload["notes"] = None

        return {
            "patient": patient_payload,
            "access": patient_access,
            "profile": patient_profile,
            "nutritionist": nutritionist,
            "main_metrics": main_metrics,
            "variable_metrics": variable_metrics,
            "conditions": conditions,
            "diets": diets,
            "workouts": workouts,
            "nutritionist_chats": nutritionist_chats,
            "patient_chats": patient_chats,
            "appointments": appointments,
            "imports": imports,
            "recent_professional_messages": recent_professional_messages,
            "recent_personal_messages": recent_personal_messages,
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
        patient_payload = self._normalize_patient_access_update(patient_payload)
        if patient_payload:
            updated = await self._request(
                "PATCH",
                "/rest/v1/patients",
                params={"id": f"eq.{patient_id}", "select": "*"},
                json=patient_payload,
                prefer="return=representation",
            )
            patient = await self._refresh_patient_access_status(updated[0])

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

    def _normalize_patient_access_update(self, payload: dict) -> dict:
        normalized = dict(payload)
        access_status = normalized.pop("access_status", None)
        is_active = normalized.pop("is_active", None)

        if access_status not in {None, "ACTIVE", "EXPIRED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status do paciente inválido.",
            )
        if (
            access_status == "ACTIVE" and is_active is False
        ) or (
            access_status == "EXPIRED" and is_active is True
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status e atividade do paciente são incompatíveis.",
            )

        if access_status == "ACTIVE" or is_active is True:
            normalized.update(
                {
                    "access_status": "ACTIVE",
                    "activated_at": datetime.now(UTC).isoformat(),
                    "expired_at": None,
                    "is_active": True,
                }
            )
        elif access_status == "EXPIRED" or is_active is False:
            normalized.update(
                {
                    "access_status": "EXPIRED",
                    "expired_at": datetime.now(UTC).isoformat(),
                    "is_active": False,
                }
            )
        return normalized

    async def get_patient_record_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
    ) -> dict:
        patient = await self._get_patient(patient_id)
        if patient["nutritionist_id"] != nutritionist_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Paciente fora do seu workspace.",
            )
        return await self._refresh_patient_access_status(patient)

    async def search_patients_by_name_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        clean_query = _normalize_search_text(query)
        if not clean_query:
            return []

        rows = await self._request(
            "GET",
            "/rest/v1/patients",
            params={
                "nutritionist_id": f"eq.{nutritionist_id}",
                "select": "*",
                "order": "updated_at.desc.nullslast,created_at.desc",
                "limit": "500",
            },
        )
        patients = self._dedupe_patients(await self._attach_profiles(rows))

        matches: list[tuple[int, str, dict]] = []
        for patient in patients:
            profile = patient.get("profile") or {}
            full_name = profile.get("full_name") or ""
            nickname = (
                patient.get("nickname")
                or profile.get("nickname")
                or profile.get("preferred_name")
                or ""
            )
            normalized_name = _normalize_search_text(full_name)
            normalized_nickname = _normalize_search_text(nickname)
            score = self._patient_name_match_score(
                clean_query,
                normalized_name,
                normalized_nickname,
            )
            if score <= 0:
                continue

            matches.append(
                (
                    score,
                    str(patient.get("updated_at") or patient.get("created_at") or ""),
                    patient,
                )
            )

        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [
            self._compact_patient_lookup(row)
            for _, _, row in matches[: max(1, min(limit, 25))]
        ]

    async def get_patient_profile_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
    ) -> dict:
        patient = await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        profile, main_metrics, variable_metrics = await asyncio.gather(
            self.get_profile(patient["user_id"]),
            self._request(
                "GET",
                "/rest/v1/patient_main_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "id,patient_id,name,value,unit,created_at,updated_at",
                    "order": "created_at.desc",
                    "limit": "80",
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_variable_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "id,patient_id,name,value,unit,recorded_at,created_at",
                    "order": "recorded_at.desc.nullslast,created_at.desc",
                    "limit": "120",
                },
            ),
        )
        metrics = [*variable_metrics, *main_metrics]
        birth_date = patient.get("birth_date")
        return {
            "id": patient["id"],
            "full_name": profile.get("full_name"),
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "gender": patient.get("gender"),
            "birth_date": birth_date,
            "age": calculate_age(birth_date),
            "height_cm": self._height_cm_from_metrics(metrics),
            "objective": patient.get("objective"),
            "notes": patient.get("notes"),
            "is_active": patient.get("is_active"),
            "created_at": patient.get("created_at"),
            "updated_at": patient.get("updated_at"),
        }

    async def list_patient_metrics_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        limit: int = 40,
    ) -> dict:
        await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        main_metrics, variable_metrics = await asyncio.gather(
            self._request(
                "GET",
                "/rest/v1/patient_main_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "created_at.desc",
                    "limit": str(max(1, min(limit, 120))),
                },
            ),
            self._request(
                "GET",
                "/rest/v1/patient_variable_metrics",
                params={
                    "patient_id": f"eq.{patient_id}",
                    "select": "*",
                    "order": "recorded_at.desc.nullslast,created_at.desc",
                    "limit": str(max(1, min(limit, 120))),
                },
            ),
        )
        metrics = [*variable_metrics, *main_metrics]
        return {
            "main_metrics": main_metrics,
            "variable_metrics": variable_metrics,
            "latest_weight": self._latest_metric_by_terms(metrics, ("peso", "weight")),
            "height_cm": self._height_cm_from_metrics(metrics),
        }

    async def list_patient_conditions_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        limit: int = 40,
    ) -> list[dict]:
        await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        return await self._request(
            "GET",
            "/rest/v1/patient_health_conditions",
            params={
                "patient_id": f"eq.{patient_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": str(max(1, min(limit, 120))),
            },
        )

    async def get_patient_summary_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
    ) -> dict:
        patient = await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        nutritionist_rows = await self._request(
            "GET",
            "/rest/v1/nutritionists",
            params={"id": f"eq.{nutritionist_id}", "select": "*", "limit": "1"},
        )
        nutritionist = nutritionist_rows[0] if nutritionist_rows else None
        context = await self.get_patient_context(
            patient,
            nutritionist,
            chat_scope="nutritionist",
        )
        profile = await self.get_patient_profile_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        metrics = {
            "main_metrics": context.get("main_metrics", [])[:30],
            "variable_metrics": context.get("variable_metrics", [])[:40],
            "latest_weight": self._latest_metric_by_terms(
                [
                    *context.get("variable_metrics", []),
                    *context.get("main_metrics", []),
                ],
                ("peso", "weight"),
            ),
            "height_cm": profile.get("height_cm"),
        }
        return {
            "profile": profile,
            "metrics": metrics,
            "conditions": context.get("conditions", [])[:40],
            "diets": context.get("diets", [])[:5],
            "workouts": context.get("workouts", [])[:5],
            "appointments": context.get("appointments", [])[:20],
        }

    async def update_patient_profile_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        payload: dict,
    ) -> dict:
        patient = await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        allowed_patient_fields = {
            "birth_date",
            "gender",
            "objective",
            "notes",
            "is_active",
        }
        patient_payload = {
            key: value
            for key, value in payload.items()
            if key in allowed_patient_fields
        }
        profile_payload = {
            key: value
            for key, value in payload.items()
            if key in {"full_name", "phone"}
        }

        if patient_payload:
            updated = await self._request(
                "PATCH",
                "/rest/v1/patients",
                params={"id": f"eq.{patient_id}", "select": "*"},
                json=patient_payload,
                prefer="return=representation",
            )
            patient = updated[0] if updated else {**patient, **patient_payload}

        if profile_payload:
            await self._request(
                "PATCH",
                "/rest/v1/profiles",
                params={"id": f"eq.{patient['user_id']}", "select": "*"},
                json=profile_payload,
                prefer="return=representation",
            )

        updated_profile = await self.get_patient_profile_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        mismatched_fields = {
            key: {
                "expected": value,
                "saved": updated_profile.get(key),
            }
            for key, value in payload.items()
            if updated_profile.get(key) != value
        }
        if mismatched_fields:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Não foi possível confirmar que o cadastro foi salvo.",
                    "fields": mismatched_fields,
                },
            )
        return updated_profile

    async def update_patient_record_for_nutritionist(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        payload: dict,
    ) -> dict:
        patient = await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        allowed_fields = {
            "birth_date",
            "gender",
            "objective",
            "notes",
        }
        patient_payload = {
            key: value
            for key, value in payload.items()
            if key in allowed_fields
        }
        if not patient_payload:
            return patient

        await self._request(
            "PATCH",
            "/rest/v1/patients",
            params={"id": f"eq.{patient_id}", "select": "*"},
            json=patient_payload,
            prefer="return=representation",
        )
        verified = await self.get_patient_record_for_nutritionist(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
        )
        mismatched_fields = {
            key: {
                "expected": value,
                "saved": verified.get(key),
            }
            for key, value in patient_payload.items()
            if verified.get(key) != value
        }
        if mismatched_fields:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Não foi possível confirmar que o cadastro foi salvo.",
                    "fields": mismatched_fields,
                },
            )
        return verified

    async def update_my_patient_profile(
        self,
        token: str,
        payload: UpdateMyPatientProfileRequest,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas pacientes podem editar este perfil.",
            )

        patient = await self.get_patient_by_user_id(profile["id"])
        patient_payload = payload.model_dump(
            exclude_unset=True,
            exclude={"full_name", "phone"},
        )
        if patient_payload:
            updated = await self._request(
                "PATCH",
                "/rest/v1/patients",
                params={"id": f"eq.{patient['id']}", "select": "*"},
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
                params={"id": f"eq.{profile['id']}", "select": "*"},
                json=profile_payload,
                prefer="return=representation",
            )

        profile_row = await self.get_profile(profile["id"])
        return {**patient, "profile": profile_row}

    async def deactivate_patient(self, token: str, patient_id: str) -> dict:
        updated = await self.update_patient(
            token,
            patient_id,
            UpdatePatientRequest(is_active=False, access_status="EXPIRED"),
        )
        return {
            "id": updated["id"],
            "access_status": updated["access_status"],
            "is_active": updated["is_active"],
        }

    async def activate_patient(
        self,
        token: str,
        patient_id: str,
        payload: Any | None = None,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas podem ativar pacientes.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        patient = await self._get_patient(patient_id)
        if patient["nutritionist_id"] != nutritionist["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Paciente fora do seu workspace.",
            )

        trial_days = getattr(payload, "trial_days", None) if payload else None

        rows = await self._request(
            "PATCH",
            "/rest/v1/patients",
            params={"id": f"eq.{patient_id}", "select": "*"},
            json=self._patient_activation_payload(trial_days),
            prefer="return=representation",
        )
        updated = await self._refresh_patient_access_status(rows[0])
        profile_row = await self.get_profile(updated["user_id"])
        return {**updated, "profile": profile_row}

    def _patient_activation_payload(self, trial_days: int | None) -> dict:
        if trial_days is not None and trial_days not in TRIAL_ALLOWED_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A duração do Trial deve ser 7, 14 ou 30 dias.",
            )

        activated_at = datetime.now(UTC)
        if trial_days is not None:
            return {
                "access_status": "TRIAL",
                "trial_days": trial_days,
                "trial_started_at": activated_at.isoformat(),
                "trial_ends_at": (activated_at + timedelta(days=trial_days)).isoformat(),
                "activated_at": None,
                "expired_at": None,
                "is_active": True,
            }

        return {
            "access_status": "ACTIVE",
            "activated_at": activated_at.isoformat(),
            "expired_at": None,
            "is_active": True,
        }

    async def insert_ai_action_log(self, payload: dict) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/ai_action_logs",
            json=payload,
            prefer="return=representation",
        )
        return await self._get_row_by_id("ai_action_logs", rows[0]["id"])

    async def insert_ai_guardrail_event(self, payload: dict) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/ai_guardrail_events",
            json=payload,
            prefer="return=representation",
        )
        return rows[0]

    async def list_conversation_memories(
        self,
        *,
        conversation_ids: list[str],
        chat_type: str,
        user_id: str,
        patient_id: str | None,
        nutritionist_id: str | None,
    ) -> list[dict]:
        if not conversation_ids:
            return []

        params = {
            "conversation_id": f"in.({','.join(conversation_ids)})",
            "chat_type": f"eq.{chat_type}",
            "user_id": f"eq.{user_id}",
            "select": "*",
            "order": "last_message_at.desc,updated_at.desc",
        }
        params["patient_id"] = f"eq.{patient_id}" if patient_id else "is.null"
        params["nutritionist_id"] = (
            f"eq.{nutritionist_id}" if nutritionist_id else "is.null"
        )

        return await self._request(
            "GET",
            "/rest/v1/ai_conversation_memories",
            params=params,
        )

    async def upsert_conversation_memory(self, payload: dict) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/ai_conversation_memories",
            json=payload,
            params={"on_conflict": "conversation_id,user_id,chat_type"},
            prefer="resolution=merge-duplicates,return=representation",
        )
        return await self._get_row_by_id("ai_conversation_memories", rows[0]["id"])

    async def list_ai_action_logs_for_context(
        self,
        *,
        chat_scope: str,
        user_id: str,
        patient_id: str | None,
        nutritionist_id: str | None,
        conversation_id: str | None = None,
        limit: int = 12,
    ) -> list[dict]:
        params = {
            "chat_scope": f"eq.{chat_scope}",
            "user_id": f"eq.{user_id}",
            "select": (
                "id,conversation_id,patient_id,nutritionist_id,tool_name,intent,"
                "status,success,requires_confirmation,result,error_message,created_at"
            ),
            "order": "created_at.desc",
            "limit": str(limit),
        }
        params["patient_id"] = f"eq.{patient_id}" if patient_id else "is.null"
        params["nutritionist_id"] = (
            f"eq.{nutritionist_id}" if nutritionist_id else "is.null"
        )
        if conversation_id:
            params["conversation_id"] = f"eq.{conversation_id}"

        return await self._request(
            "GET",
            "/rest/v1/ai_action_logs",
            params=params,
        )

    async def get_ai_conversation_state(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> dict | None:
        rows = await self._request(
            "GET",
            "/rest/v1/ai_conversation_state",
            params={
                "conversation_id": f"eq.{conversation_id}",
                "user_id": f"eq.{user_id}",
                "expires_at": f"gt.{datetime.now(UTC).isoformat()}",
                "select": "*",
                "order": "updated_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def upsert_ai_conversation_state(self, payload: dict) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/ai_conversation_state",
            json=payload,
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    async def clear_ai_conversation_state(self, state_id: str) -> None:
        await self._request(
            "DELETE",
            "/rest/v1/ai_conversation_state",
            params={"id": f"eq.{state_id}"},
        )

    async def _get_row_by_id(self, table: str, row_id: str) -> dict:
        rows = await self._request(
            "GET",
            f"/rest/v1/{table}",
            params={"id": f"eq.{row_id}", "select": "*", "limit": "1"},
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Não foi possível confirmar o registro salvo em {table}.",
            )
        return rows[0]

    async def create_health_condition_record(
        self,
        *,
        patient_id: str,
        condition_type: str,
        title: str,
        description: str,
        injury_local: str | None = None,
        notes: str | None = None,
        origin: str | None = None,
        recommendations: str | None = None,
        severity: str | None = None,
        started_at: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/patient_health_conditions",
            json={
                "patient_id": patient_id,
                "condition_type": condition_type,
                "title": title,
                "description": description,
                "injury_local": injury_local,
                "notes": notes,
                "origin": origin,
                "recommendations": recommendations,
                "severity": severity,
                "started_at": started_at,
            },
            prefer="return=representation",
        )
        return await self._get_row_by_id("patient_health_conditions", rows[0]["id"])

    async def create_training_plan_record(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        title: str,
        objective: str | None,
        restrictions: list[str],
        observations: str | None,
        status: str = "active",
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/training_plans",
            json={
                "nutritionist_id": nutritionist_id,
                "patient_id": patient_id,
                "title": title,
                "objective": objective,
                "restrictions": restrictions,
                "observations": observations,
                "status": status,
                "created_by_ai": True,
            },
            prefer="return=representation",
        )
        return await self._get_row_by_id("training_plans", rows[0]["id"])

    async def create_ai_training_plan(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        title: str,
        objective: str | None,
        restrictions: list[str],
        observations: str | None,
        days: list[dict],
    ) -> dict:
        result = await self._request(
            "POST",
            "/rest/v1/rpc/create_ai_training_plan",
            json={
                "p_nutritionist_id": nutritionist_id,
                "p_patient_id": patient_id,
                "p_title": title,
                "p_objective": objective,
                "p_restrictions": restrictions,
                "p_observations": observations,
                "p_days": days,
            },
        )
        if not isinstance(result, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="O banco retornou uma confirmacao invalida ao salvar o treino.",
            )
        return result

    async def create_training_day_records(
        self,
        *,
        training_plan_id: str,
        days: list[dict],
    ) -> list[dict]:
        rows = await self._request(
            "POST",
            "/rest/v1/training_days",
            json=[
                {
                    "training_plan_id": training_plan_id,
                    "name": day["name"],
                    "focus": day.get("focus"),
                    "order_index": index,
                }
                for index, day in enumerate(days)
            ],
            prefer="return=representation",
        )
        return rows or []

    async def create_training_exercise_records(self, exercises: list[dict]) -> list[dict]:
        rows = await self._request(
            "POST",
            "/rest/v1/training_exercises",
            json=exercises,
            prefer="return=representation",
        )
        return rows or []

    async def update_training_plan_observation(
        self,
        *,
        training_plan_id: str,
        observation: str,
    ) -> dict:
        plan = await self.get_training_plan(training_plan_id)
        current = str(plan.get("observations") or "").strip()
        next_observations = (
            f"{current}\n{observation}".strip()
            if current
            else observation
        )
        rows = await self._request(
            "PATCH",
            "/rest/v1/training_plans",
            params={"id": f"eq.{training_plan_id}", "select": "*"},
            json={"observations": next_observations},
            prefer="return=representation",
        )
        return rows[0]

    async def get_training_plan(self, training_plan_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/training_plans",
            params={"id": f"eq.{training_plan_id}", "select": "*", "limit": "1"},
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plano de treino nao encontrado.",
            )
        return rows[0]

    async def create_workout_record(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        title: str,
        description: str | None,
        frequency_per_week: int | None,
        is_active: bool = True,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/workouts",
            json={
                "nutritionist_id": nutritionist_id,
                "patient_id": patient_id,
                "title": title,
                "description": description,
                "frequency_per_week": frequency_per_week,
                "is_active": is_active,
            },
            prefer="return=representation",
        )
        return rows[0]

    async def create_workout_exercise_records(
        self,
        *,
        workout_id: str,
        exercises: list[dict],
    ) -> list[dict]:
        rows = await self._request(
            "POST",
            "/rest/v1/workout_exercises",
            json=[
                {
                    "workout_id": workout_id,
                    "exercise_name": exercise["exercise_name"],
                    "muscle_group": exercise.get("muscle_group"),
                    "sets": exercise.get("sets"),
                    "reps": exercise.get("reps"),
                    "rest_time": exercise.get("rest"),
                    "load_info": exercise.get("load_guidance"),
                    "notes": exercise.get("notes"),
                }
                for exercise in exercises
            ],
            prefer="return=representation",
        )
        return rows or []

    async def find_similar_health_condition(
        self,
        *,
        patient_id: str,
        condition_type: str,
        title: str,
    ) -> dict | None:
        rows = await self._request(
            "GET",
            "/rest/v1/patient_health_conditions",
            params={
                "patient_id": f"eq.{patient_id}",
                "condition_type": f"eq.{condition_type}",
                "title": f"ilike.*{title[:48]}*",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def get_latest_variable_metric(
        self,
        *,
        patient_id: str,
        name: str,
    ) -> dict | None:
        rows = await self._request(
            "GET",
            "/rest/v1/patient_variable_metrics",
            params={
                "patient_id": f"eq.{patient_id}",
                "name": f"ilike.*{name}*",
                "select": "*",
                "order": "recorded_at.desc,created_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def create_variable_metric_record(
        self,
        *,
        patient_id: str,
        name: str,
        value: str,
        unit: str | None = None,
        recorded_at: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/patient_variable_metrics",
            json={
                "patient_id": patient_id,
                "name": name,
                "value": value,
                "unit": unit,
                "recorded_at": recorded_at,
            },
            prefer="return=representation",
        )
        return rows[0]

    async def get_active_diet_with_meals(self, patient_id: str) -> dict | None:
        rows = await self._request(
            "GET",
            "/rest/v1/diets",
            params={
                "patient_id": f"eq.{patient_id}",
                "is_active": "eq.true",
                "select": "*",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        diet = rows[0] if rows else None
        if not diet:
            return None

        meals = await self._request(
            "GET",
            "/rest/v1/diet_meals",
            params={
                "diet_id": f"eq.{diet['id']}",
                "select": "*",
                "order": "meal_time.asc,created_at.asc",
            },
        )
        items_by_meal = await self._rows_by_parent(
            "diet_meal_items",
            "meal_id",
            [meal["id"] for meal in meals],
        )
        diet["meals"] = self._attach_items_to_meals(meals, items_by_meal)
        return diet

    async def get_diet_record(self, diet_id: str) -> dict:
        return await self._get_row_by_id("diets", diet_id)

    async def create_diet_record(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        title: str,
        description: str | None,
        calories: float | None,
        protein: float | None,
        carbs: float | None,
        fats: float | None,
        water_goal_ml: float | None,
        is_active: bool,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/diets",
            json={
                "nutritionist_id": nutritionist_id,
                "patient_id": patient_id,
                "title": title,
                "description": description,
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fats": fats,
                "water_goal_ml": water_goal_ml,
                "is_active": is_active,
            },
            prefer="return=representation",
        )
        return await self._get_row_by_id("diets", rows[0]["id"])

    async def update_diet_record(self, *, diet_id: str, payload: dict) -> dict:
        rows = await self._request(
            "PATCH",
            "/rest/v1/diets",
            params={"id": f"eq.{diet_id}", "select": "*"},
            json=payload,
            prefer="return=representation",
        )
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plano alimentar nao encontrado.",
            )
        return await self._get_row_by_id("diets", rows[0]["id"])

    async def create_diet_meal_record(
        self,
        *,
        diet_id: str,
        meal_name: str,
        foods: list[dict],
        meal_time: str | None = None,
        notes: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/diet_meals",
            json={
                "diet_id": diet_id,
                "meal_name": meal_name,
                "meal_time": meal_time,
                "foods": foods,
                "notes": notes,
            },
            prefer="return=representation",
        )
        return rows[0]

    async def update_diet_meal_foods(
        self,
        *,
        meal_id: str,
        foods: list[dict],
    ) -> dict:
        rows = await self._request(
            "PATCH",
            "/rest/v1/diet_meals",
            params={"id": f"eq.{meal_id}", "select": "*"},
            json={"foods": foods},
            prefer="return=representation",
        )
        return rows[0]

    async def update_diet_macro_totals(
        self,
        *,
        diet_id: str,
        payload: dict,
    ) -> dict:
        rows = await self._request(
            "PATCH",
            "/rest/v1/diets",
            params={"id": f"eq.{diet_id}", "select": "*"},
            json=payload,
            prefer="return=representation",
        )
        return await self._get_row_by_id("diets", rows[0]["id"])

    async def search_taco_foods(
        self,
        *,
        query: str,
        category: str | None = None,
        limit: int = 8,
    ) -> list[dict]:
        params = {
            "select": "*",
            "order": "name.asc",
            "limit": str(min(max(limit, 1), 20)),
        }
        safe_query = _postgrest_search_term(query)
        if safe_query:
            normalized = _normalize_search_text(safe_query)
            params["or"] = (
                f"(name.ilike.*{safe_query}*,search_name.ilike.*{normalized}*,"
                f"normalized_name.ilike.*{normalized}*)"
            )
        if category:
            params["category"] = f"eq.{category}"

        return await self._request(
            "GET",
            "/rest/v1/taco_foods",
            params=params,
        )

    async def get_taco_food(self, food_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/taco_foods",
            params={
                "id": f"eq.{food_id}",
                "select": "*",
                "limit": "1",
            },
        )
        food = rows[0] if rows else None
        if not food:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alimento TACO nao encontrado.",
            )
        return food

    async def find_taco_food(
        self,
        *,
        food_id: str | None = None,
        query: str | None = None,
    ) -> dict | None:
        if food_id:
            return await self.get_taco_food(food_id)
        if not query:
            return None
        foods = await self.search_taco_foods(query=query, limit=1)
        return foods[0] if foods else None

    async def create_diet_meal_item(
        self,
        *,
        meal_id: str,
        taco_food_id: str | None,
        custom_food_name: str | None,
        quantity_g: float,
        nutrients: dict,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/diet_meal_items",
            json={
                "meal_id": meal_id,
                "taco_food_id": taco_food_id,
                "custom_food_name": custom_food_name,
                "quantity_g": quantity_g,
                "energy_kcal": nutrients.get("energy_kcal"),
                "protein_g": nutrients.get("protein_g"),
                "carbohydrate_g": nutrients.get("carbohydrate_g"),
                "lipid_g": nutrients.get("lipid_g"),
                "fiber_g": nutrients.get("fiber_g"),
                "sodium_mg": nutrients.get("sodium_mg"),
            },
            prefer="return=representation",
        )
        return await self._get_row_by_id("diet_meal_items", rows[0]["id"])

    async def find_appointment(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        date: str,
        start_time: str,
    ) -> dict | None:
        rows = await self._request(
            "GET",
            "/rest/v1/patient_appointments",
            params={
                "nutritionist_id": f"eq.{nutritionist_id}",
                "patient_id": f"eq.{patient_id}",
                "date": f"eq.{date}",
                "start_time": f"eq.{start_time}",
                "status": "neq.cancelado",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    async def create_patient_appointment(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        title: str,
        type: str,
        date: str,
        start_time: str,
        end_time: str | None = None,
        location: str | None = None,
        meeting_link: str | None = None,
        status: str = "agendado",
        description: str | None = None,
        notes: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/patient_appointments",
            json={
                "nutritionist_id": nutritionist_id,
                "patient_id": patient_id,
                "title": title,
                "type": type,
                "description": description,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
                "meeting_link": meeting_link,
                "status": status,
                "notes": notes,
            },
            prefer="return=representation",
        )
        return await self._get_row_by_id("patient_appointments", rows[0]["id"])

    async def create_appointment_record(
        self,
        *,
        nutritionist_id: str,
        patient_id: str,
        title: str,
        scheduled_at: str,
        created_by: str,
        notes: str | None = None,
    ) -> dict:
        parsed = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        local = parsed.astimezone(ZoneInfo("America/Sao_Paulo"))
        return await self.create_patient_appointment(
            nutritionist_id=nutritionist_id,
            patient_id=patient_id,
            title=title,
            type="consulta",
            date=local.date().isoformat(),
            start_time=local.time().replace(microsecond=0).isoformat(),
            notes=notes,
        )

    async def resolve_nutritionist_patient(
        self,
        token: str,
        patient_id: str,
    ) -> tuple[dict, dict, dict]:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas acessam chats profissionais.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        patient = await self._get_patient(patient_id)
        if patient["nutritionist_id"] != nutritionist["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Paciente fora do seu workspace profissional.",
            )
        return profile, nutritionist, patient

    async def resolve_patient_owner(self, token: str) -> tuple[dict, dict]:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "patient":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas pacientes acessam chats pessoais.",
            )
        patient = await self.get_patient_by_user_id(profile["id"])
        self._assert_patient_ai_access(patient)
        return profile, patient

    async def list_nutritionist_chats_for_patient(
        self,
        nutritionist_id: str,
        patient_id: str | None,
        *,
        chat_scope: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        resolved_scope = chat_scope or ("patient" if patient_id else "general")
        params = {
            "nutritionist_id": f"eq.{nutritionist_id}",
            "select": "*",
            "order": "updated_at.desc,created_at.desc",
            "chat_scope": f"eq.{resolved_scope}",
        }
        params["patient_id"] = f"eq.{patient_id}" if patient_id else "is.null"
        if limit:
            params["limit"] = str(limit)

        return await self._request(
            "GET",
            "/rest/v1/nutritionist_chats",
            params=params,
        )

    async def list_patient_chats_for_patient(
        self,
        patient_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict]:
        params = {
            "patient_id": f"eq.{patient_id}",
            "select": "*",
            "order": "updated_at.desc,created_at.desc",
        }
        if limit:
            params["limit"] = str(limit)

        return await self._request(
            "GET",
            "/rest/v1/patient_chats",
            params=params,
        )

    async def list_authorized_nutritionist_chats(
        self,
        token: str,
        patient_id: str | None = None,
        *,
        chat_scope: str | None = None,
    ) -> list[dict]:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas acessam chats profissionais.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        if chat_scope and chat_scope not in {"general", "patient"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Escopo de chat invalido.",
            )
        if chat_scope == "general":
            patient_id = None
        if patient_id:
            await self.resolve_nutritionist_patient(token, patient_id)

        if settings.app_env == "development":
            print(
                "GET sessions:",
                {
                    "nutritionist_id": nutritionist["id"],
                    "chat_scope": chat_scope or ("patient" if patient_id else "general"),
                    "patient_id": patient_id,
                },
            )

        return await self.list_nutritionist_chats_for_patient(
            nutritionist["id"],
            patient_id,
            chat_scope=chat_scope,
        )

    async def list_authorized_patient_chats(self, token: str) -> list[dict]:
        _, patient = await self.resolve_patient_owner(token)
        return await self.list_patient_chats_for_patient(patient["id"])

    async def create_nutritionist_chat(
        self,
        nutritionist_id: str,
        patient_id: str | None,
        title: str | None = None,
        *,
        chat_scope: str | None = None,
    ) -> dict:
        resolved_scope = chat_scope or ("patient" if patient_id else "general")
        if resolved_scope == "patient" and not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chat por paciente exige paciente em foco.",
            )
        if resolved_scope == "general":
            patient_id = None

        rows = await self._request(
            "POST",
            "/rest/v1/nutritionist_chats",
            json={
                "chat_scope": resolved_scope,
                "nutritionist_id": nutritionist_id,
                "patient_id": patient_id,
                "title": title
                or (
                    "Nova conversa profissional"
                    if patient_id
                    else "Nova conversa geral"
                ),
            },
            prefer="return=representation",
        )
        return await self._get_row_by_id("nutritionist_chats", rows[0]["id"])

    async def create_patient_chat(
        self,
        patient_id: str,
        title: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/patient_chats",
            json={
                "patient_id": patient_id,
                "title": title or "Nova conversa pessoal",
            },
            prefer="return=representation",
        )
        return rows[0]

    async def create_authorized_nutritionist_chat(
        self,
        token: str,
        patient_id: str | None = None,
        title: str | None = None,
        *,
        chat_scope: str | None = None,
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas criam chats profissionais.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        resolved_scope = chat_scope or ("patient" if patient_id else "general")
        resolved_patient_id: str | None = None
        if resolved_scope == "patient" and patient_id:
            _, _, patient = await self.resolve_nutritionist_patient(
                token,
                patient_id,
            )
            resolved_patient_id = patient["id"]
        elif resolved_scope == "patient":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chat por paciente exige paciente em foco.",
            )

        if settings.app_env == "development":
            print(
                "POST session:",
                {
                    "nutritionist_id": nutritionist["id"],
                    "chat_scope": resolved_scope,
                    "patient_id": resolved_patient_id,
                    "title": title,
                },
            )

        return await self.create_nutritionist_chat(
            nutritionist["id"],
            resolved_patient_id,
            title,
            chat_scope=resolved_scope,
        )

    async def create_authorized_patient_chat(
        self,
        token: str,
        title: str | None = None,
    ) -> dict:
        _, patient = await self.resolve_patient_owner(token)
        return await self.create_patient_chat(patient["id"], title)

    async def get_nutritionist_chat(
        self,
        chat_id: str,
        *,
        chat_scope: str | None = None,
        nutritionist_id: str,
        patient_id: str | None | object = _UNSET,
    ) -> dict:
        params = {
            "id": f"eq.{chat_id}",
            "nutritionist_id": f"eq.{nutritionist_id}",
            "select": "*",
            "limit": "1",
        }
        if patient_id is not _UNSET:
            params["patient_id"] = f"eq.{patient_id}" if patient_id else "is.null"
        if chat_scope:
            params["chat_scope"] = f"eq.{chat_scope}"

        rows = await self._request(
            "GET",
            "/rest/v1/nutritionist_chats",
            params=params,
        )
        chat = rows[0] if rows else None
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa profissional nao encontrada.",
            )
        return chat

    async def get_patient_chat(self, chat_id: str, *, patient_id: str) -> dict:
        rows = await self._request(
            "GET",
            "/rest/v1/patient_chats",
            params={
                "id": f"eq.{chat_id}",
                "patient_id": f"eq.{patient_id}",
                "select": "*",
                "limit": "1",
            },
        )
        chat = rows[0] if rows else None
        if not chat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversa pessoal nao encontrada.",
            )
        return chat

    async def ensure_nutritionist_chat(
        self,
        nutritionist_id: str,
        patient_id: str | None,
        chat_id: str | None,
        *,
        chat_scope: str | None = None,
    ) -> dict:
        resolved_scope = chat_scope or ("patient" if patient_id else "general")
        if chat_id:
            return await self.get_nutritionist_chat(
                chat_id,
                chat_scope=resolved_scope,
                nutritionist_id=nutritionist_id,
                patient_id=patient_id,
            )
        return await self.create_nutritionist_chat(
            nutritionist_id,
            patient_id,
            chat_scope=resolved_scope,
        )

    async def ensure_patient_chat(
        self,
        patient_id: str,
        chat_id: str | None,
    ) -> dict:
        if chat_id:
            return await self.get_patient_chat(chat_id, patient_id=patient_id)
        return await self.create_patient_chat(patient_id)

    async def maybe_update_chat_title(
        self,
        *,
        table: str,
        chat: dict,
        content: str,
    ) -> None:
        current_title = (chat.get("title") or "").strip()
        default_titles = {
            "Nova conversa",
            "Nova conversa geral",
            "Nova conversa pessoal",
            "Nova conversa profissional",
            "Acompanhamento IA",
            "Conversa geral",
            "Conversa pessoal",
            "Conversa profissional",
        }
        if current_title and current_title not in default_titles:
            return

        clean_title = " ".join(content.split())
        if not clean_title:
            return

        await self._request(
            "PATCH",
            f"/rest/v1/{table}",
            params={"id": f"eq.{chat['id']}"},
            json={"title": clean_title[:80]},
        )

    async def list_authorized_nutritionist_messages(
        self,
        token: str,
        chat_id: str,
        limit: int = 120,
        offset: int = 0,
    ) -> list[dict]:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas acessam mensagens profissionais.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        await self.get_nutritionist_chat(chat_id, nutritionist_id=nutritionist["id"])
        return await self._list_chat_messages(
            "nutritionist_messages",
            chat_id,
            limit=limit,
            offset=offset,
        )

    async def list_authorized_patient_messages(
        self,
        token: str,
        chat_id: str,
        limit: int = 120,
        offset: int = 0,
    ) -> list[dict]:
        _, patient = await self.resolve_patient_owner(token)
        await self.get_patient_chat(chat_id, patient_id=patient["id"])
        return await self._list_chat_messages(
            "patient_messages",
            chat_id,
            limit=limit,
            offset=offset,
        )

    async def insert_chat_message(
        self,
        *,
        messages_table: str,
        chats_table: str,
        chat_id: str,
        sender: str,
        content: str,
        metadata: dict | None = None,
        touch_chat: bool = True,
    ) -> dict:
        rows = await self._request(
            "POST",
            f"/rest/v1/{messages_table}",
            json={
                "chat_id": chat_id,
                "sender": sender,
                "content": content,
                "metadata": metadata or {},
            },
            prefer="return=representation",
        )
        if touch_chat:
            await self._request(
                "PATCH",
                f"/rest/v1/{chats_table}",
                params={"id": f"eq.{chat_id}"},
                json={"updated_at": datetime.now(UTC).isoformat()},
            )
        return rows[0]

    async def _list_chat_messages(
        self,
        table: str,
        chat_id: str,
        *,
        limit: int = 120,
        offset: int = 0,
    ) -> list[dict]:
        return await self._request(
            "GET",
            f"/rest/v1/{table}",
            params={
                "chat_id": f"eq.{chat_id}",
                "select": "*",
                "order": "created_at.asc",
                "limit": str(limit),
                "offset": str(offset),
            },
        )

    async def list_recent_messages_for_chats(
        self,
        *,
        table: str,
        chat_ids: list[str],
        limit: int = 120,
    ) -> list[dict]:
        if not chat_ids:
            return []

        return await self._request(
            "GET",
            f"/rest/v1/{table}",
            params={
                "chat_id": f"in.({','.join(chat_ids)})",
                "select": "id,chat_id,sender,content,metadata,created_at",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )

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
        return await self._refresh_patient_access_status(patient)

    async def _refresh_patient_access_statuses(self, patients: list[dict]) -> list[dict]:
        refreshed: list[dict] = []
        for patient in patients:
            refreshed.append(await self._refresh_patient_access_status(patient))
        return refreshed

    async def _refresh_patient_access_status(self, patient: dict) -> dict:
        if not self._patient_trial_is_expired(patient):
            return self._with_patient_access_metadata(patient)

        rows = await self._request(
            "PATCH",
            "/rest/v1/patients",
            params={"id": f"eq.{patient['id']}", "select": "*"},
            json={
                "access_status": "EXPIRED",
                "expired_at": datetime.now(UTC).isoformat(),
                "is_active": False,
            },
            prefer="return=representation",
        )
        updated = rows[0] if rows else {**patient, "access_status": "EXPIRED", "is_active": False}
        return self._with_patient_access_metadata(updated)

    def _patient_trial_is_expired(self, patient: dict) -> bool:
        if patient.get("access_status") != "TRIAL":
            return False
        trial_ends_at = self._parse_datetime(patient.get("trial_ends_at"))
        return trial_ends_at is None or trial_ends_at <= datetime.now(UTC)

    def _with_patient_access_metadata(self, patient: dict) -> dict:
        access = self._patient_access_payload(patient)
        return {
            **patient,
            "access_status": access["status"],
            "trial_days_remaining": access["trial_days_remaining"],
            "has_premium_access": access["has_premium_access"],
            "trial_expired_message": access["expired_message"],
        }

    def _patient_access_payload(self, patient: dict) -> dict:
        status_value = patient.get("access_status") or (
            "ACTIVE" if patient.get("is_active") is not False else "EXPIRED"
        )
        trial_ends_at = self._parse_datetime(patient.get("trial_ends_at"))
        if status_value == "TRIAL" and (
            trial_ends_at is None or trial_ends_at <= datetime.now(UTC)
        ):
            status_value = "EXPIRED"

        days_remaining = 0
        if status_value == "TRIAL" and trial_ends_at:
            seconds_remaining = max(0.0, (trial_ends_at - datetime.now(UTC)).total_seconds())
            days_remaining = max(1, int((seconds_remaining + 86399) // 86400))

        has_access = status_value in {"TRIAL", "ACTIVE"}
        return {
            "status": status_value,
            "trial_days_remaining": days_remaining,
            "has_premium_access": has_access,
            "can_use_ai_chat": has_access,
            "expired_message": PATIENT_TRIAL_EXPIRED_MESSAGE if status_value == "EXPIRED" else None,
        }

    def _patient_has_premium_access(self, patient: dict) -> bool:
        return self._patient_access_payload(patient)["has_premium_access"]

    def _assert_patient_ai_access(self, patient: dict) -> None:
        if self._patient_access_payload(patient)["can_use_ai_chat"]:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PATIENT_TRIAL_EXPIRED_MESSAGE,
        )

    async def _fetch_patient_rows(
        self,
        table: str,
        patient_ids: list[str],
        *,
        select: str,
        order: str,
        limit: int,
    ) -> list[dict]:
        if not patient_ids:
            return []

        return await self._request(
            "GET",
            f"/rest/v1/{table}",
            params={
                "patient_id": f"in.({','.join(patient_ids)})",
                "select": select,
                "order": order,
                "limit": str(limit),
            },
        )

    async def _attach_import_files(self, imports: list[dict]) -> list[dict]:
        if not imports:
            return []

        import_ids = [row["id"] for row in imports]
        files = await self._request(
            "GET",
            "/rest/v1/patient_import_files",
            params={
                "import_id": f"in.({','.join(import_ids)})",
                "select": "*",
                "order": "order_index.asc",
            },
        )
        by_import_id: dict[str, list[dict]] = {}
        for file_row in files:
            by_import_id.setdefault(file_row["import_id"], []).append(file_row)

        return [
            {**import_row, "files": by_import_id.get(import_row["id"], [])}
            for import_row in imports
        ]

    def _dedupe_patients(self, patients: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen_patient_ids: set[str] = set()
        seen_user_ids: set[str] = set()

        for patient in patients:
            patient_id = patient.get("id")
            user_id = patient.get("user_id")
            if patient_id in seen_patient_ids or user_id in seen_user_ids:
                continue

            if patient_id:
                seen_patient_ids.add(patient_id)
            if user_id:
                seen_user_ids.add(user_id)
            deduped.append(patient)

        return deduped

    def _compact_patient_lookup(self, patient: dict) -> dict:
        profile = patient.get("profile") or {}
        birth_date = patient.get("birth_date")
        return {
            "id": patient.get("id"),
            "full_name": profile.get("full_name"),
            "email": profile.get("email"),
            "gender": patient.get("gender"),
            "birth_date": birth_date,
            "age": calculate_age(birth_date),
            "objective": patient.get("objective"),
            "is_active": patient.get("is_active"),
            "access_status": patient.get("access_status"),
            "trial_days_remaining": patient.get("trial_days_remaining"),
            "has_premium_access": patient.get("has_premium_access"),
            "created_at": patient.get("created_at"),
            "updated_at": patient.get("updated_at"),
        }

    def _patient_name_match_score(
        self,
        query: str,
        normalized_name: str,
        normalized_nickname: str,
    ) -> int:
        fields = [field for field in (normalized_name, normalized_nickname) if field]
        if not fields:
            return 0

        query_tokens = query.split()
        best_score = 0
        for field in fields:
            field_tokens = field.split()
            if query == field:
                best_score = max(best_score, 100)
            if field_tokens and query == field_tokens[0]:
                best_score = max(best_score, 92)
            if field.startswith(query):
                best_score = max(best_score, 85)
            if query in field:
                best_score = max(best_score, 76)
            if query_tokens and all(token in field_tokens for token in query_tokens):
                best_score = max(best_score, 70)
            if query_tokens and all(token in field for token in query_tokens):
                best_score = max(best_score, 60)
        return best_score

    def _height_cm_from_metrics(self, metrics: list[dict]) -> float | None:
        metric = self._latest_metric_by_terms(metrics, ("altura", "height", "estatura"))
        if not metric:
            return None

        value = _metric_number(metric.get("value"))
        if value is None:
            return None

        unit = _normalize_search_text(metric.get("unit") or "")
        if unit in {"m", "metro", "metros"} or value < 3:
            return round(value * 100, 1)
        return round(value, 1)

    def _latest_metric_by_terms(
        self,
        metrics: list[dict],
        terms: tuple[str, ...],
    ) -> dict | None:
        normalized_terms = tuple(_normalize_search_text(term) for term in terms)
        for metric in metrics:
            name = _normalize_search_text(metric.get("name") or "")
            if any(term and term in name for term in normalized_terms):
                return metric
        return None

    def _latest_by_patient(
        self,
        rows: list[dict],
        date_field: str,
        *,
        prefer_earliest: bool = False,
    ) -> dict[str, dict]:
        selected: dict[str, dict] = {}

        for row in rows:
            patient_id = row.get("patient_id")
            if not patient_id:
                continue

            current = selected.get(patient_id)
            if not current:
                selected[patient_id] = row
                continue

            current_date = self._parse_datetime(current.get(date_field))
            row_date = self._parse_datetime(row.get(date_field))
            if not row_date:
                continue
            if not current_date:
                selected[patient_id] = row
                continue

            if prefer_earliest and row_date < current_date:
                selected[patient_id] = row
            elif not prefer_earliest and row_date > current_date:
                selected[patient_id] = row

        return selected

    def _dashboard_patient_summary(
        self,
        patient: dict,
        *,
        latest_metric_by_patient: dict[str, dict],
        next_appointment_by_patient: dict[str, dict],
        latest_condition_by_patient: dict[str, dict],
        active_diet_patient_ids: set[str],
        now: datetime,
    ) -> dict:
        patient_id = patient["id"]
        profile = patient.get("profile") or {}
        latest_metric = latest_metric_by_patient.get(patient_id)
        latest_condition = latest_condition_by_patient.get(patient_id)
        next_appointment = next_appointment_by_patient.get(patient_id)
        latest_update_at = self._latest_datetime_value(
            patient.get("updated_at"),
            patient.get("created_at"),
            latest_metric.get("recorded_at") if latest_metric else None,
            latest_metric.get("created_at") if latest_metric else None,
        )

        alert = self._patient_alert_label(
            patient,
            latest_metric=latest_metric,
            latest_condition=latest_condition,
            next_appointment=next_appointment,
            has_active_diet=patient_id in active_diet_patient_ids,
            now=now,
        )

        return {
            "id": patient_id,
            "name": profile.get("full_name") or "Paciente",
            "objective": patient.get("objective"),
            "status": patient.get("access_status") or (
                "ACTIVE" if patient.get("is_active") is not False else "EXPIRED"
            ),
            "is_active": self._patient_has_premium_access(patient),
            "trial_days_remaining": patient.get("trial_days_remaining", 0),
            "last_update_at": latest_update_at,
            "next_appointment_at": (
                next_appointment.get("scheduled_at") if next_appointment else None
            ),
            "alert": alert,
        }

    def _build_dashboard_alerts(
        self,
        *,
        active_patients: list[dict],
        active_diet_patient_ids: set[str],
        latest_metric_by_patient: dict[str, dict],
        latest_condition_by_patient: dict[str, dict],
        next_appointment_by_patient: dict[str, dict],
        now: datetime,
    ) -> list[dict]:
        alerts: list[dict] = []
        stale_cutoff = now - timedelta(days=14)
        upcoming_cutoff = now + timedelta(days=2)

        for patient in active_patients:
            patient_id = patient["id"]
            profile = patient.get("profile") or {}
            patient_name = profile.get("full_name") or "Paciente"
            latest_metric = latest_metric_by_patient.get(patient_id)
            latest_metric_at = self._parse_datetime(
                latest_metric.get("recorded_at") if latest_metric else None
            ) or self._parse_datetime(
                latest_metric.get("created_at") if latest_metric else None
            )

            if not latest_metric_at or latest_metric_at < stale_cutoff:
                alerts.append(
                    {
                        "id": f"{patient_id}:stale-evolution",
                        "type": "evolution",
                        "tone": "amber",
                        "title": "Evolucao sem atualizacao recente",
                        "description": (
                            "Revise medidas ou acompanhamento deste paciente."
                        ),
                        "patient_id": patient_id,
                        "patient_name": patient_name,
                        "date": latest_metric_at.isoformat() if latest_metric_at else None,
                    }
                )

            if patient_id not in active_diet_patient_ids:
                alerts.append(
                    {
                        "id": f"{patient_id}:missing-diet",
                        "type": "diet",
                        "tone": "red",
                        "title": "Plano alimentar pendente",
                        "description": "Paciente ativo sem plano alimentar ativo.",
                        "patient_id": patient_id,
                        "patient_name": patient_name,
                        "date": None,
                    }
                )

            condition = latest_condition_by_patient.get(patient_id)
            if condition:
                alerts.append(
                    {
                        "id": f"{patient_id}:condition:{condition['id']}",
                        "type": "condition",
                        "tone": "blue",
                        "title": condition.get("title") or "Condicao ativa",
                        "description": self._condition_description(condition),
                        "patient_id": patient_id,
                        "patient_name": patient_name,
                        "date": condition.get("created_at") or condition.get("started_at"),
                    }
                )

            appointment = next_appointment_by_patient.get(patient_id)
            appointment_at = self._parse_datetime(
                appointment.get("scheduled_at") if appointment else None
            )
            if appointment_at and appointment_at <= upcoming_cutoff:
                alerts.append(
                    {
                        "id": f"{patient_id}:appointment:{appointment['id']}",
                        "type": "appointment",
                        "tone": "green",
                        "title": "Consulta proxima",
                        "description": appointment.get("title") or "Acompanhamento agendado.",
                        "patient_id": patient_id,
                        "patient_name": patient_name,
                        "date": appointment.get("scheduled_at"),
                    }
                )

        tone_order = {"red": 0, "amber": 1, "blue": 2, "green": 3}
        return sorted(
            alerts,
            key=lambda alert: (
                tone_order.get(alert["tone"], 9),
                alert.get("date") or "",
                alert["patient_name"],
            ),
        )

    def _patient_alert_label(
        self,
        patient: dict,
        *,
        latest_metric: dict | None,
        latest_condition: dict | None,
        next_appointment: dict | None,
        has_active_diet: bool,
        now: datetime,
    ) -> str | None:
        latest_metric_at = self._parse_datetime(
            latest_metric.get("recorded_at") if latest_metric else None
        ) or self._parse_datetime(
            latest_metric.get("created_at") if latest_metric else None
        )
        if patient.get("is_active") is not False and not has_active_diet:
            return "Plano pendente"
        if patient.get("is_active") is not False and (
            not latest_metric_at or latest_metric_at < now - timedelta(days=14)
        ):
            return "Atualizar evolucao"
        if latest_condition:
            return "Condicao ativa"

        appointment_at = self._parse_datetime(
            next_appointment.get("scheduled_at") if next_appointment else None
        )
        if appointment_at and appointment_at <= now + timedelta(days=2):
            return "Consulta proxima"

        return None

    def _latest_datetime_value(self, *values: str | None) -> str | None:
        latest: datetime | None = None
        latest_value: str | None = None
        for value in values:
            parsed = self._parse_datetime(value)
            if parsed and (not latest or parsed > latest):
                latest = parsed
                latest_value = value
        return latest_value

    def _is_between(
        self,
        value: str | None,
        start: datetime,
        end: datetime,
    ) -> bool:
        parsed = self._parse_datetime(value)
        return bool(parsed and start <= parsed < end)

    def _dashboard_date(self, value: datetime) -> str:
        try:
            dashboard_timezone = ZoneInfo("America/Sao_Paulo")
        except ZoneInfoNotFoundError:
            dashboard_timezone = UTC

        return value.astimezone(dashboard_timezone).date().isoformat()

    def _is_appointment_between(
        self,
        appointment: dict,
        start: datetime,
        end: datetime,
    ) -> bool:
        parsed = self._parse_datetime(self._appointment_datetime_value(appointment))
        return bool(parsed and start <= parsed < end)

    def _appointment_datetime_value(self, appointment: dict) -> str | None:
        date_value = appointment.get("date")
        start_time = appointment.get("start_time")
        if not date_value or not start_time:
            return None

        return f"{date_value}T{str(start_time)[:8]}-03:00"

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _condition_description(self, condition: dict) -> str:
        condition_type = condition.get("condition_type") or "condicao"
        severity = condition.get("severity")
        if severity:
            return f"{condition_type} registrada com severidade {severity}."
        return f"{condition_type} registrada no acompanhamento."

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

    async def _diet_meal_items_by_meal(
        self,
        meals_by_diet: dict[str, list[dict]],
    ) -> dict[str, list[dict]]:
        meal_ids = [
            meal["id"]
            for meals in meals_by_diet.values()
            for meal in meals
            if meal.get("id")
        ]
        return await self._rows_by_parent("diet_meal_items", "meal_id", meal_ids)

    def _attach_items_to_meals(
        self,
        meals: list[dict],
        items_by_meal: dict[str, list[dict]],
    ) -> list[dict]:
        for meal in meals:
            meal["items"] = items_by_meal.get(meal["id"], [])
        return meals

    async def _get_recent_messages(self, chats: list[dict], table: str) -> list[dict]:
        if not chats:
            return []

        chat_ids = [chat["id"] for chat in chats[:5]]
        return await self._request(
            "GET",
            f"/rest/v1/{table}",
            params={
                "chat_id": f"in.({','.join(chat_ids)})",
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


def _normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).split())


def _postgrest_search_term(value: str) -> str:
    return " ".join(re.sub(r"[%*',().]", " ", str(value or "")).split())


def calculate_age(birth_date: Any) -> int | None:
    if birth_date is None:
        return None

    text = str(birth_date).strip()
    if not text:
        return None

    try:
        date_value = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None

    try:
        today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    except Exception:
        today = datetime.now(UTC).date()

    if date_value > today:
        return None

    age = today.year - date_value.year
    if (today.month, today.day) < (date_value.month, date_value.day):
        age -= 1
    return age


def _metric_number(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip().replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None
