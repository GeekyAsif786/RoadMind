from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    user: UserRead
