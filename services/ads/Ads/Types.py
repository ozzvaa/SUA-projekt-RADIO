from pydantic import BaseModel, Field
from typing import Optional, Literal

class RadioAd(BaseModel):
    title: str
    content: str

class AdModel(BaseModel):
    id: str
    owner_id: str
    title: str
    description: Optional[str]
    content: Optional[str]
    status: Literal["draft", "pending", "published", "expired"] = "draft"
    tags: list[str]
    cost_class_id: Optional[str]
    expiration_date: Optional[int]

class CostClass(BaseModel):
    id: str
    title: str
    min_duration_seconds: int
    max_duration_seconds: int
    price: float

class TagModel(BaseModel):
    id: str
    title: str
    name: str

