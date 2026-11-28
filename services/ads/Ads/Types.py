from pydantic import BaseModel, Field
from typing import Optional, Literal


class Ad(BaseModel):
    id: str
    owner_id: str
    title: str

    description: Optional[str]
    content: Optional[str]
    status: Literal["draft", "pending", "published", "expired"] = "draft"
    tags: list[str] = Field(default_factory=list)
    cost_class_id: Optional[str]
    expiration_date: Optional[int]


class CreateAd(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "Summer Sale",
                    "description": "Summer promotion",
                    "content": "Visit our store!",
                    "tags": ["tag_food", "tag_events"],
                    "cost_class_id": "cost_medium",
                    "expiration_date": 1798761600
                }
            ]
        }
    }

    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    cost_class_id: Optional[str] = None
    expiration_date: Optional[int] = None


class UpdateAd(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    cost_class_id: Optional[str] = None
    expiration_date: Optional[int] = None


class CostClass(BaseModel):
    id: str
    title: str
    min_duration_seconds: int
    max_duration_seconds: int
    price: float


class TagModel(BaseModel):
    id: str
    name: str

class JWTPayload(BaseModel):
    sub: str
    role: Literal["user", "station"]
    exp: int

class AuthenticateResponse(BaseModel):
    authenticated: bool
    user_id: str
    role: Literal["user", "station"]