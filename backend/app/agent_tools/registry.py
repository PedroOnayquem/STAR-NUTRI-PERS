from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolAccess(StrEnum):
    READ = "read"
    NUTRITIONIST_WRITE = "nutritionist_write"


class ToolImpact(StrEnum):
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    domain: str
    access: ToolAccess
    handler: str
    impact: ToolImpact = ToolImpact.NORMAL
    patient_context_required: bool = True


class AgentToolRegistry:
    """Single source of truth for tool discovery, access and dispatch metadata."""

    def __init__(self, schemas: list[dict[str, Any]], specs: list[ToolSpec]) -> None:
        schema_by_name = {
            item["function"]["name"]: item
            for item in schemas
            if isinstance(item.get("function"), dict)
        }
        self._specs = {spec.name: spec for spec in specs}
        missing = set(self._specs) - set(schema_by_name)
        if missing:
            raise ValueError(f"Schemas ausentes para tools: {', '.join(sorted(missing))}")
        self._schemas = {name: schema_by_name[name] for name in self._specs}

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def schemas_for(self, allowed_names: set[str]) -> list[dict[str, Any]]:
        return [self._schemas[name] for name in self._schemas if name in allowed_names]

    def names_for_nutritionist(self, *, has_patient_context: bool) -> set[str]:
        # General chats may first resolve a patient and then continue with a
        # patient-scoped operation in the same tool loop. Handlers still deny
        # every write until an authorized context has actually been hydrated.
        return set(self._specs)

    @property
    def names(self) -> set[str]:
        return set(self._specs)


def default_specs() -> list[ToolSpec]:
    from .health import specs as health_specs
    from .nutrition import specs as nutrition_specs
    from .patients import specs as patient_specs
    from .progress import specs as progress_specs
    from .scheduling import specs as scheduling_specs
    from .training import specs as training_specs

    return [
        *patient_specs(),
        *progress_specs(),
        *health_specs(),
        *nutrition_specs(),
        *scheduling_specs(),
        *training_specs(),
    ]
