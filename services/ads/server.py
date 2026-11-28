import os

import httpx
from fastapi import FastAPI, HTTPException, status, Depends
from pymongo import MongoClient
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from Ads.Types import RadioAd
from Ads.Seed import seed_database



@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_url = os.getenv(
        "ADS_DATABASE_URL", "mongodb://ads-db:27017/ads_db"
    )
    app.state.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    # Fail early if MongoDB is unavailable
    app.state.mongo_client.admin.command("ping")

    # Select database
    db = app.state.mongo_client.get_database()


    app.state.ads = app.state.mongo_client.get_database()["ads"]
    app.state.cost_classes = app.state.mongo_client.get_database()["cost_classes"]
    app.state.tags = app.state.mongo_client.get_database()["tags"]

    app.state.users_api = httpx.Client(
        base_url=f"http://users-api:8000",
        timeout=5.0
    )

    # Seed initial data
    seed_database(db)
    yield
    app.state.users_api.close()
    app.state.mongo_client.close()



app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
def ping():
    return {"ping": "pong"}

@app.get("/ping/users")
def ping_users():
    response = app.state.users_api.get("/users")
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
