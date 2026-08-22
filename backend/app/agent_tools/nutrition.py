from .registry import ToolAccess, ToolImpact, ToolSpec


def specs() -> list[ToolSpec]:
    return [
        ToolSpec("create_diet_plan", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_create_diet_plan"),
        ToolSpec("update_diet_plan", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_update_diet_plan"),
        ToolSpec("delete_diet_plan", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_delete_diet_plan", ToolImpact.HIGH),
        ToolSpec("update_diet_meal", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_update_diet_meal"),
        ToolSpec("delete_diet_meal", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_delete_diet_meal", ToolImpact.HIGH),
        ToolSpec("add_food_to_meal", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_add_food_to_meal"),
        ToolSpec("add_taco_food_to_meal", "nutrition", ToolAccess.NUTRITIONIST_WRITE, "_add_taco_food_to_meal"),
        ToolSpec("resolve_taco_nutrition", "nutrition", ToolAccess.READ, "_resolve_taco_nutrition", patient_context_required=False),
        ToolSpec("search_taco_foods", "nutrition", ToolAccess.READ, "_search_taco_foods", patient_context_required=False),
        ToolSpec("get_taco_food", "nutrition", ToolAccess.READ, "_get_taco_food", patient_context_required=False),
        ToolSpec("calculate_taco_food_nutrients", "nutrition", ToolAccess.READ, "_calculate_taco_food_nutrients", patient_context_required=False),
    ]
