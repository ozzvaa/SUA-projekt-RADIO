from pydantic import BaseModel, Field


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

class UserData:
    def __init__(self, id: str, username: str, email: str | None = None):
        self.id = id
        self.username = username
        self.email = email

class UserUpdate:
    def __init__(self,username: str | None, email: str | None = None):
        self.username = username
        self.email = email
