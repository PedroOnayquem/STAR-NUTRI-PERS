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
                        "id": "food-tipo-1",
                        "name": "Arroz, tipo 1, cozido",
                        "energy_kcal": 128,
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
        base_energy = 76 if len(self.calculations) > 1 else 128
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


if __name__ == "__main__":
    unittest.main()
