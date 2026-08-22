from .registry import ToolAccess, ToolImpact, ToolSpec


def specs() -> list[ToolSpec]:
    return [
        ToolSpec("get_patient_conditions", "health", ToolAccess.READ, "_get_patient_conditions"),
        ToolSpec("register_injury", "health", ToolAccess.NUTRITIONIST_WRITE, "_register_injury"),
        ToolSpec("add_observation", "health", ToolAccess.NUTRITIONIST_WRITE, "_add_observation"),
        ToolSpec("update_health_condition", "health", ToolAccess.NUTRITIONIST_WRITE, "_update_health_condition"),
        ToolSpec("delete_health_condition", "health", ToolAccess.NUTRITIONIST_WRITE, "_delete_health_condition", ToolImpact.HIGH),
    ]
