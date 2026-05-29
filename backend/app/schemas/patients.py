from datetime import date

from pydantic import BaseModel, EmailStr, Field


class CreatePatientRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    birth_date: date | None = None
    gender: str | None = Field(default=None, max_length=40)
    objective: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=1000)
    import_id: str | None = None


class CreatePatientResponse(BaseModel):
    profile_id: str
    patient_id: str
    email: EmailStr
    full_name: str
    role: str = "patient"
