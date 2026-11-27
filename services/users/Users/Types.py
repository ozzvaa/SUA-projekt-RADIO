from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Optional, Literal

class RegisterCredentials(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    role: Literal["user", "station"] = "user"

class RegisterResponse(BaseModel):
    id: str
    username: str

class LoginCredentials(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Literal["user", "station"]] = None

class UserResponse(BaseModel):
    id: str
    username: str
    role: Literal["user", "station"]

class UserDetails(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: Literal["user", "station"]