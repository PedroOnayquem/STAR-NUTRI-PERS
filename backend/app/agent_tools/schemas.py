from __future__ import annotations

from typing import Any


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_patient_by_name",
            "description": (
                "Busca pacientes reais do nutricionista por nome completo, primeiro nome "
                "ou busca parcial sem diferenciar maiúsculas, minúsculas ou acentos. "
                "Use antes de afirmar que um paciente citado não existe."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_profile",
            "description": (
                "Lê o cadastro real de um paciente do nutricionista e retorna nome, gênero, "
                "data de nascimento, idade calculada, altura quando houver métrica, objetivo "
                "e observações. Use para perguntas sobre idade, nascimento, objetivo ou perfil."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_metrics",
            "description": "Consulta métricas reais do paciente, incluindo peso atual quando cadastrado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_conditions",
            "description": "Consulta condições clínicas, alergias, restrições, lesões e observações clínicas cadastradas do paciente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_summary",
            "description": (
                "Consulta um resumo operacional real do paciente com cadastro, idade calculada, "
                "métricas recentes, condições, dietas, treinos e agenda."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient_profile",
            "description": (
                "Atualiza campos simples do perfil do paciente em foco. Use somente com paciente "
                "em foco e quando a alteração estiver clara."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "birth_date": {"type": "string"},
                    "full_name": {"type": "string"},
                    "gender": {"type": "string"},
                    "is_active": {"type": "boolean"},
                    "notes": {"type": "string"},
                    "objective": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "phone": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_diet_plan",
            "description": (
                "Cria e cadastra um plano alimentar estruturado para o paciente em foco. "
                "Se ja houver plano ativo, salva o novo inativo para nao substituir sem confirmacao."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein": {"type": "number"},
                    "carbs": {"type": "number"},
                    "fats": {"type": "number"},
                    "water_goal_ml": {"type": "number"},
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "meals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "meal_name": {"type": "string"},
                                "meal_time": {
                                    "description": "Horário opcional no formato HH:MM de 24 horas.",
                                    "type": "string",
                                },
                                "foods": {"type": "array", "items": {"type": "object"}},
                                "notes": {"type": "string"},
                            },
                            "required": ["meal_name", "foods"],
                        },
                    },
                },
                "required": ["title", "meals"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_diet_plan",
            "description": (
                "Atualiza campos nao destrutivos de um plano alimentar autorizado. "
                "Nao ativa, substitui nem apaga planos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diet_id": {"type": "string"},
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein": {"type": "number"},
                    "carbs": {"type": "number"},
                    "fats": {"type": "number"},
                    "water_goal_ml": {"type": "number"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_injury",
            "description": (
                "Registra uma lesao, dor localizada ou problema fisico como condicao "
                "do paciente em foco. Use somente dados estruturados extraidos da "
                "intencao; nunca envie o prompt bruto como descricao ou notas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "description": "Data de inicio em YYYY-MM-DD. Use hoje se nao informada.",
                        "type": "string",
                    },
                    "description": {
                        "description": "Descricao clinica curta e estruturada, nunca o prompt bruto.",
                        "type": "string",
                    },
                    "local": {
                        "description": "Local anatomico da lesao, exemplo: Olho, Joelho, Ombro.",
                        "type": "string",
                    },
                    "notes": {
                        "description": "Observacoes opcionais curtas, sem copiar o prompt bruto.",
                        "type": "string",
                    },
                    "origin": {
                        "description": "Origem/causa objetiva, exemplo: trauma com cano atravessado.",
                        "type": "string",
                    },
                    "patient_id": {
                        "description": "ID do paciente em foco, quando conhecido pelo contexto operacional.",
                        "type": "string",
                    },
                    "patient_name": {"type": "string"},
                    "recommendations": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": ["local", "description", "severity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_weight_change",
            "description": "Registra peso atual ou calcula novo peso a partir de uma alteracao em kg.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_weight_kg": {"type": "number"},
                    "delta_kg": {"type": "number"},
                    "patient_name": {"type": "string"},
                    "recorded_at": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "register_progress",
            "description": "Registra uma metrica corporal simples, como cintura, quadril, percentual de gordura ou outra evolucao.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "recorded_at": {"type": "string"},
                },
                "required": ["metric_name", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_observation",
            "description": "Adiciona uma observacao relevante ao prontuario/contexto do paciente em foco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "title": {"type": "string"},
                    "observation": {"type": "string"},
                },
                "required": ["observation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_food_to_meal",
            "description": "Adiciona um alimento a uma refeicao da dieta ativa do paciente em foco. Uso exclusivo do nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "meal_name": {"type": "string"},
                    "food_name": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "quantity": {"type": "string"},
                    "notes": {"type": "string"},
                    "calories": {"type": "number"},
                    "protein_g": {"type": "number"},
                    "carbs_g": {"type": "number"},
                    "fats_g": {"type": "number"},
                },
                "required": ["meal_name", "food_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_taco_nutrition",
            "description": (
                "Conclui uma consulta nutricional baseada na TACO: resolve o alimento, "
                "classifica a correspondência como exact/probable/ambiguous/not_found e, "
                "quando segura, calcula deterministicamente os nutrientes para quantity_g. "
                "Use como primeira opção quando o usuário pedir calorias, macros ou nutrientes. "
                "Se o alimento ou a quantidade estiver no histórico, preserve esse contexto. "
                "Retorna alimento, quantidade, base de referência, nutrientes, fonte e candidatos "
                "quando precisar de esclarecimento. Nunca escolha uma opção ambiguous."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {
                        "description": "Nome do alimento extraído da mensagem ou do contexto recente.",
                        "type": "string",
                    },
                    "quantity_g": {
                        "description": "Quantidade em gramas; use 100 somente quando nenhuma quantidade foi informada.",
                        "type": "number",
                    },
                    "requested_nutrients": {
                        "description": "Nutrientes pedidos, como energy_kcal, protein_g ou sodium_mg.",
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["food_name", "quantity_g"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_taco_foods",
            "description": (
                "Localiza candidatos reais na TACO e retorna correspondências estruturadas. "
                "Serve para descoberta e NÃO conclui perguntas sobre calorias ou macros. "
                "Para alimento e quantidade, use resolve_taco_nutrition."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "category": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_taco_food",
            "description": (
                "Obtém a composição-fonte por 100g de uma entrada TACO já identificada. "
                "Não converte quantidade; use resolve_taco_nutrition para responder calorias ou macros."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_taco_food_nutrients",
            "description": (
                "Calcula nutrientes quando o food_id ou nome específico já foi resolvido. "
                "Não escolha candidatos ambíguos. Para linguagem natural, prefira resolve_taco_nutrition."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {"type": "string"},
                    "quantity_g": {"type": "number"},
                    "quantity": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_taco_food_to_meal",
            "description": "Adiciona um alimento da TACO a uma refeição da dieta ativa do paciente em foco e calcula macros automaticamente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {"type": "string"},
                    "food_name": {"type": "string"},
                    "meal_name": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "quantity_g": {"type": "number"},
                    "quantity": {"type": "string"},
                },
                "required": ["meal_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_patient_birth_date",
            "description": (
                "Atualiza a data de nascimento do paciente em foco quando a nova data "
                "estiver claramente informada. Para ano abreviado, como 'nasceu em 98', "
                "use o dia e mes atuais do cadastro se existirem e converta para YYYY-MM-DD."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "birth_date": {
                        "description": "Data completa no formato YYYY-MM-DD.",
                        "type": "string",
                    },
                    "birth_year": {
                        "description": "Ano de nascimento quando apenas o ano foi informado.",
                        "type": "integer",
                    },
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": "Cria retorno/consulta na agenda para o paciente em foco. Uso exclusivo do nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "scheduled_at_iso": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "location": {"type": "string"},
                    "meeting_link": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["scheduled_at_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_patient_appointment",
            "description": "Cria um compromisso real na agenda do paciente para o nutricionista.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "nutritionist_id": {"type": "string"},
                    "title": {"type": "string"},
                    "type": {"type": "string"},
                    "date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "location": {"type": "string"},
                    "meeting_link": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["title", "type", "date", "start_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_training_plan",
            "description": (
                "Cria e cadastra um plano de treino real para o paciente em foco. "
                "Use quando o usuario pedir para montar/salvar/cadastrar treino. "
                "Converta qualquer tabela em JSON estruturado com dias e exercicios; "
                "nunca envie markdown bruto ou texto unico."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "restrictions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "observations": {"type": "string"},
                    "suggested_observation": {
                        "description": "Observacao extra a sugerir para confirmacao posterior, se fizer sentido.",
                        "type": "string",
                    },
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "focus": {"type": "string"},
                                "exercises": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "muscle_group": {"type": "string"},
                                            "exercise_name": {"type": "string"},
                                            "sets": {"type": "integer"},
                                            "reps": {"type": "string"},
                                            "rest": {"type": "string"},
                                            "load_guidance": {"type": "string"},
                                            "notes": {"type": "string"},
                                        },
                                        "required": ["exercise_name"],
                                    },
                                },
                            },
                            "required": ["name", "exercises"],
                        },
                    },
                },
                "required": ["title", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_workout_observation",
            "description": (
                "Adiciona uma observacao estruturada a um plano de treino existente, "
                "geralmente apos confirmacao curta de uma pending_action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "training_plan_id": {"type": "string"},
                    "observation": {"type": "string"},
                },
                "required": ["training_plan_id", "observation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "replace_training_plan",
            "description": (
                "Substitui o treino atual por um novo plano estruturado. Esta operação "
                "é de alto impacto e o backend sempre exigirá confirmação humana."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "title": {"type": "string"},
                    "objective": {"type": "string"},
                    "restrictions": {"type": "array", "items": {"type": "string"}},
                    "observations": {"type": "string"},
                    "days": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "focus": {"type": "string"},
                                "exercises": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "muscle_group": {"type": "string"},
                                            "exercise_name": {"type": "string"},
                                            "sets": {"type": "integer"},
                                            "reps": {"type": "string"},
                                            "rest": {"type": "string"},
                                            "load_guidance": {"type": "string"},
                                            "notes": {"type": "string"},
                                        },
                                        "required": ["exercise_name"],
                                    },
                                },
                            },
                            "required": ["name", "exercises"],
                        },
                    },
                },
                "required": ["title", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": "Registra uma acao critica que precisa de confirmacao humana antes de executar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_description": {"type": "string"},
                    "pending_action": {
                        "description": "Nome da ferramenta real que sera executada apos confirmacao.",
                        "type": "string",
                    },
                    "pending_payload": {
                        "description": "Argumentos completos para executar a ferramenta real apos confirmacao.",
                        "type": "object",
                    },
                    "question": {"type": "string"},
                    "risk": {"type": "string"},
                    "target_entity": {"type": "string"},
                },
                "required": ["action_description", "pending_action", "pending_payload", "question"],
            },
        },
    },
]


def _operational_tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict:
    parameters: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


AGENT_TOOLS.extend(
    [
        _operational_tool("delete_diet_plan", "Exclui permanentemente uma dieta autorizada; sempre exige confirmação do backend.", {"diet_id": {"type": "string"}, "patient_id": {"type": "string"}, "patient_name": {"type": "string"}}),
        _operational_tool("update_diet_meal", "Atualiza nome, horário, alimentos ou notas de uma refeição existente.", {"meal_id": {"type": "string"}, "meal_name": {"type": "string"}, "meal_time": {"type": "string"}, "foods": {"type": "array", "items": {"type": "object"}}, "notes": {"type": "string"}}, ["meal_id"]),
        _operational_tool("delete_diet_meal", "Remove permanentemente uma refeição; sempre exige confirmação do backend.", {"meal_id": {"type": "string"}}, ["meal_id"]),
        _operational_tool("update_workout", "Atualiza campos não destrutivos do treino exibido na aba Treinos.", {"workout_id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "frequency_per_week": {"type": "integer"}, "is_active": {"type": "boolean"}}),
        _operational_tool("delete_workout", "Exclui permanentemente o treino da aba Treinos; sempre exige confirmação do backend.", {"workout_id": {"type": "string"}}),
        _operational_tool("add_workout_exercise", "Adiciona um exercício estruturado a um treino existente.", {"workout_id": {"type": "string"}, "exercise_name": {"type": "string"}, "muscle_group": {"type": "string"}, "sets": {"type": "integer"}, "reps": {"type": "string"}, "rest_time": {"type": "string"}, "load_info": {"type": "string"}, "notes": {"type": "string"}}, ["exercise_name"]),
        _operational_tool("update_workout_exercise", "Atualiza um exercício existente do treino.", {"exercise_id": {"type": "string"}, "exercise_name": {"type": "string"}, "muscle_group": {"type": "string"}, "sets": {"type": "integer"}, "reps": {"type": "string"}, "rest_time": {"type": "string"}, "load_info": {"type": "string"}, "notes": {"type": "string"}}, ["exercise_id"]),
        _operational_tool("remove_workout_exercise", "Remove permanentemente um exercício; sempre exige confirmação do backend.", {"exercise_id": {"type": "string"}}, ["exercise_id"]),
        _operational_tool("update_health_condition", "Atualiza uma lesão ou condição de saúde já cadastrada.", {"condition_id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "injury_local": {"type": "string"}, "notes": {"type": "string"}, "origin": {"type": "string"}, "recommendations": {"type": "string"}, "severity": {"type": "string"}, "started_at": {"type": "string"}}, ["condition_id"]),
        _operational_tool("delete_health_condition", "Remove permanentemente uma condição de saúde; sempre exige confirmação do backend.", {"condition_id": {"type": "string"}}, ["condition_id"]),
    ]
)
