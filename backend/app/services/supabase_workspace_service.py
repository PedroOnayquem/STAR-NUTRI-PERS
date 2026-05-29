from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import HTTPException, status

from ..core.config import settings
from ..schemas.workspace import UpdateMyPatientProfileRequest, UpdatePatientRequest


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
                "select": (
                    "id,user_id,nutritionist_id,birth_date,gender,objective,notes,"
                    "is_active,created_at,updated_at"
                ),
                "order": "updated_at.desc.nullslast,created_at.desc",
            },
        )
        patients = self._dedupe_patients(await self._attach_profiles(raw_patients))
        active_patients = [
            patient for patient in patients if patient.get("is_active") is not False
        ]
        active_patient_ids = [patient["id"] for patient in active_patients]
        active_patient_id_set = set(active_patient_ids)

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
            "stats": {
                "active_patients": len(active_patients),
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
        patient_profile = profile
        patient_id = patient["id"]

        diets, workouts, variable_metrics = await asyncio.gather(
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
                    "select": "id,patient_id,name,value,unit,recorded_at,created_at",
                    "order": "recorded_at.desc,created_at.desc",
                    "limit": "20",
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
        for diet in diets:
            diet["meals"] = meals.get(diet["id"], [])
        for workout in workouts:
            workout["exercises"] = exercises.get(workout["id"], [])
        imports = await self._attach_import_files(imports)

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
            "imports": [],
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

        for diet in diets:
            diet["meals"] = meals.get(diet["id"], [])
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
        if chat_scope == "patient":
            patient_payload["notes"] = None

        return {
            "patient": patient_payload,
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
            UpdatePatientRequest(is_active=False),
        )
        return {"id": updated["id"], "is_active": updated["is_active"]}

    async def insert_ai_action_log(self, payload: dict) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/ai_action_logs",
            json=payload,
            prefer="return=representation",
        )
        return rows[0]

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
        return rows[0]

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
        return rows[0]

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
        diet["meals"] = meals
        return diet

    async def create_diet_meal_record(
        self,
        *,
        diet_id: str,
        meal_name: str,
        foods: list[dict],
        notes: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/diet_meals",
            json={
                "diet_id": diet_id,
                "meal_name": meal_name,
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
        return rows[0]

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
        return rows[0]

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
        return profile, patient

    async def list_nutritionist_chats_for_patient(
        self,
        nutritionist_id: str,
        patient_id: str | None,
    ) -> list[dict]:
        params = {
            "nutritionist_id": f"eq.{nutritionist_id}",
            "select": "*",
            "order": "updated_at.desc,created_at.desc",
        }
        params["patient_id"] = f"eq.{patient_id}" if patient_id else "is.null"

        return await self._request(
            "GET",
            "/rest/v1/nutritionist_chats",
            params=params,
        )

    async def list_patient_chats_for_patient(self, patient_id: str) -> list[dict]:
        return await self._request(
            "GET",
            "/rest/v1/patient_chats",
            params={
                "patient_id": f"eq.{patient_id}",
                "select": "*",
                "order": "updated_at.desc,created_at.desc",
            },
        )

    async def list_authorized_nutritionist_chats(
        self,
        token: str,
        patient_id: str | None = None,
    ) -> list[dict]:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas acessam chats profissionais.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        if patient_id:
            await self.resolve_nutritionist_patient(token, patient_id)

        return await self.list_nutritionist_chats_for_patient(
            nutritionist["id"],
            patient_id,
        )

    async def list_authorized_patient_chats(self, token: str) -> list[dict]:
        _, patient = await self.resolve_patient_owner(token)
        return await self.list_patient_chats_for_patient(patient["id"])

    async def create_nutritionist_chat(
        self,
        nutritionist_id: str,
        patient_id: str | None,
        title: str | None = None,
    ) -> dict:
        rows = await self._request(
            "POST",
            "/rest/v1/nutritionist_chats",
            json={
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
        return rows[0]

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
    ) -> dict:
        profile = await self.get_authenticated_profile(token)
        if profile["role"] != "nutritionist":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas nutricionistas criam chats profissionais.",
            )

        nutritionist = await self.get_nutritionist_by_user_id(profile["id"])
        resolved_patient_id: str | None = None
        if patient_id:
            _, _, patient = await self.resolve_nutritionist_patient(
                token,
                patient_id,
            )
            resolved_patient_id = patient["id"]

        return await self.create_nutritionist_chat(
            nutritionist["id"],
            resolved_patient_id,
            title,
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
        nutritionist_id: str,
        patient_id: str | None = None,
    ) -> dict:
        params = {
            "id": f"eq.{chat_id}",
            "nutritionist_id": f"eq.{nutritionist_id}",
            "select": "*",
            "limit": "1",
        }
        params["patient_id"] = f"eq.{patient_id}" if patient_id else "is.null"

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
    ) -> dict:
        if chat_id:
            return await self.get_nutritionist_chat(
                chat_id,
                nutritionist_id=nutritionist_id,
                patient_id=patient_id,
            )
        return await self.create_nutritionist_chat(nutritionist_id, patient_id)

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
            "status": "Ativo" if patient.get("is_active") is not False else "Inativo",
            "is_active": patient.get("is_active") is not False,
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
