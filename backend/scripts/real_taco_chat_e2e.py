"""Opt-in E2E for the real HTTP chat pipeline and TACO grounding.

Creates one isolated nutritionist, tests ambiguity followed by contextual
clarification through FastAPI/SSE, verifies audit traces, and removes all data.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from typing import Any
from uuid import uuid4

import httpx

from backend.scripts.real_agent_e2e import (
    API_BASE,
    E2EFailure,
    _bearer,
    _cleanup,
    _create_auth_user,
    _insert,
    _login,
    _require,
    _rows,
    _send,
)


RUN_PERMISSION = "STAR_NUTRI_REAL_TACO_E2E"


def run() -> dict[str, Any]:
    if os.getenv(RUN_PERMISSION) != "1":
        raise E2EFailure(f"set {RUN_PERMISSION}=1 to allow temporary remote data")

    suffix = uuid4().hex[:12]
    email = f"star-nutri-taco-e2e-{suffix}@example.com"
    password = f"Sn!{secrets.token_urlsafe(18)}9a"
    name = f"Nutricionista TACO E2E {suffix}"
    state: dict[str, str] = {}
    report: dict[str, Any] = {"marker": suffix, "checks": []}

    with httpx.Client(timeout=60) as client:
        try:
            state["nutritionist_user_id"] = _create_auth_user(
                client,
                email,
                password,
                name,
            )
            _insert(
                client,
                "profiles",
                {
                    "id": state["nutritionist_user_id"],
                    "full_name": name,
                    "email": email,
                    "role": "nutritionist",
                    "is_active": True,
                },
            )
            nutritionist = _insert(
                client,
                "nutritionists",
                {
                    "user_id": state["nutritionist_user_id"],
                    "specialty": "Nutrição clínica",
                    "bio": "Conta temporária do E2E TACO",
                },
            )
            state["nutritionist_id"] = str(nutritionist["id"])
            token = _login(client, email, password)
            session = _require(
                client.post(
                    f"{API_BASE}/chat/nutritionist/sessions",
                    headers=_bearer(token),
                    json={
                        "chat_scope": "general",
                        "title": f"E2E TACO {suffix}",
                    },
                ),
                {200},
                "create general nutritionist chat",
            )
            session_id = str(session["id"])

            ambiguous_actions, ambiguous_answer = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=session_id,
                content="Quantas calorias tem 150g de arroz segundo a tabela TACO?",
            )
            ambiguous = [
                action
                for action in ambiguous_actions
                if action.get("operation") == "resolve_taco_nutrition"
            ]
            if not ambiguous or (ambiguous[-1].get("result") or {}).get(
                "resolution"
            ) != "ambiguous":
                raise E2EFailure(f"generic rice was not classified ambiguous: {ambiguous_actions}")
            if "?" not in ambiguous_answer or "encontrado(s)" in ambiguous_answer:
                raise E2EFailure(
                    f"generic rice response did not ask useful clarification: {ambiguous_answer}"
                )
            report["checks"].append("generic_query_requests_clarification")

            resolved_actions, resolved_answer = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=session_id,
                content="Considere arroz tipo 1 cozido.",
            )
            resolved = [
                action
                for action in resolved_actions
                if action.get("operation") == "resolve_taco_nutrition"
                and action.get("success") is True
            ]
            if not resolved:
                raise E2EFailure(f"clarification did not complete TACO lookup: {resolved_actions}")
            if "192" not in resolved_answer or "taco" not in resolved_answer.lower():
                raise E2EFailure(
                    f"resolved response is not grounded in TACO 192 kcal: {resolved_answer}"
                )
            report["checks"].append("contextual_clarification_returns_192_kcal")

            traces = _rows(
                client,
                "ai_action_logs",
                {
                    "actor_user_id": f"eq.{state['nutritionist_user_id']}",
                    "tool_name": "eq.agent_run",
                    "order": "created_at.asc",
                },
            )
            decisions = [
                (trace.get("result") or {}).get("final_decision") for trace in traces
            ]
            if "clarification_required" not in decisions or "answered" not in decisions:
                raise E2EFailure(f"run traces do not expose both decisions: {decisions}")
            if any(
                "Quantas calorias" in json.dumps(trace.get("input"), ensure_ascii=False)
                for trace in traces
            ):
                raise E2EFailure("run trace copied original message instead of linking it")
            report["checks"].append("safe_observability_trace")
        finally:
            cleanup_failures = _cleanup(client, state)
            report["cleanup"] = "ok" if not cleanup_failures else cleanup_failures

    if report.get("cleanup") != "ok":
        raise E2EFailure(f"cleanup incomplete: {report['cleanup']}")
    return report


if __name__ == "__main__":
    try:
        print(json.dumps(run(), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"REAL TACO E2E FAILED: {exc}", file=sys.stderr)
        raise
