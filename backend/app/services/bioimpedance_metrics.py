from __future__ import annotations

from datetime import datetime, timezone


METRIC_DEFINITIONS: dict[str, tuple[str, str | None, float | None, float | None]] = {
    "height_cm": ("Altura", "cm", 80, 250),
    "weight_kg": ("Peso", "kg", 20, 400),
    "bmi": ("IMC", None, 10, 80),
    "body_fat_percent": ("Gordura corporal", "%", 2, 75),
    "body_fat_kg": ("Gordura corporal em kg", "kg", 1, 200),
    "muscle_mass_kg": ("Massa muscular", "kg", 1, 200),
    "skeletal_muscle_kg": ("Musculo esqueletico", "kg", 1, 200),
    "fat_free_mass_kg": ("Massa magra", "kg", 1, 250),
    "body_water_kg": ("Agua corporal", "kg", 1, 250),
    "protein_kg": ("Proteina", "kg", 1, 80),
    "mineral_kg": ("Sal inorganico", "kg", 0.1, 30),
    "visceral_fat_level": ("Gordura visceral", None, 1, 60),
    "basal_metabolic_rate": ("Taxa metabolica basal", "kcal", 500, 5000),
    "subcutaneous_fat_percent": ("Gordura subcutanea", "%", 1, 80),
    "smi": ("SMI", None, 1, 20),
    "body_age": ("Idade corporal", "anos", 1, 120),
    "whr": ("WHR", None, 0.5, 2),
    "target_weight_kg": ("Peso alvo", "kg", 20, 400),
    "weight_control_kg": ("Controle de peso", "kg", -200, 200),
    "fat_control_kg": ("Controle de gordura", "kg", -200, 200),
    "muscle_control_kg": ("Controle muscular", "kg", -200, 200),
}


def imported_metrics_to_rows(
    *,
    payload: dict,
    patient_id: str,
    import_id: str,
    source_type: str = "bioimpedance_report",
) -> list[dict]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    measured_at = (
        payload.get("measurement", {}).get("measured_at")
        if isinstance(payload.get("measurement"), dict)
        else None
    )
    recorded_at = measured_at or datetime.now(timezone.utc).isoformat()
    rows = []
    for key, value in metrics.items():
        definition = METRIC_DEFINITIONS.get(key)
        if not definition or value is None:
            continue
        label, unit, _, _ = definition
        rows.append(
            {
                "patient_id": patient_id,
                "name": label,
                "value": str(value).replace(".", ","),
                "unit": unit,
                "recorded_at": recorded_at,
                "source_type": source_type,
                "source_import_id": import_id,
            }
        )
    return rows
