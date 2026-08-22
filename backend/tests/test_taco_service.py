from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from backend.app.services.ai_agent_service import _calculate_taco_nutrients
from backend.app.services.supabase_workspace_service import SupabaseWorkspaceService


class TacoWorkspaceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_ranked_rpc_instead_of_unindexed_ilike(self) -> None:
        service = SupabaseWorkspaceService.__new__(SupabaseWorkspaceService)
        service._request = AsyncMock(return_value=[{"name": "Arroz", "match_kind": "prefix"}])

        rows = await service.search_taco_foods(query="arroz", category=None, limit=6)

        self.assertEqual(rows[0]["name"], "Arroz")
        service._request.assert_awaited_once_with(
            "POST",
            "/rest/v1/rpc/search_taco_foods",
            json={"p_query": "arroz", "p_category": None, "p_limit": 6, "p_offset": 0},
        )

    async def test_ambiguous_food_name_is_not_selected_automatically(self) -> None:
        service = SupabaseWorkspaceService.__new__(SupabaseWorkspaceService)
        service.search_taco_foods = AsyncMock(
            return_value=[
                {"id": "1", "name": "Arroz, integral, cozido", "match_kind": "prefix"},
                {"id": "2", "name": "Arroz, tipo 1, cozido", "match_kind": "prefix"},
            ]
        )

        with self.assertRaisesRegex(ValueError, "ambiguo"):
            await service.find_taco_food(query="arroz")

    async def test_exact_food_name_is_resolved_even_with_similar_candidates(self) -> None:
        service = SupabaseWorkspaceService.__new__(SupabaseWorkspaceService)
        exact = {"id": "1", "name": "Arroz, integral, cozido", "match_kind": "exact"}
        service.search_taco_foods = AsyncMock(return_value=[exact, {"id": "2", "match_kind": "similar"}])
        service.get_taco_food = AsyncMock(return_value={**exact, "nutrient_details": []})

        resolved = await service.find_taco_food(query="arroz integral cozido")

        self.assertEqual(resolved["id"], "1")
        service.get_taco_food.assert_awaited_once_with("1")


class TacoCalculationTests(unittest.TestCase):
    def test_missing_and_trace_values_remain_unavailable_instead_of_zero(self) -> None:
        result = _calculate_taco_nutrients(
            {
                "carbohydrate_g": 25.8,
                "energy_kcal": 124,
                "fiber_g": 2.7,
                "lipid_g": 1,
                "protein_g": 2.6,
                "sodium_mg": None,
            },
            150,
        )

        self.assertEqual(result["energy_kcal"], 186)
        self.assertEqual(result["protein_g"], 3.9)
        self.assertIsNone(result["sodium_mg"])


if __name__ == "__main__":
    unittest.main()
