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

class UserResponse(BaseModel):
    id: str
    username: str
    role: Literal["user", "station"]

class UserDetails(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: Literal["user", "station"]

class JWTResponse(BaseModel):
    message: str
    username: str
    access_token: str
    token_type: Literal["bearer"] = "bearer"

class JWTPayload(BaseModel):
    sub: str
    role: Literal["user", "station"]
    exp: int
    iat: int

class AuthenticateResponse(BaseModel):
    authenticated: bool
    user_id: str
    role: Literal["user", "station"]