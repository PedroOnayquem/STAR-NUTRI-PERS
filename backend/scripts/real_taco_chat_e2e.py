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
                content="Quantas calorias tem 150g de arroz integral segundo a tebela taco?",
            )
            ambiguous = [
                action
                for action in ambiguous_actions
                if action.get("operation") == "resolve_taco_nutrition"
            ]
            if not ambiguous or (ambiguous[-1].get("result") or {}).get(
                "resolution"
            ) != "ambiguous":
                raise E2EFailure(f"integral rice was not classified ambiguous: {ambiguous_actions}")
            if "?" not in ambiguous_answer or "encontrado(s)" in ambiguous_answer:
                raise E2EFailure(
                    f"generic rice response did not ask useful clarification: {ambiguous_answer}"
                )
            states = _rows(
                client,
                "ai_conversation_state",
                {
                    "conversation_id": f"eq.{session_id}",
                    "user_id": f"eq.{state['nutritionist_user_id']}",
                },
            )
            slots = (states[0].get("task_slots") or {}) if len(states) == 1 else {}
            if len(states) != 1 or states[0].get("task_status") != "waiting_user" or slots.get("quantity_g") != 150:
                raise E2EFailure(f"150g active-task slot was not persisted: {states}")
            report["checks"].append("ambiguity_persists_active_task_and_150g_slot")

            other_session = _require(
                client.post(
                    f"{API_BASE}/chat/nutritionist/sessions",
                    headers=_bearer(token),
                    json={"chat_scope": "general", "title": f"E2E ISOLATION {suffix}"},
                ),
                {200},
                "create isolated nutritionist chat",
            )
            other_actions, _ = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=str(other_session["id"]),
                content="Agora procure o paciente Pedro.",
            )
            if not any(action.get("operation") == "search_patient_by_name" for action in other_actions):
                raise E2EFailure(f"explicit patient task was not routed: {other_actions}")
            if any(action.get("operation") in {"resolve_taco_nutrition", "search_taco_foods"} for action in other_actions):
                raise E2EFailure(f"patient conversation received TACO tools: {other_actions}")
            report["checks"].append("second_conversation_isolated_and_explicit_switch_routed")

            resolved_actions, resolved_answer = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=session_id,
                content="cozido",
            )
            resolved = [
                action
                for action in resolved_actions
                if action.get("operation") == "resolve_taco_nutrition"
                and action.get("success") is True
            ]
            if not resolved:
                raise E2EFailure(f"clarification did not complete TACO lookup: {resolved_actions}")
            if "186" not in resolved_answer or "taco" not in resolved_answer.lower():
                raise E2EFailure(
                    f"resolved response is not grounded in TACO 186 kcal: {resolved_answer}"
                )
            resolved_result = resolved[-1].get("result") or {}
            if (resolved_result.get("nutrients") or {}).get("energy_kcal") != 186:
                raise E2EFailure(f"deterministic 150g calculation is wrong: {resolved_result}")
            if (resolved[-1].get("arguments") or {}).get("quantity_g") != 150:
                raise E2EFailure(f"resolved tool lost the 150g slot: {resolved[-1]}")
            if any(action.get("operation") == "search_patient_by_name" for action in resolved_actions):
                raise E2EFailure(f"TACO continuation called a patient tool: {resolved_actions}")
            completed_state = _rows(
                client,
                "ai_conversation_state",
                {
                    "conversation_id": f"eq.{session_id}",
                    "user_id": f"eq.{state['nutritionist_user_id']}",
                },
            )
            if not completed_state or completed_state[0].get("task_status") != "completed":
                raise E2EFailure(f"task was not completed safely: {completed_state}")
            report["checks"].append("cozido_reuses_150g_and_returns_186_kcal")

            followup_120_actions, followup_120_answer = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=session_id,
                content="e se for 120g tem quantas calorias?",
            )
            followup_120 = [
                action
                for action in followup_120_actions
                if action.get("operation") == "resolve_taco_nutrition"
                and action.get("success") is True
            ]
            if not followup_120:
                raise E2EFailure(f"120g follow-up did not reuse the TACO task: {followup_120_actions}")
            if (followup_120[-1].get("arguments") or {}).get("quantity_g") != 120:
                raise E2EFailure(f"120g follow-up lost the new quantity: {followup_120[-1]}")
            if (followup_120[-1].get("result") or {}).get("food", {}).get("id") != resolved_result.get("food", {}).get("id"):
                raise E2EFailure(f"120g follow-up changed the food: {followup_120[-1]}")
            if (followup_120[-1].get("result") or {}).get("nutrients", {}).get("energy_kcal") != 148.8:
                raise E2EFailure(f"120g follow-up calculation is wrong: {followup_120[-1]}")
            if not any(value in followup_120_answer for value in ("149", "148,8", "148.8")):
                raise E2EFailure(f"120g answer did not expose the grounded result: {followup_120_answer}")

            followup_200_actions, followup_200_answer = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=session_id,
                content="e 200g?",
            )
            followup_200 = [
                action
                for action in followup_200_actions
                if action.get("operation") == "resolve_taco_nutrition"
                and action.get("success") is True
            ]
            if not followup_200 or (followup_200[-1].get("result") or {}).get("nutrients", {}).get("energy_kcal") != 248:
                raise E2EFailure(f"200g follow-up calculation is wrong: {followup_200_actions}")
            if "248" not in followup_200_answer:
                raise E2EFailure(f"200g answer did not expose the grounded result: {followup_200_answer}")

            comparison_actions, comparison_answer = _send(
                client,
                endpoint="chat/nutritionist/send",
                token=token,
                session_id=session_id,
                content="qual tem mais calorias?",
            )
            if any(action.get("operation") == "search_patient_by_name" for action in comparison_actions):
                raise E2EFailure(f"comparison follow-up called a patient tool: {comparison_actions}")
            if "200" not in comparison_answer or "mais" not in comparison_answer.lower():
                raise E2EFailure(f"comparison did not relate 120g and 200g: {comparison_answer}")
            contextual_state = _rows(
                client,
                "ai_conversation_state",
                {
                    "conversation_id": f"eq.{session_id}",
                    "user_id": f"eq.{state['nutritionist_user_id']}",
                },
            )
            evidence_items = ((contextual_state[0].get("task_evidence") or {}).get("items") or []) if contextual_state else []
            if len(evidence_items) < 4:
                raise E2EFailure(f"authoritative follow-up evidence was not retained: {contextual_state}")
            report["checks"].append("completed_task_answers_120g_200g_and_comparison")

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
            if not traces or any(
                not isinstance(trace.get("duration_ms"), int)
                or trace.get("duration_ms") < 0
                for trace in traces
            ):
                raise E2EFailure(f"run traces do not expose valid durations: {traces}")
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
