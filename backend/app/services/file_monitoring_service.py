from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status

from .supabase_workspace_service import SupabaseWorkspaceService


class FileMonitoringService:
    def __init__(self) -> None:
        self.workspace = SupabaseWorkspaceService()

    async def get_dashboard(self, token: str, *, days: int = 30, limit: int = 60) -> dict:
        if days not in {7, 30, 90}:
            raise HTTPException(status_code=400, detail="Periodo deve ser 7, 30 ou 90 dias.")
        limit = max(1, min(limit, 100))
        profile = await self.workspace.get_authenticated_profile(token)
        nutritionist_id: str | None = None
        if profile["role"] == "nutritionist":
            nutritionist = await self.workspace.get_nutritionist_by_user_id(profile["id"])
            nutritionist_id = nutritionist["id"]
        elif profile["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Monitoramento disponivel para nutricionistas e administradores.",
            )

        since = datetime.now(UTC) - timedelta(days=days)
        filters = {
            "select": (
                "id,patient_id,nutritionist_id,uploaded_by_user_id,status,created_at,updated_at,"
                "file_type,mime_type,original_file_name,file_size_bytes,error_message,error_code,"
                "processing_started_at,processed_at,processing_duration_ms,processing_stage,file_count"
            ),
            "created_at": f"gte.{since.isoformat()}",
            "order": "created_at.desc,id.desc",
        }
        if nutritionist_id:
            filters["nutritionist_id"] = f"eq.{nutritionist_id}"
        imports = await self._fetch_all("/rest/v1/patient_imports", filters)

        event_filters = {
            "select": "id,import_id,event_type,duration_ms,error_code,error_message,created_at,metadata",
            "created_at": f"gte.{since.isoformat()}",
            "order": "created_at.desc,id.desc",
        }
        if nutritionist_id:
            event_filters["nutritionist_id"] = f"eq.{nutritionist_id}"
        events = await self._fetch_all("/rest/v1/patient_import_events", event_filters)

        recent_imports = imports[:limit]
        import_ids = [item["id"] for item in recent_imports]
        files: list[dict] = []
        if import_ids:
            files = await self.workspace._request(
                "GET", "/rest/v1/patient_import_files",
                params={
                    "import_id": f"in.({','.join(import_ids)})",
                    "select": "id,import_id,file_type,mime_type,original_file_name,file_size_bytes,status,extraction_mode,processing_duration_ms,error_code,error_message,created_at",
                    "order": "order_index.asc",
                },
            ) or []

        patient_ids = sorted({item["patient_id"] for item in recent_imports if item.get("patient_id")})
        patients_by_id: dict[str, dict] = {}
        if patient_ids:
            patients = await self.workspace._request(
                "GET", "/rest/v1/patients",
                params={"id": f"in.({','.join(patient_ids)})", "select": "id,user_id"},
            ) or []
            user_ids = [item["user_id"] for item in patients if item.get("user_id")]
            profiles = await self.workspace._request(
                "GET", "/rest/v1/profiles",
                params={"id": f"in.({','.join(user_ids)})", "select": "id,full_name"},
            ) if user_ids else []
            names = {item["id"]: item.get("full_name") for item in (profiles or [])}
            patients_by_id = {item["id"]: {"id": item["id"], "name": names.get(item.get("user_id"))} for item in patients}

        files_by_import: dict[str, list[dict]] = defaultdict(list)
        for item in files:
            files_by_import[item["import_id"]].append(item)
        ai_uses = Counter(item["import_id"] for item in events if item["event_type"] == "ai_context_used")
        rows = [
            {**item, "patient": patients_by_id.get(item.get("patient_id")),
             "files": files_by_import.get(item["id"], []), "ai_usage_count": ai_uses[item["id"]]}
            for item in imports
        ]
        response = self._build_response(rows, events, days, profile["role"])
        response["imports"] = rows[:limit]
        return response

    async def _fetch_all(self, path: str, params: dict[str, str]) -> list[dict]:
        rows: list[dict] = []
        page_size = 500
        while True:
            page = await self.workspace._request(
                "GET", path,
                params={**params, "limit": str(page_size), "offset": str(len(rows))},
            ) or []
            rows.extend(page)
            if len(page) < page_size:
                return rows

    def _build_response(self, imports: list[dict], events: list[dict], days: int, role: str) -> dict:
        durations = [int(item["processing_duration_ms"]) for item in imports if item.get("processing_duration_ms") is not None]
        failed = [item for item in imports if item.get("status") == "failed"]
        status_counts = Counter(item.get("status") or "unknown" for item in imports)
        format_counts = Counter(item.get("file_type") or "unknown" for item in imports)
        daily: dict[str, dict[str, Any]] = {}
        today = datetime.now(UTC).date()
        for offset in range(days - 1, -1, -1):
            key = (today - timedelta(days=offset)).isoformat()
            daily[key] = {"date": key, "files": 0, "failed": 0, "ai_uses": 0}
        for item in imports:
            key = self._date_key(item.get("created_at"))
            if key in daily:
                daily[key]["files"] += int(item.get("file_count") or 1)
                daily[key]["failed"] += int(item.get("status") == "failed")
        for event in events:
            if event.get("event_type") == "ai_context_used":
                key = self._date_key(event.get("created_at"))
                if key in daily:
                    daily[key]["ai_uses"] += 1
        errors = Counter((item.get("error_code") or "unclassified", item.get("error_message") or "Erro sem detalhe") for item in failed)
        return {
            "period_days": days,
            "scope": role,
            "summary": {
                "imports": len(imports),
                "files": sum(int(item.get("file_count") or 1) for item in imports),
                "processed": sum(status_counts[key] for key in ("processed", "linked")),
                "failed": len(failed),
                "average_processing_ms": round(sum(durations) / len(durations)) if durations else None,
                "measured_processing_count": len(durations),
                "ai_usage_count": sum(1 for item in events if item.get("event_type") == "ai_context_used"),
                "file_access_count": sum(1 for item in events if item.get("event_type") == "signed_url_generated"),
            },
            "daily": list(daily.values()),
            "status_breakdown": [{"status": key, "count": value} for key, value in status_counts.items()],
            "format_breakdown": [{"format": key, "count": value} for key, value in format_counts.items()],
            "recurring_errors": [{"code": key[0], "message": key[1], "count": value} for key, value in errors.most_common(8)],
            "slow_imports": sorted(
                [item for item in imports if item.get("processing_duration_ms") is not None],
                key=lambda item: int(item["processing_duration_ms"]), reverse=True,
            )[:8],
            "imports": imports,
        }

    @staticmethod
    def _date_key(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return None

    async def record_ai_context_usage(
        self, *, token: str, context: dict, chat_scope: str, chat_id: str,
        message_id: str, metric_limit: int,
    ) -> None:
        metrics = (context.get("variable_metrics") or [])[:metric_limit]
        counts = Counter(item.get("source_import_id") for item in metrics if item.get("source_import_id"))
        if not counts:
            return
        profile = await self.workspace.get_authenticated_profile(token)
        import_ids = list(counts)
        imports = await self.workspace._request(
            "GET", "/rest/v1/patient_imports",
            params={"id": f"in.({','.join(import_ids)})", "select": "id,patient_id,nutritionist_id"},
        ) or []
        rows = [{
            "import_id": item["id"], "actor_user_id": profile["id"],
            "patient_id": item.get("patient_id"), "nutritionist_id": item["nutritionist_id"],
            "event_type": "ai_context_used", "stage": "ai_context",
            "chat_scope": chat_scope, "chat_id": chat_id, "message_id": message_id,
            "metadata": {"derived_metric_count": counts[item["id"]]},
        } for item in imports]
        if rows:
            await self.workspace._request(
                "POST", "/rest/v1/patient_import_events", json=rows, prefer="return=minimal"
            )
