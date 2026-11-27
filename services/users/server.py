import os
from contextlib import asynccontextmanager

import bcrypt
from fastapi import FastAPI, HTTPException, status
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from Users.Types import Credentials

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

@app.get("/users")
def get_users():
    users = app.state.users.find({}, {"password_hash": 0})
    return [
        {"id": str(user["_id"]), "username": user["username"]}
        for user in users
    ]


@app.post("/users/register", status_code=status.HTTP_201_CREATED)
def create_user(user: Credentials):
    password_hash = bcrypt.hashpw(
        user.password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    try:
        result = app.state.users.insert_one({
            "username": user.username,
            "password_hash": password_hash,
        })
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use",
        )

    return {"id": str(result.inserted_id), "username": user.username}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
