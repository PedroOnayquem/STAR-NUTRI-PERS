from .registry import ToolAccess, ToolSpec


def specs() -> list[ToolSpec]:
    return [
        ToolSpec("get_patient_metrics", "progress", ToolAccess.READ, "_get_patient_metrics"),
        ToolSpec("register_weight_change", "progress", ToolAccess.NUTRITIONIST_WRITE, "_register_weight_change"),
        ToolSpec("register_progress", "progress", ToolAccess.NUTRITIONIST_WRITE, "_register_progress"),
    ]
