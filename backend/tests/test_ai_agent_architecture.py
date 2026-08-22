import json
import unittest

from fastapi import HTTPException

from backend.app.services.ai_agent_service import AiAgentService
from backend.tests.test_ai_agent_permissions import (
    FakeAi,
    FakeWorkspace,
    nutritionist_context,
)


class SequencedAi:
    def __init__(self, calls):
        self.calls = list(calls)
        self.received = []

    async def complete_with_tools(self, **kwargs):
        self.received.append(kwargs)
        if not self.calls:
            return {}
        name, arguments = self.calls.pop(0)
        return {
            "content": None,
            "tool_calls": [{
                "id": f"call-{len(self.received)}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }],
        }


class CapturingWorkspace(FakeWorkspace):
    async def create_ai_diet_plan(self, **kwargs):
        self.diet_payload = kwargs
        return await super().create_ai_diet_plan(**kwargs)


class FailingFirstWorkspace(FakeWorkspace):
    async def create_health_condition_record(self, **kwargs):
        raise HTTPException(status_code=502, detail="Erro do Supabase: database unavailable")


class InvalidArgumentsAi:
    def __init__(self):
        self.calls = 0

    async def complete_with_tools(self, **kwargs):
        self.calls += 1
        if self.calls > 1:
            return {}
        return {"tool_calls": [{"id": "bad-call", "function": {"name": "register_progress", "arguments": "{invalid"}}]}


class AgentArchitectureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat = {"id": "chat-1"}
        self.message = {"id": "message-1"}
        self.context = nutritionist_context()

    async def run_agent(self, workspace, ai, content="Execute o pedido"):
        return await AiAgentService(workspace, ai).run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message=content,
            user_message_record=self.message,
        )

    async def execute(self, workspace, tool, arguments):
        return await AiAgentService(workspace, FakeAi())._execute_tool(
            actor=workspace.profile,
            arguments=arguments,
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            intent=tool,
            message=self.message,
            tool_name=tool,
        )

    async def test_multi_step_request_executes_training_and_diet_once(self):
        workspace = FakeWorkspace()
        ai = SequencedAi([
            ("create_training_plan", {"title": "Treino A", "days": [{"name": "A", "exercises": [{"exercise_name": "Caminhada"}]}]}),
            ("create_diet_plan", {"title": "Dieta A", "calories": 2000, "meals": [{"meal_name": "Cafe", "foods": [{"name": "Banana", "quantity": "1 unidade"}]}]}),
        ])
        actions = await self.run_agent(workspace, ai, "Crie um treino e uma dieta")
        self.assertEqual([item["tool"] for item in actions], ["create_training_plan", "create_diet_plan"])
        self.assertTrue(all(item["success"] for item in actions))
        self.assertEqual(workspace.mutations.count("create_training_plan"), 1)
        self.assertEqual(workspace.mutations.count("create_diet"), 1)
        self.assertTrue(any(message.get("role") == "tool" for message in ai.received[1]["messages"]))

    async def test_partial_failure_is_typed_and_next_operation_continues(self):
        workspace = FailingFirstWorkspace()
        ai = SequencedAi([
            ("register_injury", {"local": "Joelho", "description": "Dor", "severity": "Leve"}),
            ("register_weight_change", {"current_weight_kg": 82}),
        ])
        actions = await self.run_agent(workspace, ai, "Registre a lesão e o peso do paciente")
        self.assertFalse(actions[0]["success"])
        self.assertEqual(actions[0]["error_code"], "database_error")
        self.assertTrue(actions[1]["success"])
        self.assertEqual(actions[1]["operation"], "register_weight_change")

    async def test_diet_integer_columns_are_normalized_before_rpc(self):
        workspace = CapturingWorkspace()
        action = await self.execute(workspace, "create_diet_plan", {
            "title": "Plano", "calories": 2500.0, "water_goal_ml": 2300.4,
            "meals": [{"meal_name": "Cafe", "foods": [{"name": "Ovo", "quantity": "2 unidades"}]}],
        })
        self.assertTrue(action["success"])
        self.assertIsInstance(workspace.diet_payload["calories"], int)
        self.assertIsInstance(workspace.diet_payload["water_goal_ml"], int)

    async def test_high_impact_replacement_requires_and_consumes_confirmation(self):
        workspace = FakeWorkspace()
        service = AiAgentService(workspace, FakeAi())
        payload = {"title": "Novo", "days": [{"name": "A", "exercises": [{"exercise_name": "Remada"}]}]}
        pending = await service._execute_tool(
            actor=workspace.profile, arguments=payload, chat=self.chat,
            chat_scope="nutritionist", context=self.context,
            intent="replace_training_plan", message=self.message,
            tool_name="replace_training_plan",
        )
        self.assertEqual(pending["status"], "pending_confirmation")
        self.assertNotIn("create_training_plan", workspace.mutations)
        actions = await service.run(
            chat=self.chat, chat_scope="nutritionist", context=self.context,
            history=[], reasoning_level="medium", token="token",
            user_message="Sim, confirmo", user_message_record=self.message,
        )
        self.assertTrue(actions[0]["success"])
        self.assertEqual(actions[0]["tool"], "replace_training_plan")

    async def test_diet_meal_crud_and_confirmation(self):
        workspace = FakeWorkspace()
        updated = await self.execute(workspace, "update_diet_meal", {"meal_id": "meal-1", "notes": "Sem lactose"})
        self.assertTrue(updated["success"])
        pending = await self.execute(workspace, "delete_diet_meal", {"meal_id": "meal-1"})
        self.assertEqual(pending["status"], "pending_confirmation")
        deleted = await self.execute(workspace, "delete_diet_meal", {"meal_id": "meal-1", "_confirmed": True})
        self.assertTrue(deleted["success"])

    async def test_workout_and_exercise_operations(self):
        workspace = FakeWorkspace()
        self.assertTrue((await self.execute(workspace, "update_workout", {"workout_id": "workout-1", "title": "Novo"}))["success"])
        self.assertTrue((await self.execute(workspace, "add_workout_exercise", {"workout_id": "workout-1", "exercise_name": "Remada"}))["success"])
        self.assertTrue((await self.execute(workspace, "update_workout_exercise", {"exercise_id": "exercise-1", "reps": "12"}))["success"])
        self.assertTrue((await self.execute(workspace, "remove_workout_exercise", {"exercise_id": "exercise-1", "_confirmed": True}))["success"])
        self.assertTrue((await self.execute(workspace, "delete_workout", {"workout_id": "workout-1", "_confirmed": True}))["success"])

    async def test_health_update_and_delete(self):
        workspace = FakeWorkspace()
        self.assertTrue((await self.execute(workspace, "update_health_condition", {"condition_id": "condition-1", "severity": "Moderada"}))["success"])
        self.assertTrue((await self.execute(workspace, "delete_health_condition", {"condition_id": "condition-1", "_confirmed": True}))["success"])

    async def test_unknown_tool_is_audited_without_execution(self):
        workspace = FakeWorkspace()
        action = await self.execute(workspace, "drop_database", {})
        self.assertFalse(action["success"])
        self.assertEqual(action["error_code"], "tool_not_found")
        self.assertEqual(workspace.mutations, [])

    async def test_invalid_model_json_is_typed_and_never_executed(self):
        workspace = FakeWorkspace()
        actions = await self.run_agent(workspace, InvalidArgumentsAi(), "Registre o progresso do paciente")
        self.assertEqual(actions[0]["error_code"], "invalid_tool_arguments")
        self.assertFalse(actions[0]["success"])
        self.assertEqual(workspace.mutations, [])

    async def test_general_chat_resolves_owned_patient_before_write(self):
        workspace = FakeWorkspace()
        ai = SequencedAi([
            ("search_patient_by_name", {"query": "Joao"}),
            ("update_patient_profile", {"patient_id": "20000000-0000-4000-8000-000000000001", "objective": "Emagrecimento"}),
        ])
        self.context = {"nutritionist": self.context["nutritionist"]}
        actions = await self.run_agent(workspace, ai, "Atualize o objetivo de Joao")
        self.assertEqual([item["tool"] for item in actions], ["search_patient_by_name", "update_patient_profile"])
        self.assertTrue(all(item["success"] for item in actions))


if __name__ == "__main__":
    unittest.main()
