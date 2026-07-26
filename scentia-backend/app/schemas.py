from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID

# Esquema para crear nuevo usuario
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

# Esquema para login
class UserLogin(BaseModel):
    username: str
    password: str

# Respuesta de usuario (sin hash de contraseña)
class UserOut(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Respuesta de Token de Sesión
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut