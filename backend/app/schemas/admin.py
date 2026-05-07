from pydantic import BaseModel, EmailStr, Field


class CreateNutritionistRequest(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    crn: str | None = Field(default=None, max_length=40)
    specialty: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)


class CreateNutritionistResponse(BaseModel):
    profile_id: str
    nutritionist_id: str
    email: EmailStr
    full_name: str
    role: str = "nutritionist"
