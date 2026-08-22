import unittest

from backend.app.services.ai_task_state_service import AiTaskStateService


class AiTaskStateTests(unittest.TestCase):
    def setUp(self):
        self.service = AiTaskStateService()

    def test_initial_taco_task_extracts_authoritative_slots_with_typos(self):
        task = self.service.new_task(
            "Quantas calorias tem 150g de arros integral segundo a tebela taco?"
        )

        self.assertEqual(task.domain, "nutrition")
        self.assertEqual(task.intent, "taco_nutrition_lookup")
        self.assertEqual(task.slots["food_name"], "arros integral")
        self.assertEqual(task.slots["quantity_g"], 150)
        self.assertEqual(task.slots["source"], "TACO")
        self.assertEqual(task.slots["requested_nutrients"], ["energy_kcal"])

    def test_short_preparation_merges_without_erasing_quantity(self):
        state = {
            "id": "state-a",
            "task_domain": "nutrition",
            "task_intent": "taco_nutrition_lookup",
            "task_status": "waiting_user",
            "task_slots": {
                "food_name": "arroz integral",
                "quantity_g": 150,
                "source": "TACO",
                "requested_nutrients": ["energy_kcal"],
                "candidates": [
                    {"id": "cooked", "name": "Arroz, integral, cozido"},
                    {"id": "raw", "name": "Arroz, integral, cru"},
                ],
            },
            "required_slots": [
                "food_name",
                "quantity_g",
                "source",
                "requested_nutrients",
            ],
            "missing_slots": [],
            "ambiguous_slots": ["food_variant"],
            "allowed_tools": [
                "resolve_taco_nutrition",
                "search_taco_foods",
                "get_taco_food",
                "calculate_taco_food_nutrients",
            ],
        }

        task = self.service.prepare_turn(state=state, user_message="cozido")

        self.assertTrue(task.is_ready)
        self.assertEqual(task.slots["food_id"], "cooked")
        self.assertEqual(task.slots["quantity_g"], 150)
        self.assertEqual(task.slots["source"], "TACO")

    def test_generic_continuation_does_not_switch_domain(self):
        state = self._nutrition_state()
        for message in ("faça a consulta", "continue", "pode", "isso"):
            task = self.service.prepare_turn(state=state, user_message=message)
            self.assertEqual(task.domain, "nutrition", message)
            self.assertEqual(task.intent, "taco_nutrition_lookup", message)

    def test_explicit_patient_request_switches_domain(self):
        task = self.service.prepare_turn(
            state=self._nutrition_state(),
            user_message="Agora procure o paciente Pedro.",
        )

        self.assertEqual(task.domain, "patients")
        self.assertEqual(task.intent, "patients_task")
        self.assertIn("search_patient_by_name", task.allowed_tools)
        self.assertNotIn("resolve_taco_nutrition", task.allowed_tools)

    def test_contextual_food_then_quantity_promotes_same_task(self):
        context_task = self.service.new_task(
            "Estou analisando arroz integral cozido."
        )
        state = self.service.payload(
            context_task,
            conversation_id="conversation-a",
            user_id="user-a",
            patient_id=None,
            last_message_id="message-a",
            expires_at="2026-08-22T20:00:00Z",
        )
        state["id"] = "state-a"

        task = self.service.prepare_turn(
            state=state,
            user_message="Quanto tem em 150g?",
        )

        self.assertEqual(task.intent, "taco_nutrition_lookup")
        self.assertEqual(task.slots["food_name"], "arroz integral cozido")
        self.assertEqual(task.slots["quantity_g"], 150)
        self.assertEqual(task.slots["requested_nutrients"], ["energy_kcal"])

    def test_two_conversation_states_never_share_slots(self):
        state_a = self._nutrition_state()
        state_b = {
            "id": "state-b",
            "task_domain": "patients",
            "task_intent": "patients_task",
            "task_status": "waiting_user",
            "task_slots": {"patient_name": "Pedro"},
            "required_slots": [],
            "missing_slots": [],
            "ambiguous_slots": [],
            "allowed_tools": ["search_patient_by_name"],
        }

        task_a = self.service.prepare_turn(state=state_a, user_message="cozido")
        task_b = self.service.prepare_turn(state=state_b, user_message="continue")

        self.assertEqual(task_a.domain, "nutrition")
        self.assertNotIn("patient_name", task_a.slots)
        self.assertEqual(task_b.domain, "patients")
        self.assertNotIn("quantity_g", task_b.slots)

    def _nutrition_state(self):
        return {
            "id": "state-a",
            "task_domain": "nutrition",
            "task_intent": "taco_nutrition_lookup",
            "task_status": "waiting_user",
            "task_slots": {
                "food_name": "arroz integral",
                "quantity_g": 150,
                "source": "TACO",
                "requested_nutrients": ["energy_kcal"],
            },
            "required_slots": [
                "food_name",
                "quantity_g",
                "source",
                "requested_nutrients",
            ],
            "missing_slots": [],
            "ambiguous_slots": ["food_variant"],
            "allowed_tools": [
                "resolve_taco_nutrition",
                "search_taco_foods",
                "get_taco_food",
                "calculate_taco_food_nutrients",
            ],
        }


if __name__ == "__main__":
    unittest.main()
