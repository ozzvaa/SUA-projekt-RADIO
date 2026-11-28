from datetime import datetime, timedelta, timezone
import os
import jwt
from contextlib import asynccontextmanager
from typing import Optional, Literal

import bcrypt
from fastapi import FastAPI, HTTPException, status, Depends
from pydantic import ValidationError
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from Users.Types import LoginCredentials, UserUpdate, RegisterCredentials, UserResponse, UserDetails, RegisterResponse, \
    JWTResponse, AuthenticateResponse, JWTPayload
from bson import ObjectId

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("HASH_ALG", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not configured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_url = os.getenv(
        "USERS_DATABASE_URL", "mongodb://users-db:27017/users_db"
    )
    app.state.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    # Fail early if MongoDB is unavailable and ensure usernames stay unique.
    app.state.mongo_client.admin.command("ping")
    app.state.users = app.state.mongo_client.get_database()["users"]
    app.state.users.create_index("username", unique=True)
    app.state.tokens = app.state.mongo_client.get_database()["tokens"]
    app.state.tokens.create_index(
        "expires_at",
        expireAfterSeconds=0
    )
    yield
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_access_token(user_id: str, role: str) -> str:
    iat = datetime.now(timezone.utc)
    expire = iat + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "role": role,
        "iat": iat,
        "exp": expire
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> JWTPayload:
    try:
        token = credentials.credentials

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat", "role"]}
        )

        validated = JWTPayload.model_validate(payload)

        if not app.state.tokens.find_one({"token": token}):
            raise HTTPException(status_code=401, detail="Token revoked")

        return validated

    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    except ValidationError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload"
        )


@app.get("/users", response_model=list[UserResponse])
def get_users(role: Optional[Literal["user", "station"]] = None):
    query = {"role": role} if role else {}

    users = app.state.users.find(query, {"password_hash": 0})

    return [
        UserResponse(
            id=str(user["_id"]),
            username=user["username"],
            role=user["role"]
        )
        for user in users
    ]


@app.get("/users/{user_id}", response_model=UserDetails)
def get_user(user_id: str):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = app.state.users.find_one(
        {"_id": ObjectId(user_id)},
        {"password_hash": 0}
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserDetails(
        id=str(user["_id"]),
        username=user["username"],
        email=user.get("email"),
        role=user["role"]
    )


@app.post("/users/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
def register_user(user: RegisterCredentials):
    password_hash = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    try:
        result = app.state.users.insert_one({
            "username": user.username,
            "email": user.email,
            "password_hash": password_hash,
            "role": user.role,
        })
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use",
        )

    return RegisterResponse(
        id=str(result.inserted_id),
        username=user.username
    )


@app.post("/users/login", response_model=JWTResponse)
def login_user(credentials: LoginCredentials):
    user = app.state.users.find_one({"username": credentials.username})

    if not user or not bcrypt.checkpw(
            credentials.password.encode("utf-8"),
            user["password_hash"].encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    token = create_access_token(
        str(user["_id"]),
        user.get("role", "user")
    )

    app.state.tokens.delete_many({"user_id": str(user["_id"])})

    app.state.tokens.insert_one({
        "token": token,
        "user_id": str(user["_id"]),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    })

    return JWTResponse(
        message="User logged in successfully",
        username=user["username"],
        access_token=token,
        token_type="bearer"
    )


@app.post("/users/authenticate")
def authenticate(current_user: JWTPayload = Depends(get_current_user)):
    return AuthenticateResponse(
        authenticated=True,
        user_id=current_user.sub,
        role=current_user.role
    )


@app.post("/users/refresh", response_model=JWTResponse)
def refresh_token(current_user: JWTPayload = Depends(get_current_user)):
    user_id = current_user.sub

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    user = app.state.users.find_one({"_id": ObjectId(user_id)}, {"password_hash": 0})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token(user_id, current_user.role)
    app.state.tokens.delete_many({"user_id": str(user_id)})
    app.state.tokens.insert_one({
        "token": token,
        "user_id": str(user_id),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    })

    return JWTResponse(
        message="Token refreshed successfully",
        username=user["username"],
        access_token=token,
        token_type="bearer"
    )


@app.put("/users/update")
def update_user(updates: UserUpdate, current_user: JWTPayload = Depends(get_current_user)):
    user_id = current_user.sub

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    update_data = updates.model_dump(exclude_unset=True, exclude_none=True)

    # Prevent changing role
    update_data.pop("role", None)

    if "password" in update_data:
        update_data["password_hash"] = bcrypt.hashpw(
            update_data.pop("password").encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

    if not update_data:
        raise HTTPException(status_code=400, detail="No updates provided")

    try:
        result = app.state.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Username already in use")

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated successfully"}


@app.put("/users/change_role")
def update_role(new_role: Literal["user", "station"], current_user: JWTPayload = Depends(get_current_user)):
    user_id = current_user.sub

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    result = app.state.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": new_role}},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Role updated successfully"}


@app.delete("/users/logout")
def logout_user(current_user: JWTPayload = Depends(get_current_user)):
    app.state.tokens.delete_many({"user_id": current_user.sub})

    return {"message": "Logged out successfully"}


@app.delete("/users/delete")
def delete_user(current_user: JWTPayload = Depends(get_current_user)):
    user_id = current_user.sub

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=401, detail="Invalid user ID in token")

    result = app.state.users.delete_one(
        {"_id": ObjectId(user_id)}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted successfully"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
