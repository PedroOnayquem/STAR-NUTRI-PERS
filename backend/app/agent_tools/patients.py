from .registry import ToolAccess, ToolSpec


def specs() -> list[ToolSpec]:
    return [
        ToolSpec("search_patient_by_name", "patients", ToolAccess.READ, "_search_patient_by_name", patient_context_required=False),
        ToolSpec("get_patient_profile", "patients", ToolAccess.READ, "_get_patient_profile"),
        ToolSpec("get_patient_summary", "patients", ToolAccess.READ, "_get_patient_summary"),
        ToolSpec("update_patient_profile", "patients", ToolAccess.NUTRITIONIST_WRITE, "_update_patient_profile"),
        ToolSpec("update_patient_birth_date", "patients", ToolAccess.NUTRITIONIST_WRITE, "_update_patient_birth_date"),
    ]
