import os
from contextlib import asynccontextmanager
from typing import Optional, Literal

import bcrypt
from fastapi import FastAPI, HTTPException, status
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from Users.Types import LoginCredentials, UserUpdate, RegisterCredentials, UserResponse, UserDetails, RegisterResponse
from bson import ObjectId

load_dotenv()


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
    yield
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.put("/users/{user_id}")
def update_user(user_id: str, updates: UserUpdate):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    update_data = updates.model_dump(exclude_unset=True, exclude_none=True)

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


@app.post("/users/login")
def login(credentials: LoginCredentials):
    # JWT authentication will be implemented here.
    pass


@app.post("/users/authenticate")
def authenticate():
    # JWT token validation will be implemented here.
    pass

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
