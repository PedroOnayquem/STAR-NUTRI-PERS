import json
import unittest

from backend.app.api.routes.chat import (
    _answer_from_agent_actions,
    _with_agent_actions,
)
from backend.app.services.ai_agent_service import AiAgentService
from backend.app.services.ai_guardrail_service import AiGuardrailService
from backend.tests.test_ai_agent_permissions import (
    FakeWorkspace,
    nutritionist_context,
)


class SequencedNutritionAi:
    def __init__(self, calls):
        self.calls = list(calls)
        self.received = []

    async def complete_with_tools(self, **kwargs):
        self.received.append(kwargs)
        if not self.calls:
            return {"content": "evidence_complete"}
        name, arguments = self.calls.pop(0)
        return {
            "tool_calls": [
                {
                    "id": f"call-{len(self.received)}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments),
                    },
                }
            ]
        }


class TacoPipelineWorkspace(FakeWorkspace):
    def __init__(self, confidence="exact"):
        super().__init__()
        self.confidence = confidence
        self.calculations = []

    async def resolve_taco_food(self, *, food_id=None, query=None, limit=10):
        if food_id == "food-integral":
            return {
                "confidence": "exact",
                "query": query,
                "candidates": [],
                "food": {
                    "id": "food-integral",
                    "name": "Arroz, integral, cozido",
                    "energy_kcal": 124,
                    "protein_g": 2.6,
                    "carbohydrate_g": 25.8,
                    "lipid_g": 1.0,
                    "fiber_g": 2.7,
                    "sodium_mg": 1,
                    "source": "TACO",
                    "source_edition": "4ª edição ampliada e revisada",
                    "publication_year": 2011,
                    "source_url": "https://example.test/taco.xlsx",
                    "reference_quantity_g": 100,
                    "reference_basis": "100 g de parte comestível",
                },
            }
        if food_id:
            return {
                "confidence": "exact",
                "query": query,
                "candidates": [],
                "food": {
                    "id": food_id,
                    "name": "Arroz integral cozido",
                    "energy_kcal": 128,
                    "protein_g": 2.5,
                    "carbohydrate_g": 28.1,
                    "lipid_g": 0.2,
                    "fiber_g": 1.6,
                    "sodium_mg": 1,
                    "source": "TACO",
                    "source_edition": "4Âª ediÃ§Ã£o ampliada e revisada",
                    "publication_year": 2011,
                    "source_url": "https://example.test/taco.xlsx",
                    "reference_quantity_g": 100,
                    "reference_basis": "100 g de parte comestÃ­vel",
                },
            }
        if self.confidence == "not_found":
            return {
                "confidence": "not_found",
                "query": query,
                "food": None,
                "candidates": [],
            }
        if self.confidence == "ambiguous":
            return {
                "confidence": "ambiguous",
                "query": query,
                "food": None,
                "candidates": [
                    {
                        "id": "food-integral",
                        "name": "Arroz, integral, cozido",
                        "energy_kcal": 124,
                        "source": "TACO",
                        "reference_quantity_g": 100,
                    },
                    {
                        "id": "food-integral-raw",
                        "name": "Arroz, integral, cru",
                        "energy_kcal": 360,
                        "source": "TACO",
                        "reference_quantity_g": 100,
                    },
                ],
            }
        name = query or "Alimento TACO"
        energy = 76 if "feij" in name.lower() else 128
        return {
            "confidence": self.confidence,
            "query": query,
            "candidates": [],
            "food": {
                "id": f"food-{len(self.calculations) + 1}",
                "name": name,
                "energy_kcal": energy,
                "protein_g": 2.5,
                "carbohydrate_g": 28.1,
                "lipid_g": 0.2,
                "fiber_g": 1.6,
                "sodium_mg": 1,
                "source": "TACO",
                "source_edition": "4ª edição ampliada e revisada",
                "publication_year": 2011,
                "source_url": "https://example.test/taco.xlsx",
                "reference_quantity_g": 100,
                "reference_basis": "100 g de parte comestível",
            },
        }

    async def calculate_taco_food_nutrients(self, *, food_id, quantity_g):
        self.calculations.append((food_id, quantity_g))
        base_energy = 124 if food_id == "food-integral" else 76 if len(self.calculations) > 1 else 128
        factor = quantity_g / 100
        return {
            "energy_kcal": round(base_energy * factor, 2),
            "protein_g": round(2.5 * factor, 2),
            "carbohydrate_g": round(28.1 * factor, 2),
            "lipid_g": round(0.2 * factor, 2),
            "fiber_g": round(1.6 * factor, 2),
            "sodium_mg": round(1 * factor, 2),
        }


class EmptyPatientWorkspace(FakeWorkspace):
    async def list_patient_metrics_for_nutritionist(self, **kwargs):
        self._assert_scope(kwargs["nutritionist_id"], kwargs["patient_id"])
        return {"main_metrics": [], "variable_metrics": [], "latest_weight": None}

    async def list_patient_conditions_for_nutritionist(self, **kwargs):
        self._assert_scope(kwargs["nutritionist_id"], kwargs["patient_id"])
        return []


class AiIntentPipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat = {"id": "40000000-0000-4000-8000-000000000001"}
        self.message = {"id": "50000000-0000-4000-8000-000000000001"}
        self.context = nutritionist_context()

    async def execute_resolver(self, workspace, arguments):
        return await AiAgentService(workspace, SequencedNutritionAi([]))._execute_tool(
            actor=workspace.profile,
            arguments=arguments,
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            intent="nutrition_lookup",
            message=self.message,
            tool_name="resolve_taco_nutrition",
        )

    async def test_taco_resolver_calculates_quantity_and_preserves_source(self):
        workspace = TacoPipelineWorkspace()
        action = await self.execute_resolver(
            workspace,
            {
                "food_name": "Arroz, tipo 1, cozido",
                "quantity_g": 150,
                "requested_nutrients": ["energy_kcal"],
            },
        )

        self.assertTrue(action["success"])
        self.assertEqual(action["intent"], "nutrition_lookup")
        self.assertEqual(action["result"]["nutrients"]["energy_kcal"], 192)
        self.assertEqual(action["result"]["reference"]["quantity_g"], 100)
        self.assertEqual(action["result"]["source"]["name"], "TACO")
        self.assertEqual(workspace.calculations[0][1], 150)

    async def test_ambiguous_taco_food_requests_clarification_without_calculation(self):
        workspace = TacoPipelineWorkspace(confidence="ambiguous")
        action = await self.execute_resolver(
            workspace,
            {"food_name": "arroz", "quantity_g": 150},
        )

        self.assertFalse(action["success"])
        self.assertEqual(action["error_code"], "ambiguous_entity")
        self.assertEqual(action["result"]["resolution"], "ambiguous")
        self.assertTrue(action["result"]["requires_clarification"])
        self.assertEqual(workspace.calculations, [])

    async def test_not_found_food_never_falls_back_to_model_knowledge(self):
        action = await self.execute_resolver(
            TacoPipelineWorkspace(confidence="not_found"),
            {"food_name": "XYZ", "quantity_g": 150},
        )

        self.assertFalse(action["success"])
        self.assertEqual(action["result"]["resolution"], "not_found")
        self.assertEqual(action["result"]["candidates"], [])

    async def test_multiple_foods_are_resolved_before_agent_stops(self):
        workspace = TacoPipelineWorkspace()
        ai = SequencedNutritionAi(
            [
                (
                    "resolve_taco_nutrition",
                    {"food_name": "Arroz, tipo 1, cozido", "quantity_g": 150},
                ),
                (
                    "resolve_taco_nutrition",
                    {"food_name": "Feijão, carioca, cozido", "quantity_g": 100},
                ),
            ]
        )

        actions = await AiAgentService(workspace, ai).run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="Calorias de 150g de arroz tipo 1 cozido e 100g de feijão carioca cozido",
            user_message_record=self.message,
        )

        self.assertEqual(
            [action["tool"] for action in actions],
            ["resolve_taco_nutrition", "resolve_taco_nutrition"],
            actions,
        )
        self.assertTrue(all(action["success"] for action in actions))
        self.assertEqual(len(workspace.calculations), 2)

    def test_search_action_no_longer_short_circuits_final_synthesis(self):
        search_action = {
            "tool": "search_taco_foods",
            "status": "executed",
            "success": True,
            "result": {"summary": "10 alimentos encontrados."},
        }

        self.assertIsNone(_answer_from_agent_actions([search_action]))
        synthesis = _with_agent_actions("PROMPT", [search_action])
        self.assertIn("Busca de candidatos nao e resposta nutricional", synthesis)

    def test_authoritative_taco_result_is_rendered_without_provider_dependency(self):
        answer = _answer_from_agent_actions(
            [
                {
                    "tool": "resolve_taco_nutrition",
                    "status": "executed",
                    "success": True,
                    "result": {
                        "summary": "200g de Frango segundo a TACO: 320 kcal.",
                    },
                }
            ]
        )

        self.assertEqual(answer, "200g de Frango segundo a TACO: 320 kcal.")

    def test_contextual_comparison_is_rendered_from_authoritative_evidence(self):
        answer = _answer_from_agent_actions(
            [
                {
                    "tool": "compare_nutrition_evidence",
                    "status": "executed",
                    "success": True,
                    "result": {
                        "comparisons": [
                            {"quantity_g": 120, "nutrients": {"energy_kcal": 148.8}},
                            {"quantity_g": 200, "nutrients": {"energy_kcal": 248}},
                        ]
                    },
                }
            ]
        )

        self.assertIn("120 g: 148,8 kcal", answer)
        self.assertIn("200 g: 248 kcal", answer)
        self.assertIn("200 g tem mais calorias", answer)
        self.assertIn("Segundo a TACO", answer)

    def test_search_candidates_cannot_ground_arbitrary_nutrient_claim(self):
        validation = AiGuardrailService().validate_output(
            "Segundo a TACO, 150 g de arroz têm 195 kcal.",
            actor={"id": "user-1", "role": "nutritionist"},
            context={"diets": [], "main_metrics": [], "variable_metrics": []},
            agent_actions=[
                {
                    "tool": "search_taco_foods",
                    "status": "executed",
                    "success": True,
                    "result": {
                        "foods": [{"name": "Arroz A", "energy_kcal": 130}]
                    },
                }
            ],
        )

        self.assertFalse(validation.allowed)
        self.assertEqual(validation.category, "unsupported_nutrition_fact")

    def test_total_of_two_authoritative_taco_results_is_grounded(self):
        actions = []
        for energy in (192, 76):
            actions.append(
                {
                    "tool": "resolve_taco_nutrition",
                    "status": "executed",
                    "success": True,
                    "result": {
                        "resolution": "exact",
                        "source": {"name": "TACO"},
                        "nutrients": {"energy_kcal": energy},
                    },
                }
            )

        validation = AiGuardrailService().validate_output(
            "Segundo a TACO: arroz 192 kcal, feijão 76 kcal; total 268 kcal.",
            actor={"id": "user-1", "role": "nutritionist"},
            context={"diets": [], "main_metrics": [], "variable_metrics": []},
            agent_actions=actions,
        )

        self.assertTrue(validation.allowed)

    def test_contextual_comparison_is_grounded_by_prior_tool_evidence(self):
        validation = AiGuardrailService().validate_output(
            "Segundo a TACO, 200 g tÃªm mais calorias: 248 kcal, contra 148,8 kcal em 120 g.",
            actor={"id": "user-1", "role": "nutritionist"},
            context={"diets": [], "main_metrics": [], "variable_metrics": []},
            agent_actions=[
                {
                    "tool": "compare_nutrition_evidence",
                    "status": "executed",
                    "success": True,
                    "result": {
                        "resolution": "exact",
                        "source": {"name": "TACO"},
                        "comparisons": [
                            {"quantity_g": 120, "nutrients": {"energy_kcal": 148.8}},
                            {"quantity_g": 200, "nutrients": {"energy_kcal": 248}},
                        ],
                    },
                }
            ],
        )

        self.assertTrue(validation.allowed, validation)

    async def test_missing_patient_weight_and_injury_are_reported_without_invention(self):
        workspace = EmptyPatientWorkspace()
        service = AiAgentService(workspace, SequencedNutritionAi([]))
        metrics = await service._execute_tool(
            actor=workspace.profile,
            arguments={},
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            intent="patient_metrics_lookup",
            message=self.message,
            tool_name="get_patient_metrics",
        )
        conditions = await service._execute_tool(
            actor=workspace.profile,
            arguments={},
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            intent="patient_conditions_lookup",
            message=self.message,
            tool_name="get_patient_conditions",
        )

        self.assertIn("Não encontrei métricas", metrics["summary"])
        self.assertIn("Não encontrei condições", conditions["summary"])
        validation = AiGuardrailService().validate_output(
            "O peso atual do paciente é 80 kg.",
            actor=workspace.profile,
            context={**self.context, "main_metrics": [], "variable_metrics": []},
            agent_actions=[metrics, conditions],
        )
        self.assertFalse(validation.allowed)
        self.assertEqual(validation.category, "unsupported_patient_fact")

    async def test_run_trace_links_original_message_without_copying_sensitive_text(self):
        workspace = TacoPipelineWorkspace(confidence="ambiguous")
        service = AiAgentService(workspace, SequencedNutritionAi([]))
        action = await self.execute_resolver(
            workspace,
            {"food_name": "arroz", "quantity_g": 150},
        )
        original = "Calorias do arroz para paciente@example.com"

        await service.record_run_trace(
            actor=workspace.profile,
            answer="Qual tipo de arroz?",
            actions=[action],
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            message=self.message,
            output_allowed=True,
            output_category="allowed",
            user_message=original,
        )

        trace = workspace.logs[-1]
        self.assertEqual(trace["tool_name"], "agent_run")
        self.assertEqual(
            trace["result"]["final_decision"],
            "clarification_required",
        )
        self.assertEqual(trace["input"]["message_id"], self.message["id"])
        self.assertNotIn(original, json.dumps(trace, ensure_ascii=False))

    async def test_active_taco_task_preserves_150g_and_executes_after_cozido(self):
        workspace = TacoPipelineWorkspace(confidence="ambiguous")
        ai = SequencedNutritionAi([])
        service = AiAgentService(workspace, ai)
        first_message = {
            "id": "50000000-0000-4000-8000-000000000010",
        }

        first_actions = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message=(
                "Quantas calorias tem 150g de arroz integral segundo a tebela taco?"
            ),
            user_message_record=first_message,
        )

        self.assertEqual(first_actions[0]["status"], "waiting_clarification")
        self.assertEqual(workspace.state["task_status"], "waiting_user")
        self.assertEqual(workspace.state["task_slots"]["quantity_g"], 150)
        self.assertEqual(workspace.state["task_domain"], "nutrition")

        second_actions = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[
                {
                    "role": "user",
                    "content": "Quantas calorias tem 150g de arroz integral segundo a tebela taco?",
                },
                {
                    "role": "assistant",
                    "content": "Você se refere ao arroz integral cozido ou cru?",
                },
            ],
            reasoning_level="medium",
            token="token",
            user_message="cozido",
            user_message_record={
                "id": "50000000-0000-4000-8000-000000000011",
            },
        )

        self.assertEqual([action["tool"] for action in second_actions], ["resolve_taco_nutrition"])
        self.assertTrue(second_actions[0]["success"], second_actions)
        self.assertEqual(second_actions[0]["arguments"]["quantity_g"], 150)
        self.assertEqual(second_actions[0]["result"]["nutrients"]["energy_kcal"], 186)
        self.assertEqual(workspace.calculations[-1], ("food-integral", 150))
        self.assertEqual(workspace.state["task_status"], "completed")
        self.assertEqual(ai.received, [])

    async def test_task_lock_blocks_patient_tool_during_taco_task(self):
        workspace = TacoPipelineWorkspace()
        service = AiAgentService(workspace, SequencedNutritionAi([]))
        active = service.task_state.new_task(
            "Quantas calorias tem 150g de arroz integral segundo a TACO?"
        )

        action = await service._execute_tool(
            actor=workspace.profile,
            active_task=active,
            arguments={"query": "Pedro"},
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            intent=active.intent,
            message=self.message,
            tool_name="search_patient_by_name",
        )

        self.assertEqual(action["status"], "blocked")
        self.assertEqual(action["error_code"], "task_domain_mismatch")
        self.assertEqual(workspace.mutations, [])

    async def test_completed_taco_task_answers_120g_and_200g_followups(self):
        workspace = TacoPipelineWorkspace()
        service = AiAgentService(workspace, SequencedNutritionAi([]))

        first = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="Quantas calorias tem 150g de arroz integral cozido?",
            user_message_record={"id": "50000000-0000-4000-8000-000000000020"},
        )
        second = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="e se for 120g tem quantas calorias?",
            user_message_record={"id": "50000000-0000-4000-8000-000000000021"},
        )
        third = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="e 200g?",
            user_message_record={"id": "50000000-0000-4000-8000-000000000022"},
        )
        comparison = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="qual tem mais calorias?",
            user_message_record={"id": "50000000-0000-4000-8000-000000000023"},
        )

        self.assertEqual(first[0]["result"]["nutrients"]["energy_kcal"], 192)
        self.assertEqual(second[0]["arguments"]["food_id"], first[0]["result"]["food"]["id"])
        self.assertEqual(second[0]["arguments"]["quantity_g"], 120)
        self.assertEqual(third[0]["arguments"]["quantity_g"], 200)
        self.assertEqual(
            [calculation[1] for calculation in workspace.calculations],
            [150, 120, 200],
        )
        self.assertEqual(comparison[0]["tool"], "compare_nutrition_evidence")
        self.assertEqual(
            [item["quantity_g"] for item in comparison[0]["result"]["comparisons"]],
            [150, 120, 200],
        )
        self.assertEqual(workspace.state["task_status"], "completed")
        self.assertEqual(len(workspace.state["task_evidence"]["items"]), 4)

    async def test_frango_frito_clarification_then_bare_answer_executes_lookup(self):
        workspace = TacoPipelineWorkspace()
        service = AiAgentService(workspace, SequencedNutritionAi([]))

        first = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="Quantas calorias tem um frango frito?",
            user_message_record={"id": "50000000-0000-4000-8000-000000000030"},
        )
        second = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[
                {"role": "user", "content": "Quantas calorias tem um frango frito?"},
                {"role": "assistant", "content": "Qual quantidade voce deseja consultar?"},
            ],
            reasoning_level="medium",
            token="token",
            user_message="Frango frito, 200g",
            user_message_record={"id": "50000000-0000-4000-8000-000000000031"},
        )

        self.assertEqual(first[0]["status"], "waiting_clarification")
        self.assertEqual(first[0]["result"]["active_task"]["missing_slots"], ["quantity_g"])
        self.assertEqual(second[0]["tool"], "resolve_taco_nutrition")
        self.assertTrue(second[0]["success"], second)
        self.assertEqual(second[0]["arguments"]["food_name"], "frango frito")
        self.assertEqual(second[0]["arguments"]["quantity_g"], 200)
        self.assertEqual(workspace.state["task_status"], "completed")

    async def test_context_free_bare_quantity_requests_food_without_provider(self):
        workspace = TacoPipelineWorkspace()
        ai = SequencedNutritionAi([])
        service = AiAgentService(workspace, ai)

        actions = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="e 120g?",
            user_message_record={"id": "50000000-0000-4000-8000-000000000032"},
        )

        self.assertEqual(actions[0]["tool"], "conversation_state")
        self.assertEqual(actions[0]["status"], "waiting_clarification")
        self.assertIn("food_name", actions[0]["result"]["active_task"]["missing_slots"])
        self.assertEqual(ai.received, [])

    async def test_concurrent_turn_in_same_conversation_is_blocked(self):
        workspace = TacoPipelineWorkspace()
        workspace.claimed_message_id = "50000000-0000-4000-8000-000000000099"
        service = AiAgentService(workspace, SequencedNutritionAi([]))

        actions = await service.run(
            chat=self.chat,
            chat_scope="nutritionist",
            context=self.context,
            history=[],
            reasoning_level="medium",
            token="token",
            user_message="cozido",
            user_message_record=self.message,
        )

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["status"], "blocked")
        self.assertEqual(actions[0]["error_code"], "conversation_turn_in_progress")
        self.assertEqual(workspace.claimed_message_id, "50000000-0000-4000-8000-000000000099")
        self.assertEqual(workspace.mutations, [])


if __name__ == "__main__":
    unittest.main()
