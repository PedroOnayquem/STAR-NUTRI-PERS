from .registry import ToolAccess, ToolSpec


def specs() -> list[ToolSpec]:
    return [
        ToolSpec("create_appointment", "scheduling", ToolAccess.NUTRITIONIST_WRITE, "_create_appointment"),
        ToolSpec("create_patient_appointment", "scheduling", ToolAccess.NUTRITIONIST_WRITE, "_create_appointment"),
    ]
