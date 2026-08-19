from typing import Literal

from pydantic import BaseModel, Field


class UpdatePatientRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    birth_date: str | None = None
    gender: str | None = Field(default=None, max_length=40)
    objective: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    access_status: Literal["ACTIVE", "EXPIRED"] | None = None


class UpdateMyPatientProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    birth_date: str | None = None
    gender: str | None = Field(default=None, max_length=40)
    objective: str | None = Field(default=None, max_length=240)


class ActivatePatientRequest(BaseModel):
    trial_days: Literal[7, 14, 30] | None = Field(default=None)
