import re

from pydantic import BaseModel, Field, field_validator


class ChangeOwnPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, value: str) -> str:
        checks = (
            (" " not in value, "A senha não pode conter espaços."),
            (bool(re.search(r"[A-Z]", value)), "A senha deve conter uma letra maiúscula."),
            (bool(re.search(r"[a-z]", value)), "A senha deve conter uma letra minúscula."),
            (bool(re.search(r"\d", value)), "A senha deve conter um número."),
            (
                bool(re.search(r"[^A-Za-z0-9]", value)),
                "A senha deve conter um caractere especial.",
            ),
        )
        for valid, message in checks:
            if not valid:
                raise ValueError(message)
        return value
