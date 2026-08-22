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

    def test_completed_task_inherits_food_source_and_nutrient_for_new_quantity(self):
        state = self._completed_nutrition_state()

        task = self.service.prepare_turn(
            state=state,
            user_message="e se for 120g tem quantas calorias?",
        )

        self.assertEqual(task.status, "ready")
        self.assertEqual(task.slots["food_id"], "food-integral")
        self.assertEqual(task.slots["food_name"], "Arroz, integral, cozido")
        self.assertEqual(task.slots["quantity_g"], 120)
        self.assertEqual(task.slots["source"], "TACO")
        self.assertEqual(task.slots["requested_nutrients"], ["energy_kcal"])
        self.assertEqual(task.evidence["latest"]["source_type"], "FACT_FROM_TOOL")

    def test_completed_task_supports_successive_quantity_followups(self):
        first = self.service.prepare_turn(
            state=self._completed_nutrition_state(),
            user_message="e 120g?",
        )
        first_state = self.service.payload(
            first,
            conversation_id="conversation-a",
            user_id="user-a",
            patient_id=None,
            last_message_id="message-b",
            expires_at="2026-09-22T20:00:00Z",
            status="completed",
        )
        first_state["id"] = "state-a"

        second = self.service.prepare_turn(state=first_state, user_message="e 200g?")

        self.assertEqual(second.slots["quantity_g"], 200)
        self.assertEqual(second.slots["food_id"], "food-integral")
        self.assertEqual(second.intent, "taco_nutrition_lookup")

    def test_completed_task_does_not_hijack_unrelated_conversation(self):
        task = self.service.prepare_turn(
            state=self._completed_nutrition_state(),
            user_message="Oi, tudo bem?",
        )

        self.assertIsNone(task)

    def test_food_replacement_clears_stale_food_identifier(self):
        task = self.service.prepare_turn(
            state=self._completed_nutrition_state(),
            user_message="e se eu trocar por arroz branco cozido?",
        )

        self.assertEqual(task.slots["food_name"], "arroz branco cozido")
        self.assertNotIn("food_id", task.slots)
        self.assertEqual(task.slots["quantity_g"], 150)

    def test_quantity_without_any_context_correctly_requires_food(self):
        task = self.service.prepare_turn(
            state=None,
            user_message="e se for 120g tem quantas calorias?",
        )

        self.assertEqual(task.intent, "taco_nutrition_lookup")
        self.assertIn("food_name", task.missing_slots)

    def test_comparison_followup_keeps_prior_authoritative_evidence(self):
        state = self._completed_nutrition_state()
        state["task_evidence"]["items"] = [
            {
                "source_type": "FACT_FROM_TOOL",
                "arguments": {"quantity_g": 120},
                "result": {"nutrients": {"energy_kcal": 148.8}},
            },
            {
                "source_type": "FACT_FROM_TOOL",
                "arguments": {"quantity_g": 200},
                "result": {"nutrients": {"energy_kcal": 248}},
            },
        ]
        state["task_slots"]["quantity_g"] = 200

        task = self.service.prepare_turn(
            state=state,
            user_message="qual tem mais calorias?",
        )

        self.assertEqual(task.slots["food_id"], "food-integral")
        self.assertEqual(task.slots["quantity_g"], 200)
        self.assertEqual(len(task.evidence["items"]), 2)

    def test_protein_followup_inherits_chicken_and_changes_only_quantity(self):
        task = self.service.new_task("Qual a proteina de 100g de frango cozido?")
        state = self.service.payload(
            task,
            conversation_id="conversation-protein",
            user_id="user-a",
            patient_id=None,
            last_message_id="message-protein",
            expires_at="2026-09-22T20:00:00Z",
            status="completed",
        )
        state["id"] = "state-protein"

        followup = self.service.prepare_turn(state=state, user_message="e em 200g?")

        self.assertEqual(followup.slots["food_name"], "frango cozido")
        self.assertEqual(followup.slots["quantity_g"], 200)
        self.assertEqual(followup.slots["requested_nutrients"], ["protein_g"])

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

    def _completed_nutrition_state(self):
        state = self._nutrition_state()
        state.update(
            {
                "task_status": "completed",
                "ambiguous_slots": [],
                "task_slots": {
                    "food_id": "food-integral",
                    "food_name": "Arroz, integral, cozido",
                    "preparation": "cozido",
                    "quantity_g": 150,
                    "unit": "g",
                    "source": "TACO",
                    "requested_nutrients": ["energy_kcal"],
                },
                "task_evidence": {
                    "latest": {
                        "source_type": "FACT_FROM_TOOL",
                        "tool": "resolve_taco_nutrition",
                    },
                    "items": [],
                },
                "context_entities": {},
            }
        )
        return state


if __name__ == "__main__":
    unittest.main()
