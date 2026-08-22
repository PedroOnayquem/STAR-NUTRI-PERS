import unittest

from backend.app.services.supabase_workspace_service import SupabaseWorkspaceService


class WorkspacePersistenceConfirmationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = object.__new__(SupabaseWorkspaceService)
        self.confirmed_tables = []

        async def request(method, path, **kwargs):
            return [{"id": "row-1"}]

        async def get_row(table, row_id):
            self.confirmed_tables.append(table)
            return {"id": row_id, "confirmed_table": table}

        self.service._request = request
        self.service._get_row_by_id = get_row

    async def test_each_write_confirms_the_inserted_table(self):
        await self.service.upsert_conversation_memory({"conversation_id": "chat-1"})
        await self.service.create_health_condition_record(
            patient_id="patient-1", condition_type="injury", title="Joelho", description="Dor"
        )
        await self.service.create_training_plan_record(
            nutritionist_id="nutritionist-1", patient_id="patient-1", title="Treino",
            objective=None, restrictions=[], observations=None,
        )
        await self.service.create_diet_meal_item(
            meal_id="meal-1", taco_food_id=None, custom_food_name="Arroz",
            quantity_g=100, nutrients={},
        )
        await self.service.create_patient_appointment(
            nutritionist_id="nutritionist-1", patient_id="patient-1", title="Retorno",
            type="retorno", date="2026-08-20", start_time="10:00:00",
        )
        await self.service.create_nutritionist_chat(
            "nutritionist-1", "patient-1", chat_scope="patient"
        )
        self.assertEqual(
            self.confirmed_tables,
            [
                "ai_conversation_memories",
                "patient_health_conditions",
                "training_plans",
                "diet_meal_items",
                "patient_appointments",
                "nutritionist_chats",
            ],
        )

    async def test_get_row_returns_confirmed_row_without_recursion(self):
        service = object.__new__(SupabaseWorkspaceService)

        async def request(method, path, **kwargs):
            return [{"id": "row-1", "title": "ok"}]

        service._request = request
        row = await SupabaseWorkspaceService._get_row_by_id(service, "diets", "row-1")
        self.assertEqual(row["title"], "ok")

    async def test_ai_training_plan_uses_atomic_rpc(self):
        calls = []

        async def request(method, path, **kwargs):
            calls.append((method, path, kwargs.get("json")))
            return {
                "training_plan_id": "plan-1",
                "workout_id": "workout-1",
                "days_count": 1,
                "exercises_count": 1,
            }

        self.service._request = request
        result = await self.service.create_ai_training_plan(
            nutritionist_id="nutritionist-1",
            patient_id="patient-1",
            title="Treino seguro",
            objective="Condicionamento",
            restrictions=[],
            observations=None,
            days=[
                {
                    "name": "Treino A",
                    "exercises": [
                        {"exercise_name": "Caminhada", "sets": 3, "reps": "10 min"}
                    ],
                }
            ],
        )

        self.assertEqual(result["training_plan_id"], "plan-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0:2], ("POST", "/rest/v1/rpc/create_ai_training_plan"))

    async def test_pending_action_upsert_targets_conversation_user_key(self):
        calls = []

        async def request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return [{"id": "state-1"}]

        self.service._request = request
        state = await self.service.upsert_ai_conversation_state(
            {
                "conversation_id": "chat-1",
                "user_id": "user-1",
                "pending_action": "replace_training_plan",
            }
        )

        self.assertEqual(state["id"], "state-1")
        self.assertEqual(
            calls[0][2]["params"],
            {"on_conflict": "conversation_id,user_id"},
        )
        self.assertEqual(
            calls[0][2]["prefer"],
            "resolution=merge-duplicates,return=representation",
        )


if __name__ == "__main__":
    unittest.main()
