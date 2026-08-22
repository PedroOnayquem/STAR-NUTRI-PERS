from .registry import ToolAccess, ToolImpact, ToolSpec


def specs() -> list[ToolSpec]:
    return [
        ToolSpec("create_training_plan", "training", ToolAccess.NUTRITIONIST_WRITE, "_create_training_plan"),
        ToolSpec("replace_training_plan", "training", ToolAccess.NUTRITIONIST_WRITE, "_replace_training_plan", ToolImpact.HIGH),
        ToolSpec("update_workout", "training", ToolAccess.NUTRITIONIST_WRITE, "_update_workout"),
        ToolSpec("delete_workout", "training", ToolAccess.NUTRITIONIST_WRITE, "_delete_workout", ToolImpact.HIGH),
        ToolSpec("add_workout_exercise", "training", ToolAccess.NUTRITIONIST_WRITE, "_add_workout_exercise"),
        ToolSpec("update_workout_exercise", "training", ToolAccess.NUTRITIONIST_WRITE, "_update_workout_exercise"),
        ToolSpec("remove_workout_exercise", "training", ToolAccess.NUTRITIONIST_WRITE, "_remove_workout_exercise", ToolImpact.HIGH),
        ToolSpec("add_workout_observation", "training", ToolAccess.NUTRITIONIST_WRITE, "_add_workout_observation"),
        # Compatibility for already persisted confirmation states.
        ToolSpec("request_confirmation", "system", ToolAccess.NUTRITIONIST_WRITE, "_request_confirmation", ToolImpact.HIGH),
    ]
